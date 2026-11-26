"""MotherDuck helpers. Target 'dev' -> pickem_dev, 'prod' -> pickem_prod."""
import os
import sys

import duckdb
from dotenv import load_dotenv

DATABASES = {"dev": "pickem_dev", "prod": "pickem_prod"}


def connect(target="dev"):
    load_dotenv()
    if not os.getenv("MOTHERDUCK_TOKEN"):
        sys.exit("MOTHERDUCK_TOKEN is not set. Check your .env file.")
    if target not in DATABASES:
        sys.exit(f"Unknown target {target!r}; use one of {list(DATABASES)}")
    return duckdb.connect(f"md:{DATABASES[target]}")


def upsert_teams(con, teams):
    """Insert teams we haven't seen (by espn_team_id). Existing rows are left alone.

    Stages rows in a local TEMP table, then sends ONE bulk INSERT ... SELECT to MotherDuck
    (executemany straight into MotherDuck = one network round trip per row = slow).
    DO NOTHING (not DO UPDATE): DuckDB can't update rows that other tables reference.
    Returns the number of new teams.
    """
    before = con.execute("SELECT count(*) FROM teams").fetchone()[0]
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
    return con.execute("SELECT count(*) FROM teams").fetchone()[0] - before
