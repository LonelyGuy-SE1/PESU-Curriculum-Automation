from os import environ
from supabase import create_client
from dotenv import load_dotenv

load_dotenv("../.env")

url=environ["SUPABASE_URL"]
key=environ["SUPABASE_KEY"]
supabase=create_client(supabase_url=url, supabase_key=key)
