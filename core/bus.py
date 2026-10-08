import json
import os
from urllib.parse import quote

import httpx
from redis.asyncio import Redis


def get_redis() -> Redis:
    return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


async def publish(topic: str, payload: dict) -> None:
    if ":" not in topic:
        raise ValueError("Topics must be namespaced as hive:topic")
    redis = get_redis()
    try:
        await redis.xadd(topic, {"data": json.dumps(payload)}, maxlen=10000, approximate=True)
    finally:
        await redis.aclose()


async def latest(topic: str, count: int = 50) -> list[dict]:
    bridge_url = os.getenv("REDIS_BRIDGE_URL")
    if bridge_url:
        hive, _, topic_name = topic.partition(":")
        if not hive or not topic_name:
            raise ValueError("Topics must be namespaced as hive:topic")
        headers = {}
        token = os.getenv("REDIS_BRIDGE_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{bridge_url.rstrip('/')}/api/topics/{quote(hive, safe='')}/{quote(topic_name, safe='')}",
                params={"count": count},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["events"]

    redis = get_redis()
    try:
        rows = await redis.xrevrange(topic, count=count)
        return [{"id": row_id, **json.loads(fields["data"])} for row_id, fields in reversed(rows)]
    finally:
        await redis.aclose()
