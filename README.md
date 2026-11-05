# workBee 🐝

Find current technical internships, jobs, research opportunities, and first-/second-year postings
that fit your skills and goals.

<img src="hives/careers/static/workbee-logo.png" alt="workBee professional bee" width="112">

**Active development:** [PR #2](https://github.com/emmanguyen1/workBee/pull/2)
and branch `feat/hivepath-careers`. Check out that branch for the current app.

## Features

- Discover **technical professions across industries**: Health IT, Aerospace,
  FinTech, Business Systems, Cybersecurity, Cloud/Data Infrastructure, AI/Robotics,
  Mobility, Bioinformatics, EdTech, Energy Technology, and more.
- General clinical, recruiting, sales, and administrative jobs are excluded.
  A tech employer alone does not make a role technical; titles or explicit
  technical-tool requirements must support the classification.
- Filter internships, jobs, and research by career stage, employer, country,
  state/province, workplace, and keywords. Select several options in each menu;
  results can match any selected option within a group. Field counts follow all
  other active filters, and selections can be saved to your account.
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
in a left filter sidebar, with keyword search above the results. A narrow category may have no current listings.
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
git switch feat/hivepath-careers
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
collector runs. Add employers in `hives/careers/employers.yml` (33 direct employers plus the
community archive source).
Manually reviewed program archives live in `hives/careers/programs.yml`.
Additional healthcare/business feeds include Oscar Health, Commure, Included
Health, Carta, Gusto, Brex, and Flexport. Aerospace coverage also includes
Rocket Lab and Astranis alongside SpaceX. Research and lab technology feeds include
Ai2, Recursion, Chan Zuckerberg Initiative, and Lila Sciences.

This is a curated catalog, not every available position. Feed-listed does not
prove an application form accepts submissions. Failed checks mean unknown, not
closed; community listings require employer confirmation. Remote does not mean
worldwide. Unclear city-only locations remain unspecified. State/province parsing
covers the US and Canada; country filters use explicit feed evidence.

## Matching and accounts

Matching is rule-based coverage, not a hiring probability or complete eligibility
decision. Unknowns stay explicit; class-year filters show wording from the posting.
Raw resume files are not persisted or sent to an AI provider. Review extraction
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
