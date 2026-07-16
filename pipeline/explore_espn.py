import requests
import json

url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=20241005"

response = requests.get(url)
data = response.json()

events = data['events']
first_game = events[0]
competition = first_game["competitions"][0]

print("Team 1 details:")
print("Home/Away:", competition["competitors"][0]["homeAway"])
print("Winner:", competition["competitors"][0]["winner"])
print("Score:", competition["competitors"][0]["score"])
print("Team:", competition["competitors"][0]["team"]["id"], competition["competitors"][0]["team"]["displayName"])