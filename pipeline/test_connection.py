import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SECRET_KEY")

supabase = create_client(url, key)

response = supabase.table("weekly_games").select("*").execute()
print("Connection sucessful:", response)