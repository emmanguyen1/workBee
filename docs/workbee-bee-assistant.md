> Updated freshness and refresh behavior: the website now keeps last-known-open
> listings for seven days with recheck labels and offers explicit manual refresh.
> See [performance and refresh details](workbee-performance-refresh.md).

# Bee assistant and broader Simplify discovery

The former hero bee callout has been removed. The bottom-right **Ask Bee** launcher
uses a new waving pose of the same professional bee, navy blazer, white shirt and
tablet. The original header logo remains unchanged. Generated artwork is local;
no remote image or idle animation service is needed. The panel works on discovery
and account pages, supports Escape/close, source links and explicit search-filter
shortcuts. It makes no requests until opened or used, and keeps chat only in the tab.

## More employers from the supplied source

The [Pitt CSC / Simplify Summer 2027 list](https://github.com/SimplifyJobs/Summer2027-Internships)
was checked on November 5, 2026. Its public JSON snapshot contained 2,452 active,
visible Summer 2027 rows. Application URLs identified the following additional
public employer boards; each board was independently checked successfully before
configuration. Raw community counts and employer-board counts are different and
are deduplicated by application URL where possible.

| Employer | Adapter | Board | Public board probe rows |
| --- | --- | --- | ---: |
| Bedrock Robotics | Ashby | bedrock-robotics | 59 |
| Skydio | Ashby | skydio | 196 |
| DV Trading | Greenhouse | dvtrading | 73 |
| Graphcore | Greenhouse | graphcore-early-careers | 32 |
| Virtu Financial | Greenhouse | virtu | 47 |
| Verkada | Greenhouse | verkada | 340 |
| Toyota Research Institute | Lever | tri | 30 |
| Akuna Capital | Greenhouse | akunacapitaloci | 17 |
| CesiumAstro | Lever | CesiumAstro | 350 |
| Muon Space | Greenhouse | muonspace | 141 |
| Sigma Computing | Greenhouse | sigmacomputing | 79 |

Board rows include the employer's other open professions as well as internships;
not all 1,364 probe rows are internships. Sources and availability vary over time.
No API key is needed for public job feeds.

**Include Simplify discoveries** is an optional saved preference. Default search
still requires recent employer-feed evidence. Opting in adds only recently observed
community entries, clearly labelled as employer-unverified; missing descriptions
and qualifications stay unknown. Removed, stale, and explicitly expired entries
remain excluded. A matching employer listing takes precedence, with community
attribution retained. Filter totals include community rows only when opted in.

## Questions, coaching and outside resources

Bee separates workBee help, catalog searches, career advice and general questions.
It can explain concepts, help draft application materials, plan learning, practice
interviews, and discuss questions beyond job discovery when AI is enabled. It no
longer searches for random jobs in response to every question. Simple follow-ups
such as “What about remote?” retain the preceding search area. Search shortcuts
remain explicit: Bee does not change filters until the user chooses the shortcut.

**Resource guide (no key required):** practical starting advice for resumes,
interviews, learning plans and research outreach, plus relevant curated links to
NSF, NIH, MIT career guidance and CareerOneStop. Directories are clearly labelled
as resource starting points, not confirmed open postings. Arbitrary questions
receive an honest explanation of the local guide's limits. Opportunity searches
still return a bounded sample of up to three public employer listings.

**Bee AI (optional):** server-side OpenAI Responses integration for open-ended
answers. With **Search the web when useful** enabled, Bee can use the hosted
`web_search` tool for current information and outside resources. It prefers primary
sources and distinguishes web findings from cached catalog evidence. The switch
can be disabled for an answer without live web research. Product-help responses
never need the web tool.

Citations come from provider `url_citation` annotations, not URLs invented in answer
text. The UI renders prominent clickable inline citations and a web-source list,
using text nodes and validated HTTPS links. Curated resources appear separately;
their presence does not mean they were searched live. The response states whether
web search actually ran. HTML is not executed, and links with embedded credentials
or unsafe schemes are rejected. Clear chat discards the tab's recent conversation
and cancels its pending request.

## Privacy, limits and fallback

Questions, up to four recent chat turns, product help and selected public posting
excerpts are sent to OpenAI in AI mode. Search queries may also be sent to search
providers when web search is enabled. Saved profiles, resumes and private notes
are never automatically read or attached. Anything the user types into chat is
part of the message sent to the provider; avoid pasting sensitive data.
Requests use `store:false`; workBee does not persist chat. This is not a claim
of zero provider retention. Bee has no account-writing, application-submission,
email, file-upload or shell tools, and does not guarantee eligibility or hiring.

A request permits at most two hosted tool calls, uses a 55-second HTTP timeout,
and has bounded answer tokens. The UI permits 75 seconds for the complete request.
Provider errors fall back to the clearly labelled local guide without exposing
provider internals or keys. No web-search claim or fabricated citation is added
to a fallback answer.

The endpoint accepts questions up to 1,000 characters and at most four 1,500-character
history turns. It requires same-origin requests and limits a client to twelve
questions per ten minutes. This bounded in-memory limiter is for the local
single-process app; public deployment needs shared limits and authenticated usage
controls. There are no idle AI calls or background research jobs.

## Enable AI and live research locally

Set `WORKBEE_OPENAI_API_KEY` in your private local `.env` file. Keep it out of chat,
browser code and GitHub. `WORKBEE_AI_MODEL` defaults to `gpt-5-mini`; a custom
model must support Responses, low reasoning effort, and hosted web search.
Then recreate only workBee:

```sh
docker compose up -d --no-deps --build workbee
```

No separate search-provider API key is needed: hosted web search uses the same
OpenAI API account. Model tokens and web-search tool calls can incur charges.
Check `/api/bee/status` or open Ask Bee to see whether AI is configured. Boolean
readiness is exposed; key values remain server-side. The integration is covered
by mocked provider tests. Live AI/web quality cannot be verified until a valid key
is configured; the current local deployment is in resource-guide mode.

Implementation follows official [OpenAI web-search and citation documentation](https://developers.openai.com/api/docs/guides/tools-web-search)
and the [GPT-5 mini model reference](https://developers.openai.com/api/docs/models/gpt-5-mini).
Curated starting points include [NSF undergraduate research guidance](https://www.nsf.gov/funding/initiatives/reu/students)
and the [NIH Summer Internship Program guide](https://www.training.nih.gov/research-training/pb/sip/).

## Battery use

Only workBee and Postgres need to remain running. Bee never starts the collector,
Redis or Redis bridge. Source checks older than thirty minutes need rechecking;
last-known-open listings remain visible for seven days. Bee makes requests only
when opened or asked a question; it has no idle polling or background model calls.
