import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SECRET_KEY")

try:
    print(f"Connecting to Supabase at {url}...")
    supabase: Client = create_client(url, key)
    # Perform a safe select limit 1
    res = supabase.table("reports").select("*").limit(1).execute()
    print("PASS: Successfully connected to Supabase and queried reports table.")
except Exception as e:
    print(f"FAIL: Database connection failed. Error: {e}")
