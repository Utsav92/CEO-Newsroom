# Deployment

The hosted app is [ceo-newsroom.vercel.app](https://ceo-newsroom.vercel.app).
Vercel runs FastAPI and the built React UI, with a connected Neon free PostgreSQL
database and native daily Cron jobs. Render is not used. See
[native Vercel deployment](vercel.md) for migration evidence, server-only settings,
verification and platform limits.

## Local Windows and Docker

The local Windows target uses one FastAPI process and SQLite, with the compiled frontend served at the same origin. Keep the bind address `127.0.0.1` for local use. Docker provides the same app and exposes it only on the host loopback address by default.

For continuous briefings, keep the server running. The provided Docker service uses `restart: unless-stopped`. A Windows Task Scheduler job can run `scripts/run.ps1` after login if the owner chooses to configure it. No OS startup automation was installed.

Account login protects browser/API data; chats, saved articles, billing and preferences are scoped by account. Reporting, videos and briefing snapshots are shared server content. Before remote hosting, create the first account through localhost to claim existing history. Configure PUBLIC_APP_URL with the exact HTTPS origin and terminate TLS correctly. Public deployment still requires per-account provider quotas, shared task locking, monitoring, backups and any push notification service. NEWSROOM_ADMIN_TOKEN can authorize legacy script mutations but does not bypass account login. Never expose server credentials in browser configuration.

Back up `data/newsroom.db` and any cached audio while the server is stopped, or use SQLite's consistent backup API. A Docker named volume persists the same data. Native Vercel's PostgreSQL deployment was tested; the Docker configuration itself was inspected but not built or deployed.


The standard Windows launcher now suppresses the server header and caps concurrency at 64. Remote plain HTTP is rejected; configure TLS and trusted proxy forwarding explicitly before hosting remotely. Remote registration defaults off, and initial owner setup requires a loopback client. For Docker, initial owner setup must be performed through a loopback request inside the container before opening remote registration. Docker hardening uses UID/GID 10001, a read-only root filesystem, dropped capabilities and no-new-privileges; existing root-owned data volumes require a backed-up ownership migration. Docker configuration has not been executed here. See ../SECURITY.md.
