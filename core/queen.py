import asyncio
import importlib
import logging
import os
import signal

import yaml

from core import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("queen")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


async def run_bot(hive: str, class_name: str, config: dict):
    module_name = config.pop("module", None)
    if not module_name:
        raise ValueError(f"Bot {class_name} needs a module in hive.yml")
    cls = getattr(importlib.import_module(module_name), class_name)
    bot = cls(**config)
    bot.hive = hive
    bot.name = config.get("name", getattr(cls, "name", class_name))
    await bot.run_forever()


async def main():
    await db.initialize()
    config = load_config(os.getenv("HIVE_CONFIG", "hives/kalshi/hive.yml"))
    hive = config.get("hive", "default")
    tasks = {}
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopping.set)
    log.info("Queen starting hive %s", hive)
    while not stopping.is_set():
        if os.getenv("KILL_SWITCH", "false").lower() == "true":
            log.warning("Kill switch is on; stopping all bots")
            break
        for class_name, raw in config.get("bots", {}).items():
            spec = raw if isinstance(raw, dict) else {}
            task = tasks.get(class_name)
            if task is None or task.done():
                if task is not None:
                    log.error("Bot %s stopped; restarting", class_name)
                else:
                    log.info("Starting bot %s", class_name)
                tasks[class_name] = asyncio.create_task(run_bot(hive, class_name, dict(spec)), name=class_name)
        await asyncio.sleep(2)
    for task in tasks.values():
        task.cancel()
    await asyncio.gather(*tasks.values(), return_exceptions=True)
    log.info("Queen stopped")


if __name__ == "__main__":
    asyncio.run(main())
