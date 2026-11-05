# workBee 🐝

Find internships, jobs, research opportunities, and first-/second-year programs
that fit your skills and goals.

<img src="hives/careers/static/workbee-logo.png" alt="workBee professional bee" width="112">

**Active development:** [PR #2](https://github.com/emmanguyen1/workBee/pull/2)
and branch `feat/hivepath-careers`. Check out that branch for the current app.

## Features

- Discover opportunities across software, science, marketing, finance, design,
  engineering, and more.
- Filter internships, jobs, and research by career stage, employer, country,
  state/province, workplace, and keywords. Field counts follow active filters.
- Compare skills and qualifications with posting excerpts, missing requirements,
  eligibility questions, and an explained skill-coverage score.
- Import PDF, DOCX, or text resumes and review drafts before applying them.
- Save profiles, preferences, programs, and application statuses in private accounts.
- Check source-feed availability; recognize employers through cached logos.

## First & second year programs — in the opportunity search

| Program | Audience and important distinction |
| --- | --- |
| NVIDIA Ignite | First-/second-year undergraduates; researched 2027 cycle is closed. |
| Microsoft Explore | First-/second-year overview; exact requisition eligibility varies. |
| Microsoft Discovery | Incoming freshmen, rather than continuing first-/second-year students. |
| Jane Street FTTP | First-year insight program; official page offers session notifications. |
| Jane Street FOCUS | First-year insight program with provider-defined access criteria. |
| NREIP | Research route requiring rising-sophomore standing; laboratory rules apply. |
| DOE SULI | Research route with semester, credit, GPA, age, and citizenship/residency rules. |

Choose **First & second year programs** in Opportunity type, or keep all
opportunities to see program guides alongside internships, jobs, and research.
Filter by class year, employer, field, country, and program status in the same
search. Save programs, review preparation steps, and export published deadlines
to a calendar from their details. Result counts distinguish job listings from
program guides, including closed cycles and notification-only pages.
Official sources were reviewed November 5, 2026. Open-window labels expire after
30 days without a new review; passed deadlines close automatically.

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
collector runs. Add employers in `hives/careers/employers.yml`.
Manually reviewed programs live in `hives/careers/programs.yml`.

This is a curated catalog, not every available position. Feed-listed does not
prove an application form accepts submissions. Failed checks mean unknown, not
closed; community listings require employer confirmation. Remote does not mean
worldwide. Unclear city-only locations remain unspecified. State/province parsing
covers the US and Canada; country filters use explicit feed evidence.

## Matching and accounts

Matching is rule-based coverage, not a hiring probability or complete eligibility
decision. Unknowns stay explicit; class-year filters show wording from the posting.
Raw resume files are not persisted or sent to an AI provider. Review extraction
drafts before use. Guest data can stay in browser storage; account profiles,
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
