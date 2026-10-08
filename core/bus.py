import json
import os

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
    redis = get_redis()
    try:
        rows = await redis.xrevrange(topic, count=count)
        return [{"id": row_id, **json.loads(fields["data"])} for row_id, fields in reversed(rows)]
    finally:
        await redis.aclose()
