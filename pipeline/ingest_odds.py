import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

api_key = os.getenv("ODDS_API_KEY")

url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

params = {
    "apiKey": api_key,
    "regions": "us",
    "markets": "spreads",
    "oddsFormat": "american"
}

response = requests.get(url, params=params)
data = response.json()

for game in data:
    home_team = game["home_team"]
    away_team = game["away_team"]
    commence_time = game["commence_time"]

    print(f"\n{away_team} at {home_team}")

    # look up home team in our database
    cursor.execute("""
                    SELECT team_id
                    FROM teams
                    WHERE odds_api_name = %s
                   """, (home_team,))
    home_result = cursor.fetchone()

    cursor.execute("""
                   SELECT team_id
                   FROM teams
                   WHERE odds_api_name = %s
                   """, (away_team,))
    away_result = cursor.fetchone()

    if home_result is None and away_result is None:
        print(" Skipping - one or both teams not in the watchlist")
        continue

    spread = None
    betmgm_found = False

    for bookmaker in game["bookmaker"]:
        if bookmaker["title"] == "BetMGM":
            betmgm_found = True
            outcomes = bookmaker["markets"][0]["outcomes"]
            for outcome in outcomes:
                if outcome["point"] < 0:
                    spread = outcome["point"]
    if not betmgm_found:
        print( "No BetMGM line available - will score straight up")