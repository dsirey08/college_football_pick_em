import os
import sys

import duckdb
from dotenv import load_dotenv

load_dotenv()

if len(sys.argv) != 2:
    sys.exit("Usage: python sql/apply_schema.py <path/to/file.sql>")

with open(sys.argv[1]) as f:
    ddl = f.read()

if not os.getenv("MOTHERDUCK_TOKEN"):
    sys.exit("MOTHERDUCK_TOKEN is not set. Check your .env file.")

con = duckdb.connect("md:pickem_dev")

con.execute(ddl)
print(f"Applied {sys.argv[1]} to pickem_dev.")
con.close()