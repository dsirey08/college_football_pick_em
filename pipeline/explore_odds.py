import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

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
    print(f"\n{game['away_team']} at {game['home_team']}")
    betmgm_found = False
    for bookmaker in game["bookmakers"]:
        if bookmaker["title"] == "BetMGM":
            betmgm_found = True
            outcomes = bookmaker["markets"][0]["outcomes"]
            for outcome in outcomes:
                print(f"{outcome['name']}: {outcome['point']}")
    if not betmgm_found:
        print(" No BetMGM line available - will score straight up")                





