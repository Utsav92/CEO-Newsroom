# Native Vercel deployment

The app runs as a native Python 3.12 FastAPI Function on Vercel, with the existing
React UI built by Vite. Its PostgreSQL database is the connected Neon **Free**
resource `ceo-newsroom-db`, provisioned through Vercel Marketplace in London.
Render is not used and no Render service was purchased.

Project: `ceo-newsroom` (`prj_ZSrFthcMq9Dc1wZPC23IOWM4zOtz`).
Canonical address: `https://ceo-newsroom.vercel.app`.
Deployment evidence and the final public verification result are stored in
ignored `output/vercel-deployment-status.json`.

## Runtime

- `app.py` exports the existing FastAPI app. `pyproject.toml` declares the pinned
  runtime dependencies. Vercel must run its default Python dependency install;
  the frontend's npm install belongs in the build command, not an override of
  the Python install command.
- Runtime database connections use the provisioned pooled URL, psycopg 3 and a
  small pre-pinged/recycled SQLAlchemy pool. Functions refuse ephemeral SQLite.
  `/tmp/newsroom` is disposable runtime scratch space, never the account store.
- Schema version 6 adds durable small narration objects, shared security buckets
  and distributed job leases. Narration remains behind account-specific audio
  grants and is capped below the Function response-size limit. It is not public
  object storage. The browser splits long narration into bounded tracks.
- Signed CSRF tokens use a stable server-only secret across instances. Account
  sessions remain hashed in the database, Secure, HttpOnly and expiring. Exact
  production and platform-supplied deployment origins are allowed; arbitrary
  forwarded hosts and cross-origin writes remain rejected.
- Rate windows and authentication throttles use transactional database locks;
  security storage is bounded to 8,192 buckets. Shared ingestion and YouTube
  refreshes use expiring leases instead of process-only locks. Checkout locks
  the membership row before creating an idempotent payment attempt.
- APScheduler stays available for the local Windows app. It is not started in
  Vercel Functions. Native protected Vercel Cron endpoints perform daily news
  and YouTube updates. The free platform's daily scheduling has an approximate
  hour window; it does not provide the local server's 30-minute ingestion loop
  or exact custom briefing-time execution. Briefings are also generated when
  viewed. No push-notification delivery service has been provisioned.

## Credentials and billing

The connected database injects its environment variables into this project.
Authorized existing OpenAI, YouTube and Gemini credentials were copied only to
server-side Vercel Secrets. `NEWSROOM_CSRF_SECRET` and `CRON_SECRET` were generated
locally and stored as Secrets. No provider key is a browser variable. Local env
files, database snapshots, SQL parameter exports, cookies and QA credentials are
excluded from deployment and the source archive.

Neon uses its selected free plan. Vercel and AI-provider usage remains subject to
the user's own account limits. No paid hosting upgrade was authorized or made.
Stripe was intentionally not activated: its verified signing secret is still
missing. A configured Gemini credential also needs valid service access; key
presence alone does not establish video-understanding availability.

Remote registration remains disabled. The migrated owner can sign in with the
existing local account credentials. Passwords were not reset. New account
onboarding, MFA, account recovery and public paid-tier quotas remain separate
product work.

## Migration and verification

The original local server and database were retained. The SQLite backup API made
a consistent snapshot before transfer. The migration was tested atomically in
an isolated PostgreSQL schema, verified by table counts, and then applied to the
empty production schema. No stale joins were discarded. The imported snapshot
contains 421 articles, 18 conversations, 82 messages, one owner account, 399
official videos and its cached narration. Active local login sessions were not
copied; sign in again on the hosted app.

Local TCP connections to Neon timed out. The one-off migration used the official
`@neondatabase/serverless@1.2.0` HTTPS driver with bound parameters. Vercel's live
Python Function successfully uses PostgreSQL directly. Private migration plans
and parameter values stay under ignored `output/`; never upload that directory.

Reports: `output/vercel-migration-check.json`, `output/vercel-migration.json`,
`output/vercel-staged-verification.json`, and the final deployment status report.
The temporary deployment QA account and its private test data are removed after
verification. Local tests include 199 backend checks and 13 frontend checks.

## Updating this app

CEO-Newsroom has its own Git repository, separate from the unrelated parent
workspace. Its GitHub source is `Utsav92/CEO-Newsroom`. Do not deploy the parent
repository's metadata or publish its other apps. `scripts/export_vercel_source.py`
can still export only this app to an isolated temporary directory, retaining its
existing Vercel project link and excluding local data, secrets and dependencies.
Deploy that source snapshot to the same project. Pushing the GitHub repository
alone does not configure Vercel Git integration or change the live deployment.

Use the installed, reviewed Vercel CLI 64.7.0. Stage a production build with
`deploy --prod --skip-domain`, verify it using `vercel curl`, then promote the
tested deployment. Keep Vercel Standard Protection on previews and unique
deployment URLs while allowing the production domain to serve the app's own
sign-in screen. The app's authentication still protects private APIs.

For a fresh environment, provision and accept the free database integration,
configure Secrets, and migrate an empty target before deployment. The migration
tools refuse to replace an already populated cloud schema. Use a direct database
connection for schema work and the pooled connection for application requests.
For another migration using HTTPS, install the official helper dependency under
ignored `output/cloud-tools` before running `prepare_http_migration.py` and
`run_http_migration.mjs`; review the private generated plan first.

## References

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Neon and SQLAlchemy](https://neon.com/docs/guides/sqlalchemy)
- [Vercel Cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing)
