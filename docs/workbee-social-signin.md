# Google and LinkedIn sign-in

workBee supports username/password accounts and optional provider sign-in on
`/account`. New provider users get a workBee profile automatically. Returning
users are identified by the provider's stable subject ID, not their email address.

## Connect an existing profile

If you already use a workBee username, sign in with it first. Save any profile
changes, then use **Sign-in methods → Connect Google / LinkedIn**. This attaches
the provider to the same profile, preferences, notes and applications. Linking
does not overwrite your display name or saved data. A provider identity already
attached to another workBee account is rejected; accounts are not silently merged
by matching email. Connecting a different identity from an already-connected
provider requires disconnecting the existing one first.

The settings show connected methods and allow disconnection. A provider-only
account cannot remove its final sign-in method. Local username/password sign-in
remains available for existing password accounts. Provider-only accounts do not
receive an invented/shared password. Password recovery is still not implemented.

## Server configuration

Create your own provider application, then put its credentials in the private
local `.env` file or environment. Do not paste secrets into chat, browser code,
GitHub, or the example file.

```dotenv
WORKBEE_PUBLIC_URL=http://localhost:8001
WORKBEE_GOOGLE_CLIENT_ID=your-google-web-client-id
WORKBEE_GOOGLE_CLIENT_SECRET=your-google-web-client-secret
WORKBEE_LINKEDIN_CLIENT_ID=your-linkedin-client-id
WORKBEE_LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
```

Either provider can be enabled independently. A provider with missing credentials
is visibly disabled, with username sign-in kept available. This distinguishes
implementation support from a live provider connection; real sign-in requires
registered credentials and an authorized redirect URL.

### Google

Create a web OAuth client in your Google Cloud project, configure its consent
screen for workBee, and register this exact callback for the local origin:

`http://localhost:8001/api/account/oauth/google/callback`

Use a test account allowed by your consent-screen configuration while the app is
in testing. See Google's official [OpenID Connect setup](https://developers.google.com/identity/openid-connect/openid-connect).

### LinkedIn

Create an application in LinkedIn's developer portal and request/enable the
**Sign In with LinkedIn using OpenID Connect** product. Register the exact callback:

`http://localhost:8001/api/account/oauth/linkedin/callback`

If your provider configuration requires a public HTTPS origin, use that origin
for `WORKBEE_PUBLIC_URL`, register the corresponding HTTPS callback, and access
workBee through that origin. A local test transport is not evidence that an app
has provider access/approval. See LinkedIn's official [OIDC guide](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2)
and [authorization-code flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow).

Recreate just the web container after setting credentials:

```sh
docker compose up -d --no-deps workbee
```

Only named workBee provider variables are forwarded. The collector, Redis and
Redis bridge do not need to run. `WORKBEE_PUBLIC_URL` must be a root HTTPS origin
outside loopback; the authorization start must use the configured origin rather
than an arbitrary Host-derived redirect URI.

## Authentication boundaries

- The web server starts the provider redirect and performs code exchange with its
  client secret. Provider passwords are handled by Google/LinkedIn, never workBee.
- Browser-bound random state is single-use and expires after ten minutes. Its
  browser binding is an HttpOnly, SameSite cookie; only hashes are stored for
  state/browser/nonce values. Expired pending flows are cleaned on the next start.
- Google uses S256 PKCE and validates the requested nonce. LinkedIn uses its
  documented confidential web authorization-code flow, not its separate native
  PKCE endpoint. Both validate the signed ID token with PyJWT against fixed
  provider JWKS endpoints, RS256, issuer, audience, subject, issue/expiry times and
  authorized-party/access-token bindings when present.
- JWT-supplied key URLs are ignored. Public signing-key documents are cached;
  provider tokens are not retained after the login request.
- Only the stable provider subject and an initial display name are used. Email
  matching never links accounts. Optional missing email claims are supported.
- Linking requires the same existing workBee session at both start and callback;
  logout/session changes abort it. Provider/account uniqueness and database locks
  protect against conflicting account attachments.
- Successful authentication creates the existing opaque HttpOnly workBee session;
  session cookies are Secure for HTTPS deployments. Provider identity tables are
  additive and do not rewrite passwords/profiles/preferences.
- Callback redirects contain fixed result codes rather than raw provider errors
  or user-controlled destinations. workBee access logs are disabled so callback
  authorization codes are not logged in URL query strings. Reverse-proxy logging
  should follow the same policy when deploying behind one.

Provider sign-in confirms control of a provider account; it is not a verified
professional credential or a claim of identity verification.

## Simplified opportunity controls

Pay, deadline-window and recency controls are removed from the search sidebar and
account preferences. Legacy saved values for those controls are ignored by the
website, so they cannot silently constrain the search. Compatible backend API
filters remain available. Time commitment remains.

Sort is at the top-right of the opportunities heading on the search page; the
account page keeps it as an explicit saved search preference. Each card displays
its application deadline or **Not published**, with cutoff/timezone context.
Existing pay facts stay on individual cards when supplied by the posting.

## Validation

Provider transport tests use signed test JWTs and mocked HTTPS responses. Database
lifecycle tests use isolated temporary schemas and cover returning sign-in,
existing-account linking, preservation of saved profiles, email collision/rejected
links, state/browser binding, replay/expiry/nonce rejection, logout during linking
and last-method protection. Live provider authorization requires real app
credentials and has not been verified on the unconfigured demo.
