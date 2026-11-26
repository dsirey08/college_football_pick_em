"""ESPN helpers: fetching plus pure parsing functions.

Fetch functions touch the network. Everything else is pure (input -> output),
so it can be unit-tested against saved fixtures in tests/fixtures/.
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"

PACIFIC = ZoneInfo("America/Los_Angeles")

# ESPN group IDs (verified Nov 22, 2026). Division label is what we store in teams.division.
GROUP_DIVISIONS = {"80": "FBS", "81": "FCS", "58": "DIII"}

LEAGUE_BOWL_WEEK = 16


def get_json(url, params=None):
    """GET a URL and return parsed JSON. Raises on HTTP errors so bad data is never parsed."""
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_espn_time(value):
    """ESPN timestamps look like '2026-08-22T07:00Z'. Return a timezone-aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------- calendar / weeks

def league_weeks(scoreboard):
    """Build the league's 16 weeks from a scoreboard response's calendar.

    Returns a list of dicts: week, start, end (UTC datetimes), and espn_params
    (the scoreboard query params that fetch that week's games).
    Weeks 1-15 = ESPN regular-season weeks. Week 16 = Dec 31 + Jan 1, Pacific time,
    pulled from ESPN's postseason "Bowls" week and filtered by date later.
    """
    season_year = scoreboard["season"]["year"]
    calendar = scoreboard["leagues"][0]["calendar"]
    weeks = []
    bowls_value = None
    for section in calendar:
        for entry in section["entries"]:
            if section["label"] == "Regular Season":
                weeks.append({
                    "week": int(entry["value"]),
                    "start": parse_espn_time(entry["startDate"]),
                    # ESPN endDate is the last minute (e.g. 07:59Z); +1 min makes it exclusive
                    "end": parse_espn_time(entry["endDate"]) + timedelta(minutes=1),
                    "espn_params": {"seasontype": 2, "week": int(entry["value"]), "dates": season_year},
                })
            elif section["label"] == "Postseason" and entry["label"] == "Bowls":
                bowls_value = int(entry["value"])
    if bowls_value is None:
        raise ValueError("ESPN calendar has no Postseason 'Bowls' entry; calendar format may have changed")
    bowl_start = datetime(season_year, 12, 31, tzinfo=PACIFIC)
    weeks.append({
        "week": LEAGUE_BOWL_WEEK,
        "start": bowl_start,
        "end": bowl_start + timedelta(days=2),  # through end of Jan 1 Pacific
        "espn_params": {"seasontype": 3, "week": bowls_value, "dates": season_year},
    })
    found = sorted(w["week"] for w in weeks)
    if found != list(range(1, 17)):
        raise ValueError(f"Expected league weeks 1-16, got {found}; ESPN calendar may have changed")
    return weeks


def league_week_for(moment, weeks):
    """Return the league week number containing `moment`, or None (e.g. Dec 13-30, or after Jan 1)."""
    for w in weeks:
        if w["start"] <= moment < w["end"]:
            return w["week"]
    return None


def weeks_to_pull(moment, weeks, count=2):
    """The next `count` league weeks that haven't ended yet (current week first).

    Pulling current + next means kickoff-time changes for next week get picked up early.
    """
    upcoming = [w for w in sorted(weeks, key=lambda w: w["week"]) if w["end"] > moment]
    return upcoming[:count]


def in_league_bowl_window(kickoff_utc, season_year):
    """True if a game kicks off on Dec 31 or Jan 1, Pacific time."""
    local = kickoff_utc.astimezone(PACIFIC)
    return (local.year, local.month, local.day) in [(season_year, 12, 31), (season_year + 1, 1, 1)]


# ---------------------------------------------------------------- conferences -> division

def parse_child_group_ids(children_response):
    """Core API 'children' responses list {'$ref': '.../groups/<id>?...'}. Return the ids."""
    ids = []
    for item in children_response.get("items", []):
        match = re.search(r"/groups/(\d+)", item["$ref"])
        if match:
            ids.append(match.group(1))
    return ids


def fetch_conference_divisions(season_year):
    """Map conference id -> division ('FBS'/'FCS'/'DIII') using the core API group tree. 3 calls."""
    mapping = {}
    for group_id, division in GROUP_DIVISIONS.items():
        url = f"{CORE_BASE}/seasons/{season_year}/types/2/groups/{group_id}/children"
        for conf_id in parse_child_group_ids(get_json(url, {"limit": 100})):
            mapping[conf_id] = division
    return mapping


# ---------------------------------------------------------------- events -> rows

def is_placeholder(team):
    """ESPN uses negative ids (and isActive False) for not-yet-decided teams, e.g. 'TBD' in title games."""
    return str(team.get("id", "")).startswith("-") or not team.get("id")


def parse_events(scoreboard, league_week, conference_divisions, season_year=None, feed_division=None):
    """Turn a scoreboard response into (games, teams, skipped).

    games: dicts with espn_event_id, week_id, home/away espn ids, kickoff_at (None if time TBD)
    teams: dict espn_team_id -> {team_name, division}
    skipped: list of (espn_event_id, reason)
    For league week 16, only games on Dec 31 / Jan 1 Pacific are kept.
    Division comes from the team's conference; if that's unknown (e.g. some DIII playoff
    games), fall back to feed_division, the division of the ESPN group feed being parsed.
    """
    games, teams, skipped = [], {}, []
    for event in scoreboard.get("events", []):
        comp = event["competitions"][0]
        sides = {c["homeAway"]: c["team"] for c in comp["competitors"]}
        if set(sides) != {"home", "away"}:
            skipped.append((event["id"], "missing home/away"))
            continue
        if any(is_placeholder(t) for t in sides.values()):
            skipped.append((event["id"], "placeholder team (TBD)"))
            continue
        kickoff = parse_espn_time(event["date"])
        if league_week == LEAGUE_BOWL_WEEK and not in_league_bowl_window(kickoff, season_year):
            skipped.append((event["id"], "postseason game outside Dec 31/Jan 1"))
            continue
        for team in sides.values():
            teams[team["id"]] = {
                "team_name": team.get("location") or team.get("displayName"),
                "division": conference_divisions.get(str(team.get("conferenceId"))) or feed_division or "Other",
            }
        games.append({
            "espn_event_id": event["id"],
            "week_id": league_week,
            "home_espn_id": sides["home"]["id"],
            "away_espn_id": sides["away"]["id"],
            "kickoff_at": kickoff if comp.get("timeValid", True) else None,
        })
    return games, teams, skipped
