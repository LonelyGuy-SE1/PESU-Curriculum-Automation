from os import environ
from supabase import create_client, ClientOptions
from dotenv import load_dotenv
import httpx

load_dotenv("../.env")

url=environ["SUPABASE_URL"]
key=environ["SUPABASE_KEY"]
supabase=create_client(
    supabase_url=url,
    supabase_key=key,
    options=ClientOptions(
        httpx_client=httpx.Client(http2=False),
    ),
)
