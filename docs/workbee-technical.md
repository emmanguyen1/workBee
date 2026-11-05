# workBee

## workBee — internships, jobs & research

workBee is an independent careers website, with its own FastAPI application
(`hives.careers.app:app`) and Docker service. Open <http://localhost:8001/>.
The Kalshi dashboard remains a separate website at <http://localhost:8000/>.
Neither website serves the other's pages or APIs, and neither links to the other.
They share the underlying framework and Postgres infrastructure in this repository;
existing careers accounts, profiles, and application statuses are preserved.

workBee collects
public Greenhouse, Lever, and Ashby employer feeds every 15 minutes. No job API
keys are required. Configure employers in `hives/careers/employers.yml`; these are
individual employer boards, not a global search of all jobs. The initial directory
now includes 22 employers across technology, financial services, aerospace,
autonomous vehicles, healthcare technology, and nonprofit work.

Search across 14 inferred career fields, including marketing, finance, design,
HR, legal, operations, science, hardware, software, and customer-facing work.
The web discovery view starts with all career levels. Choose Internships, Jobs,
or Research & fellowships as the opportunity type, then narrow the career stage
to early career, new graduate, junior, or apprenticeship as needed. Research
internships appear under both Internships and Research. The API retains its
early-career default for existing clients. Career stages rely on explicit title signals: an "associate" title alone
does not prove a role is entry level. Fields are title/department heuristics and
can be imperfect.

Combine field, employer, country, state/province, and workplace filters.
Country and region dropdowns use explicit feed country codes, country names,
US states and Canadian provinces. Cities remain displayed on cards but are not
search-filter choices. Ambiguous city-only locations remain unspecified; remote
listings are not assumed to be worldwide. Choose "Country not specified" to find
listings lacking reliable country metadata. Changing country clears the state
selection. Previous saved city searches are no longer applied by the web form.
 Locations include
secondary offices supplied by the employer; country information is used when
explicitly supplied. Common location aliases (NYC, UK, USA) are recognized, but
the app does not infer countries for city-only listings or treat remote roles as
worldwide. An unspecified workplace is kept separate from on-site roles.
"Recently discovered" sorts by first observation in this database, not the
employer publication date. Hero coverage counters describe the stored catalog, including potentially stale
snapshots. Career-field counts respect the current query, career stage,
opportunity type, location, employer, workplace, and comparable-requirements
filter; each field count excludes only the field selection itself. Search and
filter changes refresh the results automatically. Obvious talent-network and
general-interest posts are excluded from discovery counts.

Start with the existing local `.env` and `docker compose up --build`, then open
<http://localhost:8001/>. Kalshi remains at <http://localhost:8000/kalshi>.
The first collection may take
a minute. Redis and Postgres are private Docker services. The queen creates the
careers tables automatically. For a single collection inside the running stack:

```bash
docker compose exec careers-queen python -m hives.careers.collector
```

Opportunities use a light card layout with company branding, location, career
stage, skill coverage, application tracking, and a detailed requirements dialog.
Known employers use locally cached logo PNGs when available (50 cached logos);
additional known domains fall back to Google's favicon service, then company
initials. Domain aliases tolerate common company suffixes. No logo API key is
needed. The header and favicon use a generated professional bee in a blazer; see
[logo notes](workbee-logo.md) for the prompt and asset path.

First-/second-year program guides are integrated into the main opportunity
search. The web client requests `include_programs: true`; API clients can opt in
or select `opportunity_type: program`. Guides and feed listings share employer,
field, geography, class-year, and search-text filtering. Counts distinguish job
listings from program guides. This includes seven researched routes, with
manual status labels and official links, while preserving anonymous API defaults.
Programs can be saved with existing application tracking; published deadlines
can be exported as calendar files. Account preference saving includes class-year
and program-status selections. Guides do not receive fabricated skill scores.

Application windows, closed cycles, notification signups, and pages needing an
individual requisition check have separate labels. Open-window labels require
research within the last 30 days; deadlines automatically close expired cycles.
The current researched NVIDIA 2027 cycle is closed. NREIP and SULI have published
2027 application windows; no guarantee is made that an application portal accepts
submissions. Program sources were manually reviewed November 5, 2026 and need
ongoing editorial updates; they are not part of the 15-minute feed collector.

The live-job **Class-year wording** filter includes only internship descriptions
that explicitly mention first-/second-year students. Quotes appear in details.
It does not infer eligibility from company names, graduation years, or a general
program overview. Unknown wording remains visible without this filter.

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

Each card distinguishes recently listed employer roles, community discoveries,
stale snapshots, and failed source checks. Open details and choose "Check source
now" to check membership in the configured employer/community feed. Checks use
only configured public feeds, cache each board for 60 seconds, and save the
result for reloads. Results remain current for 30 minutes or until a newer
successful collector observation supersedes them. Removed listings lose their
Apply action; the collector removes them from discovery after its next successful
snapshot. A source failure never means a job is closed. Feed presence does not
prove that an application form still accepts submissions; community-list presence
never becomes employer verification. Arbitrary application URLs are not fetched.

The match details show required/preferred group counts, weighted points, missing
required skills, source excerpts, and supporting profile examples. Skills without
examples are explicitly marked self-reported. Eligibility checks remain separate
from the skill coverage score.

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

