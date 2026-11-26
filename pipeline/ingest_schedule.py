"""Ingest ESPN schedules (FBS, FCS, DIII) into the schedule table.

Usage:
  python pipeline/ingest_schedule.py                 # current + next league week, pickem_dev
  python pipeline/ingest_schedule.py --week 14       # one specific league week (backfill)
  python pipeline/ingest_schedule.py --dry-run       # fetch and parse only, no database writes
  python pipeline/ingest_schedule.py --target prod   # write to pickem_prod

Idempotent: teams upsert by espn_team_id (DO NOTHING), games upsert by espn_event_id
(only kickoff_at is updated, because DuckDB can't update FK/indexed columns on referenced rows).
"""
import argparse
from datetime import datetime, timezone

import espn


def fetch_week(week, conference_divisions, season_year):
    """Fetch and parse one league week across all three ESPN groups. Dedupes by event id."""
    games, teams, skipped = {}, {}, []
    # Narrowest feed first: if a team's conference is unknown, the first feed it appears in
    # labels it, and a DIII team should be labeled by the DIII feed, not a broader one.
    for group_id in ["58", "81", "80"]:
        params = {**week["espn_params"], "groups": group_id, "limit": 500}
        data = espn.get_json(f"{espn.SITE_BASE}/scoreboard", params)
        g, t, s = espn.parse_events(
            data, week["week"], conference_divisions, season_year,
            feed_division=espn.GROUP_DIVISIONS[group_id])
        for game in g:
            games[game["espn_event_id"]] = game  # FBS-vs-FCS games appear in both feeds
        for espn_id, team in t.items():
            # first label wins (see feed order above)
            teams.setdefault(espn_id, team)
        skipped.extend(s)
        print(f"  week {week['week']} group {group_id}: {len(data.get('events', []))} events, kept {len(g)}")
    return list(games.values()), teams, skipped


def write(con, games, teams):
    """Upsert teams then games. Returns (new_teams, games_before, games_after)."""
    teams_before = con.execute("SELECT count(*) FROM teams").fetchone()[0]
    # Stage rows in a local TEMP table (fast, no network per row), then send ONE bulk
    # INSERT ... SELECT to MotherDuck. executemany straight into MotherDuck = 1 round trip per row.
    con.execute("CREATE OR REPLACE TEMP TABLE stg_teams (team_name VARCHAR, division VARCHAR, espn_team_id VARCHAR)")
    con.executemany(
        "INSERT INTO stg_teams VALUES (?, ?, ?)",
        [(t["team_name"], t["division"], espn_id) for espn_id, t in teams.items()],
    )
    con.execute("""
        INSERT INTO teams (team_name, division, is_listed, espn_team_id)
        SELECT team_name, division, FALSE, espn_team_id FROM stg_teams
        ON CONFLICT (espn_team_id) DO NOTHING
    """)
    teams_after = con.execute("SELECT count(*) FROM teams").fetchone()[0]

    games_before = con.execute("SELECT count(*) FROM schedule").fetchone()[0]
    con.execute("""
        CREATE OR REPLACE TEMP TABLE stg_schedule (
            espn_event_id VARCHAR, week_id INTEGER,
            home_espn_id VARCHAR, away_espn_id VARCHAR, kickoff_at TIMESTAMPTZ)
    """)
    con.executemany(
        "INSERT INTO stg_schedule VALUES (?, ?, ?, ?, ?)",
        [(g["espn_event_id"], g["week_id"], g["home_espn_id"], g["away_espn_id"], g["kickoff_at"]) for g in games],
    )
    con.execute("""
        INSERT INTO schedule (espn_event_id, week_id, home_team_id, away_team_id, kickoff_at)
        SELECT s.espn_event_id, s.week_id, h.team_id, a.team_id, s.kickoff_at
        FROM stg_schedule s
        JOIN teams h ON h.espn_team_id = s.home_espn_id
        JOIN teams a ON a.espn_team_id = s.away_espn_id
        ON CONFLICT (espn_event_id) DO UPDATE SET kickoff_at = excluded.kickoff_at
    """)
    games_after = con.execute("SELECT count(*) FROM schedule").fetchone()[0]
    return teams_after - teams_before, games_before, games_after


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--week", type=int, help="league week 1-16 (default: current + next)")
    parser.add_argument("--target", default="dev", choices=["dev", "prod"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scoreboard = espn.get_json(f"{espn.SITE_BASE}/scoreboard")
    season_year = scoreboard["season"]["year"]
    weeks = espn.league_weeks(scoreboard)
    if args.week:
        selected = [w for w in weeks if w["week"] == args.week]
        if not selected:
            raise SystemExit(f"No league week {args.week}")
    else:
        selected = espn.weeks_to_pull(datetime.now(timezone.utc), weeks)
    if not selected:
        print("Season is over; nothing to pull.")
        return

    print(f"Season {season_year}; pulling league weeks {[w['week'] for w in selected]}")
    conference_divisions = espn.fetch_conference_divisions(season_year)
    print(f"Loaded {len(conference_divisions)} conference -> division mappings")

    all_games, all_teams, all_skipped = [], {}, []
    for week in selected:
        g, t, s = fetch_week(week, conference_divisions, season_year)
        all_games += g
        all_teams.update(t)
        all_skipped += s

    reasons = {}
    for _, reason in all_skipped:
        reasons[reason] = reasons.get(reason, 0) + 1
    print(f"Parsed {len(all_games)} games, {len(all_teams)} teams; skipped {reasons or 'none'}")
    other = sorted(t["team_name"] for t in all_teams.values() if t["division"] == "Other")
    if other:
        print(f"{len(other)} teams outside FBS/FCS/DIII (division 'Other'), e.g. {other[:5]}")

    if args.dry_run:
        print("Dry run: no database writes.")
        return

    import db  # imported here so --dry-run works without MotherDuck set up
    import time
    t0 = time.time()
    con = db.connect(args.target)
    new_teams, before, after = write(con, all_games, all_teams)
    con.close()
    print(f"Teams: +{new_teams} new. Schedule: {before} -> {after} rows (+{after - before}). "
          f"DB time {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
