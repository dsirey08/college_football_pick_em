import os
import sys

import duckdb
from dotenv import load_dotenv

load_dotenv()

with open("sql/create_tables.sql") as f:
    ddl = f.read()

if not os.getenv("MOTHERDUCK_TOKEN"):
    sys.exit("MOTHERDUCK_TOKEN is not set. Check your .env file.")

con = duckdb.connect("md:pickem_dev")

con.execute(ddl)
print("Schema applied to pickem_dev.")
con.close()