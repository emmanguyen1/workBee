from core.bot import Bot


class HiveStatus(Bot):
    """Starter bot proving the runtime works; it makes no market requests."""
    name = "hive_status"
    every = 30

    async def run_once(self):
        await self.publish("status", {"state": "running", "mode": "demo-only"})
