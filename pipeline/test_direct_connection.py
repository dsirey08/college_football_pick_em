import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

database_url = os.getenv("DATABASE_URL")

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")

tables = cursor.fetchall()
print("Tables found:")
for table in tables:
    print(table[0])

conn.close()