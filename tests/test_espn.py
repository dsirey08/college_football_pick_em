"""Offline tests for pipeline/espn.py, using real ESPN responses saved in tests/fixtures/.

Run: python -m pytest tests   (or: python -m unittest discover tests)
"""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import espn  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


# A few real FBS conference ids (ACC=1, Big 12=4, Big Ten=5, SEC=8, Pac-12=9, CUSA=12, MW=17)
CONFS = {"1": "FBS", "4": "FBS", "5": "FBS", "8": "FBS", "9": "FBS", "12": "FBS", "17": "FBS"}


class TestLeagueWeeks(unittest.TestCase):
    def setUp(self):
        self.weeks = espn.league_weeks(load("scoreboard_current.json"))

    def test_sixteen_weeks(self):
        self.assertEqual(sorted(w["week"] for w in self.weeks), list(range(1, 17)))

    def test_thanksgiving_is_week_13(self):
        self.assertEqual(espn.league_week_for(utc(2026, 11, 26, 17, 0), self.weeks), 13)

    def test_monday_rollover_pacific(self):
        # Sunday Nov 29, 11:59 pm Pacific = Nov 30 07:59 UTC -> still week 13
        self.assertEqual(espn.league_week_for(utc(2026, 11, 30, 7, 59), self.weeks), 13)
        # Monday Nov 30, 12:00 am Pacific -> week 14
        self.assertEqual(espn.league_week_for(utc(2026, 11, 30, 8, 0), self.weeks), 14)

    def test_bowl_gap_is_not_a_league_week(self):
        self.assertIsNone(espn.league_week_for(utc(2026, 12, 20, 12, 0), self.weeks))

    def test_week_16_window_is_pacific(self):
        # Dec 31 00:30 Pacific = 08:30 UTC
        self.assertEqual(espn.league_week_for(utc(2026, 12, 31, 8, 30), self.weeks), 16)
        # Jan 1 11:30 pm Pacific = Jan 2 07:30 UTC -> still week 16
        self.assertEqual(espn.league_week_for(utc(2027, 1, 2, 7, 30), self.weeks), 16)
        self.assertIsNone(espn.league_week_for(utc(2027, 1, 2, 8, 30), self.weeks))

    def test_weeks_to_pull(self):
        pulled = espn.weeks_to_pull(utc(2026, 11, 26, 17, 0), self.weeks)
        self.assertEqual([w["week"] for w in pulled], [13, 14])
        # during the bowl gap, the only upcoming league week is 16
        pulled = espn.weeks_to_pull(utc(2026, 12, 20, 12, 0), self.weeks)
        self.assertEqual([w["week"] for w in pulled], [16])
        self.assertEqual(espn.weeks_to_pull(utc(2027, 1, 5), self.weeks), [])

    def test_week_16_fetches_espn_bowls(self):
        w16 = [w for w in self.weeks if w["week"] == 16][0]
        self.assertEqual(w16["espn_params"]["seasontype"], 3)


class TestParseEvents(unittest.TestCase):
    def test_placeholder_tbd_teams_are_skipped(self):
        games, teams, skipped = espn.parse_events(load("w14_fbs.json"), 14, CONFS)
        self.assertEqual(len(games), 3)  # Liberty-JSU, Boise-SDSU, Miami-Wake
        self.assertEqual(sum(1 for _, r in skipped if "placeholder" in r), 7)
        self.assertNotIn("-1", teams)
        self.assertNotIn("-2", teams)

    def test_game_fields(self):
        games, teams, _ = espn.parse_events(load("w14_fbs.json"), 14, CONFS)
        g = [g for g in games if g["espn_event_id"] == "401869535"][0]
        self.assertEqual((g["home_espn_id"], g["away_espn_id"]), ("2335", "55"))
        self.assertEqual(g["kickoff_at"], utc(2026, 12, 5, 0, 0))
        self.assertEqual(g["week_id"], 14)
        self.assertEqual(teams["2335"], {"team_name": "Liberty", "division": "FBS"})

    def test_unknown_conference_is_other(self):
        _, teams, _ = espn.parse_events(load("w14_fbs.json"), 14, {})
        self.assertEqual({t["division"] for t in teams.values()}, {"Other"})

    def test_unknown_conference_falls_back_to_feed_division(self):
        _, teams, _ = espn.parse_events(load("w14_fbs.json"), 14, {}, feed_division="DIII")
        self.assertEqual({t["division"] for t in teams.values()}, {"DIII"})

    def test_known_conference_beats_feed_division(self):
        _, teams, _ = espn.parse_events(load("w14_fbs.json"), 14, CONFS, feed_division="DIII")
        self.assertEqual(teams["2335"]["division"], "FBS")

    def test_bowl_week_keeps_only_dec31_jan1_pacific(self):
        games, _, skipped = espn.parse_events(load("bowls_2025.json"), 16, CONFS, season_year=2025)
        ids = {g["espn_event_id"] for g in games}
        names = {e["id"]: e["shortName"] for e in load("bowls_2025.json")["events"]}
        kept = sorted(names[i] for i in ids)
        # Alamo Bowl (Dec 30, 6 pm PT) is excluded even though it's Dec 31 in UTC.
        self.assertNotIn("USC VS TCU", kept)
        # Cotton (Dec 31, 4:30 pm PT) and Sugar (Jan 1, 5 pm PT) are in, even though they're Jan 1/2 UTC.
        self.assertIn("MIA VS OSU", kept)
        self.assertIn("MISS VS UGA", kept)
        self.assertEqual(len(games), 8)
        self.assertTrue(all(r == "postseason game outside Dec 31/Jan 1" for _, r in skipped))

    def test_tbd_kickoff_time_stored_as_none(self):
        data = load("w14_fbs.json")
        data["events"][0]["competitions"][0]["timeValid"] = False
        games, _, _ = espn.parse_events(data, 14, CONFS)
        self.assertIsNone(games[0]["kickoff_at"])


class TestConferenceRefs(unittest.TestCase):
    def test_parse_child_group_ids(self):
        resp = {"items": [
            {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/2026/types/2/groups/1?lang=en"},
            {"$ref": "http://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/2026/types/2/groups/151?lang=en"},
        ]}
        self.assertEqual(espn.parse_child_group_ids(resp), ["1", "151"])


if __name__ == "__main__":
    unittest.main()
