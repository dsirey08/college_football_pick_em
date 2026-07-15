import requests
import json

url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"

response = requests.get(url)
data = response.json()

rankings = data["rankings"]

for ranking in rankings:
    print("Poll name:", ranking["name"])

print("\nFirst team in first poll:")
print(json.dumps(rankings[0]["ranks"][0], indent=2))