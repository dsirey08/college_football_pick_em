"""MotherDuck connection helper. Target 'dev' -> pickem_dev, 'prod' -> pickem_prod."""
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
