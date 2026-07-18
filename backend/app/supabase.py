from os import environ
from supabase import create_client, ClientOptions
from dotenv import load_dotenv
import httpx

load_dotenv("../.env")

url = environ["SUPABASE_URL"].strip()
key = environ["SUPABASE_KEY"].strip()
supabase = create_client(
    supabase_url=url,
    supabase_key=key,
    options=ClientOptions(
        httpx_client=httpx.Client(
            http2=False,
            timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10),
        ),
    ),
)


def first_row(query) -> dict | None:
    rows = query.limit(1).execute().data
    return rows[0] if rows else None
