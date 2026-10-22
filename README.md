# Hivework

## HivePath — internships & early careers

HivePath is a separate careers page inside the same Hivework FastAPI application,
not an embedded Kalshi widget or a separate public deployment. Open `/careers`
(also `/hivepath`) for HivePath. The original Kalshi demo stays at `/` and `/kalshi`.
Each page links to the other. The existing `queen` service keeps its original hive
configuration; a separate `careers-queen` runs the careers hive alongside it.

HivePath collects
public Greenhouse, Lever, and Ashby employer feeds every 15 minutes. No job API
keys are required. Configure employers in `hives/careers/employers.yml`; these are
individual employer boards, not a global search of all jobs. The initial directory
now includes 18 employers across technology, financial services, aerospace,
autonomous vehicles, healthcare technology, and nonprofit work.

Search across 14 inferred career fields, including marketing, finance, design,
HR, legal, operations, science, hardware, software, and customer-facing work.
The default view includes internships/co-ops, explicit new-grad roles, junior or
entry-level titles, and apprenticeships. Select "All roles & levels" for the full
catalog. Career stages rely on explicit title signals: an "associate" title alone
does not prove a role is entry level. Fields are title/department heuristics and
can be imperfect.

Combine field, employer, location, and workplace filters. Locations include
secondary offices supplied by the employer; country information is used when
explicitly supplied. Common location aliases (NYC, UK, USA) are recognized, but
the app does not infer countries for city-only listings or treat remote roles as
worldwide. An unspecified workplace is kept separate from on-site roles.
"Recently discovered" sorts by first observation in this database, not the
employer publication date. Coverage counters and filter counts describe the
whole currently stored catalog, including potentially stale snapshots.

Start with the existing local `.env` and `docker compose up --build`, then open
<http://localhost:8000/careers>. Kalshi remains at <http://localhost:8000/kalshi>.
The first collection may take
a minute. Redis and Postgres are private Docker services. The queen creates the
careers tables automatically. For a single collection inside the running stack:

```bash
docker compose exec careers-queen python -m hives.careers.collector
```

Opportunities use a light card layout with company branding, location, career
stage, skill coverage, application tracking, and a detailed requirements dialog.
Known employer domains load logos through Google's favicon service; unavailable
or unmapped logos fall back to company initials. No logo API key is needed.

Enter skills separated by commas, semicolons, or new lines, optionally followed by `|` and a project, coursework,
or work example. Add graduation year, enrollment, sponsorship needs, an optional
GPA on the 4.0 scale, and a preferred location. The skill vocabulary includes
business, marketing, design, finance, engineering, and laboratory tools. Explicit
minimum GPA phrases are checked when recognized; missing or differently worded
requirements still need manual review. The results separate skill evidence from recognized
eligibility rules and unknowns. Required skills have twice the weight of
preferred skills; contextual mentions are excluded from the score. This limited,
rule-based parser is not a hiring prediction or comprehensive eligibility check.
Review the full description and employer application page before applying.

“Match my profile” normalizes skill names, switches to fit ranking, and selects
listings with comparable skill requirements when skills are supplied. Filters
such as location and employer remain in place. Clear the comparable-requirements
filter to include community listings without descriptions. Unavailable scores
are shown separately from a measured 0% skill coverage. In an opportunity's
details, paste the employer's requirements to compare an otherwise unscored
listing; this text is processed without saving it and does not alter the source.

Guest profiles submitted for matching are not persisted on the server or
published into Redis. "Save on device" stores a guest profile in browser local
storage; guest application statuses also persist in that browser. Signed-in users
can explicitly save profiles and filters to their private account in Postgres;
their application status changes sync automatically. "Clear device data" clears
browser data and the current form; it does not delete a saved account. Automated
applications and personal alert delivery are not implemented. Do not
use device saving on a shared computer. The matching endpoint returns `no-store`.

Successful complete board snapshots update Postgres and emit metadata events on
`careers:jobs` (`discovered`, `changed`, `reopened`, `closed`). Failed checks retain
the prior snapshot and show a source error. A job disappears from the open catalog
only after a successful snapshot omits it; records remain in Postgres. Snapshots
older than 30 minutes are labeled in the interface. A listed role does not prove
the employer is actively hiring. Source feeds can omit details and their terms
must be checked before wider redistribution. The initial release does not merge
duplicates across different sources.

The deployed FastAPI app needs access to the same durable Postgres database as
the queen. A local-only Docker database cannot be reached from Vercel. No cloud
database or deployment is provisioned by these changes.

Run verification with `python -m unittest discover -s tests -v`.

### Accounts and saved preferences

Create an account or sign in above the profile form. Usernames are case-insensitive,
3–40 characters (letters, numbers, dots, dashes, underscores); passwords must be
12–128 characters. The first version does not collect email addresses or provide
email verification/password recovery. Keep access to your chosen password.

"Save profile & filters to account" persists the reviewed profile and current
search settings. Signing in or reloading account data restores them; new accounts
keep the current guest form until it is explicitly saved. Device-only guest
application statuses are not automatically uploaded into a new account. Signed-in
application statuses sync individually. Optimistic revisions prevent a stale tab
from overwriting a more recent profile/preferences save. Account data and sessions
are private to the authenticated user and are never put on the public Redis bus.

