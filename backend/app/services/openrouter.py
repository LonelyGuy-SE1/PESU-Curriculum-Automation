import os, json
from httpx import Client
from dotenv import load_dotenv

load_dotenv("../.env")

URL   = os.environ["OPENROUTER_URL"]
KEY   = os.environ["OPENROUTER_API_KEY"]
MODEL = os.environ["OPENROUTER_MODEL"]

def call(system: str, user: str) -> dict:
    with Client(timeout=120) as c:
        r = c.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json={
            "model": MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        r.raise_for_status()
        data = r.json()
        if "choices" not in data:
            raise RuntimeError(f"OpenRouter response missing choices: {data.get('error') or data}")
        text = data["choices"][0]["message"]["content"]
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
