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

prepared = requests.Request('GET', url,params=params).prepare()


response = requests.get(url, params=params)

data = response.json()

game = data[0]
print("Game:", game["away_team"], "at", game["home_team"])
print("Commence time:", game["commence_time"])
print("Bookmakers:", [b["title"] for b in game["bookmakers"]])

for bookmaker in game["bookmakers"]:
    if bookmaker["title"] == "BetMGM":
        outcomes = bookmaker["markets"][0]["outcomes"]
        for outcome in outcomes:
            print(f"{outcome['name']}: {outcome['point']}")
            
