import os

import httpx


async def send(message: str) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json={"content": message[:1900]})
        response.raise_for_status()
