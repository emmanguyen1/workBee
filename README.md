# workBee 🐝

Find current internships, jobs, research opportunities, and first-/second-year postings
that fit your skills and goals.

<img src="hives/careers/static/workbee-logo.png" alt="workBee professional bee" width="112">

**Broader discovery development:** `feat/workbee-beyond-tech`, based on
the existing `feat/hivepath-careers` development branch. This branch adds nontechnical
careers, practical comparison tools and a personal application planner.
See [research and feature details](docs/workbee-expansion.md).

## Features

- Explore healthcare, education, business, public policy, nonprofits, marketing,
  finance, research, labs, engineering and technology.
- Select multiple **career fields** and **employer industries** independently.
  Industry and career-field menus are alphabetical; counts follow the other filters.
- Filter by explicit pay information, time-commitment wording, posting recency,
  upcoming deadlines, geography, employer and career stage.
- Compare up to three opportunities in a temporary side-by-side shortlist.
- Add private notes, a next action and a follow-up date to saved applications;
  see your next steps and export your saved tracker as CSV.
- Compare skills and qualifications with posting excerpts, missing requirements,
  eligibility questions, and an explained skill-coverage score.
- Import PDF, DOCX, or text resumes, review supporting examples, and merge or
  replace skills before matching. Learning goals are not treated as experience.
- Create a private user profile with display name, school, and career headline;
  save matching skills, search preferences, and application statuses.
- Sort by **Most relevant**, **Most recent**, **Closing soon**, or **Company A–Z**.
  Industry choices are alphabetical. Closing dates come only from explicit employer
  fields/posting text; missing dates sort last and past explicit deadlines are excluded.
- Check source-feed availability; recognize employers through cached logos.

## Current postings only

The web search includes roles listed in configured employer feeds within the
last 30 minutes, excluding removed, stale, community-only listings and researched
program guides. Feed presence is not a guarantee that the application portal
accepts submissions; confirm on the employer website.

The **First & second year postings** opportunity type filters current internships
with explicit class-year wording in the posting itself. There are no separate
class-year-wording or program-guide-status controls. Tech sectors, country,
state/province, employer, workplace, keywords, and career stage remain available
in a left filter sidebar, with keyword search above the results. A narrow category may have no current listings. Career fields and employer industries
are distinct, and all professions are included by default on this branch.
Historical program research remains in the source tree/API for compatibility,
but closed cycles, general overviews, and signup pages are not web search results.

## Resume matching and your profile

Resume import prefers concrete project/work/course examples, reports listed-only
skills separately, recognizes more business/science/software tools, and skips
obvious negative-experience or future-learning statements. Review and correct the
draft, then merge it with your existing skills (default) or replace them. Equal
skill-coverage results favor supporting examples; examples remain self-reported.

Open **[My account](http://localhost:8001/account)** through the header to register
or sign in, import a resume, edit your profile, and manage saved applications. Add a display name, optional school, and career headline. Save profile
and filters explicitly to restore them across sessions/devices. Unsaved changes
are indicated; existing accounts and application tracking are preserved.

## Run locally

Requires Git, Docker Desktop/Compose, and Python 3.12+ for development.

```sh
git clone https://github.com/emmanguyen1/workBee.git
cd workBee
git switch feat/workbee-beyond-tech
cp .env.workbee.example .env
docker compose up -d --build workbee careers-queen
```

Open **http://localhost:8001/**. Allow time for initial collection. No paid job
API key is required. Compose starts private Redis and Postgres services;
database data survives container restarts in a named volume. If a local `.env`
already exists, keep it and add only needed settings instead of replacing it.

## Sources and coverage

Public Greenhouse, Lever, and Ashby boards plus the
[Simplify/Pitt CSC Summer 2027 list](https://github.com/SimplifyJobs/Summer2027-Internships)
feed the catalog. Configured boards are checked every 15 minutes while the
collector runs. Add employers in `hives/careers/employers.yml` (including public-health, policy, education and business boards).
Manually reviewed program archives live in `hives/careers/programs.yml`.
Additional healthcare/business feeds include Oscar Health, Commure, Included
Health, Carta, Gusto, Brex, and Flexport. Aerospace coverage also includes
Rocket Lab and Astranis alongside SpaceX. Broader sources include APHA, ACLU,
Human Rights Watch, Vera, Achievement First and AlphaSights. Research and lab technology feeds include
Ai2, Recursion, Chan Zuckerberg Initiative, and Lila Sciences.

This is a curated catalog, not every available position. Feed-listed does not
prove an application form accepts submissions. Failed checks mean unknown, not
closed; community listings require employer confirmation. Remote does not mean
worldwide. Unclear city-only locations remain unspecified. State/province parsing
covers the US and Canada; country filters use explicit feed evidence.

## Matching and accounts

Matching is rule-based coverage, not a hiring probability or complete eligibility
decision. Unknowns stay explicit; class-year filters show wording from the posting.
Pay and commitment filters reflect explicit posting wording; missing information
stays unknown. Follow-up dates are personal planning dates, with no email or
background notifications. Raw resume files are not persisted or sent to an AI provider. Review extraction
drafts before use. Guest application tracking can stay in browser storage; account profiles,
preferences, and application statuses use Postgres. Email verification and
account recovery are not implemented. Keep production credentials private;
never commit `.env` or keys.

## Development checks

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -q
node --test tests/test_careers_ui.mjs
```

Opt-in database integration checks:

```sh
docker compose exec -T -e CAREERS_DB_TEST=1 workbee python -m unittest discover -s tests -q
```

See [technical details](docs/workbee-technical.md),
[professional bee logo notes](docs/workbee-logo.md), and the
[active PR](https://github.com/emmanguyen1/workBee/pull/2).

The unrelated trading demo has its own repository:
[Kalshi Demo](https://github.com/emmanguyen1/kalshi-demo).
workBee serves none of its pages or APIs. Public deployment is a separate step.


## Lower-battery local use

Keep only the website and Postgres running when you are not collecting new data:

```sh
docker compose stop careers-queen redis-bridge redis
docker compose up -d --no-deps workbee
```

This pauses live feed collection; current-only results age out after 30 minutes.
Profiles, notes and saved applications remain available. Resume collection when
needed with `docker compose up -d careers-queen`. The web app does not need Redis.
