import os
import duckdb
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("MOTHERDUCK_TOKEN")

if not token:
    raise SystemExit("MOTHERDUCK_TOKEN not found in .env")

print("Token loaded, length:", len(token))

con = duckdb.connect(f"md:pickem_spike?motherduck_token={token}")
result = con.execute("SELECT current_database()").fetchone()
print("Connected to:", result)