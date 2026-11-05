# workBee: explore broadly, act deliberately

This expansion lives on `feat/workbee-beyond-tech`, based on the existing workBee
feature branch. It broadens the default website beyond technical professions;
the legacy `technical_only` API option remains available for existing clients.

## Research and source choices

Public-board probes on November 5, 2026 returned successful responses for these
additional feeds. Counts describe the probe, not guaranteed application acceptance
or permanent availability. Current-only search still requires a recent successful
employer-feed observation and excludes removed/stale rows and expired explicit
deadlines. Source failures preserve the last successful snapshot.

| Employer | Practical coverage | Public Greenhouse board | Probe rows | Official context |
| --- | --- | --- | ---: | --- |
| American Public Health Association | Public health, policy, communications internships | americanpublichealthassociation | 13 | [Example public-health internship](https://job-boards.greenhouse.io/americanpublichealthassociation/jobs/4434205009) |
| ACLU | Legal, advocacy, communications, and operational roles | aclu / acluinternships | 18 / 61 | [Internships](https://www.aclu.org/careers/internships/) |
| Human Rights Watch | Advocacy, outreach, fundraising and international careers | humanrightswatch | 5 | [Careers](https://www.hrw.org/careers) |
| Vera Institute of Justice | Justice policy, research and nonprofit operations | verainstituteofjustice | 8 | [Careers](https://www.vera.org/careers) |
| Achievement First | Education, teaching and school operations | achievementfirst | 112 | [Careers](https://www.achievementfirst.org/careers/) |
| AlphaSights | Business, client services, graduate and internship paths | alphasights | 65 | [Students and interns](https://www.alphasights.com/careers/students-and-interns/) |

These seven feeds add six employers. Existing health employers now expose their
nontechnical roles as well. Existing research, lab, aerospace and software feeds
remain available. Summer Associate and explicitly titled Placement openings are
recognized as internships; a generic Associate title alone is not enough.

APHA's example explicitly describes unpaid internships. ACLU describes stipends
and AlphaSights describes internship/placement pathways. These differences make
pay and commitment evidence useful; a program overview is not ingested as a live
opening. WRI and several other researched organizations use unsupported or moved
boards; they were not added as unverified feeds. A future Workday integration
would broaden universities, hospitals and climate organizations.

## Features built from applicant needs

- **Find work, not just an industry.** Career field (e.g. finance, education,
  marketing, healthcare, science) and employer industry are independent,
  alphabetically ordered multi-selects. A marketing applicant can find roles at
  healthcare employers. Previous saved industry selections are preserved; clearing
  filters opens the broader catalog.
- **Check practical constraints early.** Paid/unpaid/amount-disclosed filters use
  explicit wording. Benefits, research budgets and missing pay do not imply paid
  work. Contradictory evidence stays unknown. Part-time/full-time/fixed-term filters
  reflect wording in the posting, not guaranteed schedules. Date filters select
  recently published/first-seen roles and explicit deadlines within 7 or 30 days.
  Counts respect these filters. “Most recent” has the same publication/first-seen
  fallback as before; indexing an older feed does not prove a new publication.
- **Choose between options.** An in-tab shortlist compares up to three opportunities
  across pay wording, commitment, location, workplace, closing date and skill
  coverage. Comparison is temporary and cleared when the saved account/profile
  changes; save application stages to keep a role across visits.
- **Remember what to do next.** Signed-in applicants can add private notes, a next
  action and a personal follow-up date to each saved role. An agenda shows dated
  actions and overdue items. These dates are personal reminders, separate from
  employer deadlines. No background/email notification is promised.
- **Keep ownership of your tracker.** Download saved application records as CSV,
  including notes, stages, dates and source links. CSV quoting handles multiline
  notes and neutralizes spreadsheet formula prefixes. Unsaved edits are not exported.
- **Match beyond software.** Resume and posting vocabulary includes policy analysis,
  qualitative research, teaching, classroom management, clinical research, patient
  care, outreach, grant writing and other skills. Coverage remains an explained
  checklist, never a license/credential check or hiring prediction. Unknown posting
  requirements remain visible unless the user selects comparable-only.

## Branding

The professional bee stays the primary mark. Warm honey accents, a restrained
hexagon detail, a small bee alongside the introduction, and calm, purposeful copy
make the site recognizable while retaining the navy/grey palette. There are no
animated backgrounds or new external image services. Mobile layouts retain the
existing responsive breakpoints and stack comparisons vertically.

## Account implementation

`application_details` is an additive JSONB column; existing accounts, passwords,
profiles, preferences and stages are preserved. `/api/account/application-details/{id}`
requires a same-origin authenticated request and a role already saved by that user.
Updates lock the account row, check the per-role revision and reject stale writes
with 409. Notes are capped at 3,000 characters; dates must be valid ISO dates.
Deleting an application status also deletes its notes. Private responses remain
`Cache-Control: no-store`. Notes are returned only with the user's own saved roles,
not in search responses or cross-tab broadcast messages. In-memory unsaved note
drafts survive stage filtering/refresh for the same account, but not a page reload.

Current-only database reads exclude stale/community rows before loading descriptions.
Decision facts are extracted for the result page or active practical filters, and
new snapshots store the public facts to avoid repeated parsing.

Public requirement snapshots move to version 5; `python -m hives.careers.reindex`
upgrades only public analysis with unchanged-description guards. It never updates
availability timestamps or private account profiles.

## Next useful work

1. Add verified university/hospital/Workday feeds with source-health reporting.
2. Add opt-in saved-search digests after email verification, delivery and unsubscribe
   handling exist; do not simulate alerts with an account-only date field.
3. Add per-role document checklists and reviewed writing-sample/portfolio reminders.
4. Add more conservative credential/subject-area checks with visible source quotes,
   particularly for regulated healthcare and teaching roles.
