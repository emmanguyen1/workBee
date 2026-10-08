# Hivework

Hivework runs small Python bots that exchange events through Redis. Postgres stores an event history, and a FastAPI dashboard shows recent activity. The first hive is configured for Kalshi demo market work; the included starter bot only reports runtime status and does not connect to a market or place trades.

## Run locally

Install Git, Python 3.12, and Docker Desktop. Copy the example environment file and start the services:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>. The dashboard refreshes the Kalshi hive status stream every five seconds. Stop the services with `Ctrl+C`. Local Postgres data is stored in the `postgres_data` Docker volume.

## Repository layout

```text
core/                 Shared Bot, queen, Redis, Postgres, and alert helpers
dashboard/            FastAPI status dashboard
hives/kalshi/          First hive configuration and bots
docker-compose.yml     Local Redis, Postgres, queen, and dashboard
.env.example           Safe local defaults; copy to the ignored .env file
```

## Add a bot

Put each hive's code under its own folder. A bot subclasses `core.bot.Bot`, implements `run_once`, and publishes to a short topic name. The base class prefixes the hive name, so `status` becomes `kalshi:status` for the first hive.

```python
from core.bot import Bot

class ExampleFeed(Bot):
    name = "example_feed"
    every = 60

    async def run_once(self):
        await self.publish("observations", {"value": 1})
```

Register it in the hive's `hive.yml` with its import module:

```yaml
hive: example
bots:
  ExampleFeed:
    module: hives.example.bots.feed
```

The queen starts configured bots, restarts tasks that exit, and stops them when `KILL_SWITCH=true`. Keep credentials out of code and commits. Start with public/free APIs, check their terms and rate limits, and keep every trading integration on fake money and Kalshi's demo environment.

For a Kalshi demo integration, put the replacement `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY` values in your local `.env` file. The example file intentionally leaves both empty. Never commit `.env` or paste a private key into chat.

## Shared topics and dashboard API

Events are Redis streams named `<hive>:<topic>`. Read recent events at `/api/topics/{hive}/{topic}?count=50`; counts from 1 to 500 are accepted. `/health` is a basic dashboard health endpoint.

## Connect the Vercel dashboard to local Redis

The Vercel dashboard can read the local `kalshi:status` stream through the authenticated, read-only `redis-bridge` service. Keep Redis private; the bridge binds to `127.0.0.1:8765` and only serves that status topic. Set a strong `REDIS_BRIDGE_TOKEN` in `.env` and as a sensitive Production environment variable in Vercel, then start the bridge and a Cloudflare Quick Tunnel:

```bash
docker compose up -d --build redis-bridge
cloudflared tunnel --url http://localhost:8765
```

Set the generated HTTPS URL as Vercel's `REDIS_BRIDGE_URL` Production environment variable and redeploy with `vercel deploy --prod`. Quick Tunnels have no uptime guarantee; the local computer, Docker services, and tunnel process must stay online for the public dashboard to show live events.

## Project rules

- Never pay for services or enter payment details for this project without checking with the project owner.
- Never commit `.env`, keys, or passwords.
- Use official APIs and respect rate limits. Back off after HTTP 429 responses.
- Do not track private individuals.
- Keep changes in your hive folder where possible and use pull requests for shared work.
