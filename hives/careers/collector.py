import asyncio
import logging

import httpx

from core.bot import Bot
from core import db
from hives.careers import store
from hives.careers.feeds import employers, fetch_board

log = logging.getLogger(__name__)


class JobCollector(Bot):
    name = "job_collector"
    every = 900

    async def run_once(self):
        await store.initialize()
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Hivework-Careers/0.1"}) as client:
            for employer in employers():
                try:
                    jobs = await fetch_board(client, employer)
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    message = "Rate limited; will retry next scheduled check." if status == 429 else "Employer feed unavailable; keeping last successful snapshot."
                    log.warning("%s: %s", employer["name"], message)
                    await store.record_error(employer, message)
                    await self.publish("status", {"company": employer["name"], "state": "unavailable"})
                    continue
                changes = await store.save_snapshot(employer, jobs)
                for change in changes:
                    await self.publish("jobs", change)
                await self.publish("status", {"company": employer["name"], "state": "running", "jobs": len(jobs), "changes": len(changes)})


async def main():
    await db.initialize()
    bot = JobCollector()
    bot.hive = "careers"
    await bot.run_once()


if __name__ == "__main__":
    asyncio.run(main())
