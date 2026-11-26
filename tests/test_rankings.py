"""Offline tests for espn.parse_rankings against a saved ESPN rankings response."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import espn  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "rankings_current.json"


class TestParseRankings(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())
        self.rows, self.teams, self.skipped = espn.parse_rankings(self.data)

    def rows_for(self, poll):
        return [r for r in self.rows if r["poll_type"] == poll]

    def test_four_polls_week_13(self):
        self.assertEqual({r["poll_type"] for r in self.rows}, {"cfp", "ap", "usa", "fcs"})
        self.assertEqual({r["week_id"] for r in self.rows}, {13})

    def test_cfp_top_25_only(self):
        cfp = self.rows_for("cfp")
        self.assertEqual(len(cfp), 25)
        self.assertEqual(sorted(r["rank"] for r in cfp), list(range(1, 26)))
        self.assertIn({"week_id": 13, "espn_team_id": "61", "poll_type": "cfp", "rank": 1}, cfp)

    def test_ap_others_get_rank_26_plus(self):
        ap = self.rows_for("ap")
        self.assertEqual(len(ap), 25 + 12)
        others = sorted(r["rank"] for r in ap if r["rank"] > 25)
        self.assertEqual(others[0], 26)  # New Mexico, 95 points
        self.assertEqual(len(others), 12)

    def test_tied_points_share_rank(self):
        poll = {"type": "ap", "season": {"type": {"type": 2}}, "occurrence": {"number": 5},
                "ranks": [], "others": [
                    {"points": 10, "team": {"id": "1", "location": "A"}},
                    {"points": 10, "team": {"id": "2", "location": "B"}},
                    {"points": 4, "team": {"id": "3", "location": "C"}}]}
        rows, _, _ = espn.parse_rankings({"rankings": [poll]})
        self.assertEqual([r["rank"] for r in rows], [26, 26, 28])

    def test_team_division_from_parent_group(self):
        self.assertEqual(self.teams["61"], {"team_name": "Georgia", "division": "FBS"})
        self.assertEqual(self.teams["2168"]["division"], "FCS")  # Dayton, FCS poll

    def test_postseason_poll_skipped(self):
        poll = {"type": "ap", "name": "AP Final", "season": {"type": {"type": 3}},
                "occurrence": {"number": 1}, "ranks": [], "others": []}
        rows, _, skipped = espn.parse_rankings({"rankings": [poll]})
        self.assertEqual(rows, [])
        self.assertEqual(len(skipped), 1)


if __name__ == "__main__":
    unittest.main()
