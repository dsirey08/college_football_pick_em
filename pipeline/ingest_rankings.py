"""Ingest ESPN's latest polls (CFP, AP, Coaches, FCS Coaches) into the rankings table.

Usage:
  python pipeline/ingest_rankings.py              # latest polls -> pickem_dev
  python pipeline/ingest_rankings.py --dry-run    # fetch and parse only
  python pipeline/ingest_rankings.py --target prod

Stores ALL ranked teams (top 25 plus "others receiving votes" as rank 26+), not just
the watchlist: land raw, filter in dbt. The CFP-else-AP rule also lives in dbt.
Ranked teams not yet in teams are added (is_listed = FALSE).
Idempotent: upsert on (week_id, team_id, poll_type); a re-issued poll updates rank.
"""
import argparse
import time

import db
import espn


def write(con, rows):
    before = con.execute("SELECT count(*) FROM rankings").fetchone()[0]
    con.execute("""
        CREATE OR REPLACE TEMP TABLE stg_rankings (
            week_id INTEGER, espn_team_id VARCHAR, poll_type VARCHAR, rank INTEGER)
    """)
    con.executemany(
        "INSERT INTO stg_rankings VALUES (?, ?, ?, ?)",
        [(r["week_id"], r["espn_team_id"], r["poll_type"], r["rank"]) for r in rows],
    )
    con.execute("""
        INSERT INTO rankings (week_id, team_id, poll_type, rank)
        SELECT s.week_id, t.team_id, s.poll_type, s.rank
        FROM stg_rankings s
        JOIN teams t ON t.espn_team_id = s.espn_team_id
        ON CONFLICT (week_id, team_id, poll_type) DO UPDATE SET rank = excluded.rank
    """)
    after = con.execute("SELECT count(*) FROM rankings").fetchone()[0]
    return before, after


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default="dev", choices=["dev", "prod"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = espn.get_json(f"{espn.SITE_BASE}/rankings")
    rows, teams, skipped = espn.parse_rankings(data)
    summary = {}
    for r in rows:
        key = (r["poll_type"], r["week_id"])
        summary[key] = summary.get(key, 0) + 1
    for (poll, week), n in sorted(summary.items()):
        print(f"  {poll:>4} week {week}: {n} teams")
    if skipped:
        print(f"Skipped polls: {skipped}")
    if not rows:
        raise SystemExit("No rankings parsed; ESPN response may have changed.")

    if args.dry_run:
        print("Dry run: no database writes.")
        return

    t0 = time.time()
    con = db.connect(args.target)
    new_teams = db.upsert_teams(con, teams)
    before, after = write(con, rows)
    con.close()
    print(f"Teams: +{new_teams} new. Rankings: {before} -> {after} rows (+{after - before}). "
          f"DB time {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
