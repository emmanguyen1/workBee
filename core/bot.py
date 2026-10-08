import asyncio
import logging
import os
from abc import ABC, abstractmethod

from core import alerts, bus, db

log = logging.getLogger(__name__)


class Bot(ABC):
    name = "bot"
    every = 30
    hive = "default"

    def __init__(self, **config):
        self.config = config

    async def publish(self, topic: str, payload: dict) -> None:
        await bus.publish(f"{self.hive}:{topic}", payload)
        await db.record(self.hive, self.name, "publish", {"topic": f"{self.hive}:{topic}", **payload})

    async def heartbeat(self) -> None:
        await bus.publish(f"{self.hive}:heartbeats", {"bot": self.name})
        await db.record(self.hive, self.name, "heartbeat")

    @abstractmethod
    async def run_once(self):
        raise NotImplementedError

    async def run_forever(self):
        while True:
            try:
                await self.run_once()
                await self.heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("%s failed", self.name)
                await db.record(self.hive, self.name, "error", {"error": str(exc)})
                try:
                    await alerts.send(f"Hivework bot `{self.hive}/{self.name}` failed: {exc}")
                except Exception:
                    log.exception("Discord alert failed")
            await asyncio.sleep(max(1, int(self.every)))
