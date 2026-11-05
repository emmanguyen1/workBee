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

## Assistant modes

**Search guide (available without a key):** read-only local feature help and public
catalog search. It can translate straightforward field/internship/pay/workplace
questions into filters and show up to three employer links. This mode is explicitly
labelled; it is not presented as model-generated AI. Results are a bounded sample,
so no matches does not imply no jobs exist. Paused collection can yield no recent rows.

**Bee AI (optional):** a server-side OpenAI Responses integration. Questions, up to
four recent chat turns, product help and up to three selected public posting
excerpts are sent to the provider. Saved profiles, raw resumes and private application
notes are never read or attached. Requests use `store:false`; workBee does not persist
chat, but this is not a claim of zero provider retention. Output is plain text;
clickable source links come only from retrieved records. Bee has no account-writing,
application-submission, browsing or shell tools. Provider errors fall back to the
clearly labelled guide without exposing provider details or keys.

The local endpoint accepts questions up to 1,000 characters and history turns up to
1,500 characters, with at most four history turns. It requires same-origin requests
and limits a client to twelve questions per ten minutes. The bounded in-memory
limiter is intended for this local single-process app; public deployment needs
shared rate limiting and authenticated usage limits.

## Enable model-generated answers locally

Set `WORKBEE_OPENAI_API_KEY` in your local environment or private `.env` file.
Do not put a key into browser code, chat messages, the example file or GitHub.
`WORKBEE_AI_MODEL` defaults to `gpt-5-mini`; it must support Responses and low
reasoning effort. Then recreate only the web service:

```sh
docker compose up -d --no-deps workbee
```

Compose forwards only the named Bee key/model to the web container; other demo
credentials are not forwarded. The optional key can incur provider charges when
someone sends a question. The feature is tested with a mocked Responses transport;
live model access is not verified without a configured key.

The implementation follows the official [text-generation guide](https://developers.openai.com/api/docs/guides/text),
[conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state)
and [GPT-5 mini model reference](https://developers.openai.com/api/docs/models/gpt-5-mini).

## Battery use

Only workBee and Postgres need to remain running. New feeds and the community list
are imported once for this update; the collector, Redis and Redis bridge stay
stopped. Search/help does not restart them. Current-only entries age out after
thirty minutes without another successful collection. Bee has no idle polling or
background model requests.