Passwords use scrypt with independent random salts. Only hashes of random session
tokens are stored; cookies are HttpOnly, SameSite=Lax, expire after 30 days, and are
Secure on HTTPS. Set `CAREERS_COOKIE_SECURE=true` for a deployed HTTPS service and
configure the reverse proxy's trusted forwarding headers correctly. Logout revokes
the current session. Account writes reject cross-origin browser requests, and
registration/login attempts are rate limited in Postgres. Production hosting needs
HTTPS, a private durable database, appropriate backups, and database access controls.
This local demo has not been publicly deployed.

### Simplify / Pitt CSC internship discovery

The collector also reads the public structured dataset linked from
<https://github.com/SimplifyJobs/Summer2027-Internships>. It keeps only entries with
`active=true`, `is_visible=true`, and the `Summer 2027` term. Closed, hidden, and
other-season records are excluded. Attribution and a link back to Pitt CSC & Simplify
are displayed. Community-list membership is not employer verification; the interface
labels these entries and directs users to the original application page.

The community dataset does not include full job descriptions. It supplies discovery
metadata only; missing skills and qualifications remain unassessed. Matching does
not invent a description from the title or treat source sponsorship/degree tags
as verified eligibility. Known Greenhouse, Lever, and Ashby application URLs are
deduplicated across sources; direct employer descriptions are preferred and the
community source attribution is preserved. Other URL formats may still contain
duplicates. Catalog totals count listed opportunities, including community entries.

### Resume import and qualification checklist

Use "Start with your resume" to upload a PDF, DOCX, or UTF-8 text file up to 4 MB,
or paste up to 60,000 characters. PDFs must contain selectable text and have no
more than 10 pages. Scanned/image-only or password-protected PDFs are unsupported;
paste text from an unlocked/OCR copy instead. Legacy `.doc` files are unsupported.

The importer returns suggested skills with source excerpts and explicit education
details. Multiple degree levels or graduation years stay unresolved; GPA is
imported only when its 4.0 scale is explicit. School prestige, names, contact
details, work authorization, sponsorship needs, experience duration, and
availability are not used as inferred matching criteria. Review all suggestions:
keyword detection cannot establish proficiency or verify a resume claim.

The draft does not change the search profile until the user checks the review
confirmation and clicks "Apply reviewed draft & match". Applying replaces the
skill list and merges filled draft education fields; other profile fields remain
as entered. Empty draft education fields preserve current values. Use "Clear
import" to discard a draft and its selected file/pasted text. Applying also clears
the import inputs. Device persistence still requires "Save on device".

`POST /api/careers/resume?format=pdf|docx|txt` accepts raw file bytes, not multipart
data. The filename is not sent. Parsing occurs in a child process with a
15-second timeout; Linux workers additionally have CPU and memory limits. DOCX XML
is parsed without entities or external resources. Uploaded files are not written
to disk, stored in Postgres, published in Redis, or sent to an AI provider. The
review response is marked `Cache-Control: no-store`. Deployment infrastructure
must also avoid request-body logging.

The profile now includes degree/program level, completion status, major,
self-reported experience duration, and an availability window. The qualification
checklist shows the employer quote, the relevant profile fact, and an explanation
for each recognized criterion. Earned degrees and ongoing programs are distinct;
unmatched related majors and experience duration remain questions for review.
Preferences are not eligibility blockers. Explicit start/end dates are compared
separately; seasons without dates remain unclear. Additional stated qualifications
outside the supported rules are shown for manual review when detected.

Skill groups distinguish alternatives from conjunctions: "Python or Java and SQL"
requires one language plus SQL. Old stored skill extractions are recomputed until
the collector refreshes them with the current extraction version. The displayed
percentage still measures weighted skill coverage only, not total eligibility or
hiring probability. Summaries list possible conflicts, unclear qualifications,
and required skill groups lacking profile evidence, with suggested next steps.

The Kalshi dashboard remains at `/` and `/kalshi`. Its existing queen uses
`HIVE_CONFIG` from `.env`, normally `hives/kalshi/hive.yml`; `careers-queen` uses
`hives/careers/hive.yml`. Both can run together.

## Original Kalshi integration

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

The portfolio dashboard reads Kalshi's demo API directly on the server using
`KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY`. Configure both as sensitive Production
environment variables in Vercel. The client is read-only and fixed to the demo
API host. It refreshes every 15 seconds, caches successful results for 10 seconds,
and backs off for 60 seconds after rate limiting. Positions and resting orders
are paginated; History shows the latest 50 fills. Unsupported snapshot metrics
are omitted. The portfolio no longer requires the local Redis bridge.

Unrealized gain/loss compares Kalshi's portfolio value with the summed remaining
`market_exposure_dollars`, before fees. It is not an all-time realized return.
Fees are shown separately because fees on currently open markets can include
earlier trades. Account value change starts at the first successful refresh of
the current page and includes non-profit movements such as deposits.

The deployed portfolio endpoint displays demo account balances and positions to
website visitors. Credentials stay server-side. Hive status describes the demo
API connection; the separate Redis topic API still reports bot runtime activity.

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
