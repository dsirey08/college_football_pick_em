import os
import requests
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

ESPN_RANKINGS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"

response = requests.get(ESPN_RANKINGS_URL)
data = response.json()

ap_poll = None
for ranking in data["rankings"]:
    if ranking["name"] == "AP Top 25":
        ap_poll = ranking
        break

if ap_poll is None:
    print("AP poll not found")
else:
    print(f"Found poll: {ap_poll['name']}")
    print(f"Number of teams ranked: {len(ap_poll['ranks'])}")

    for rank_entry in ap_poll["ranks"]:
        team = rank_entry["team"]
        rank = rank_entry["current"]
        espn_team_id = team["id"]
        team_name = team["location"]

        cursor.execute("""
            SELECT team_id
            FROM teams
            WHERE espn_team_id = %s
            """, (espn_team_id,))
        
        result = cursor.fetchone()

        if result is None:
            print(f"Skipping # {rank} {team_name} - not in watchlist")
        else:
            team_id = result[0]
            cursor.execute("""
                INSERT INTO rankings (week_id, team_id, poll_type, rank)
                VALUES (%s, %s, %s, %s)
                """,  (1, team_id, 'AP', rank))
            print(f"Inserted # {rank} {team_name}")

conn.commit()
conn.close()

