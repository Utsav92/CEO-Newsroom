# Security and verification

No application can be guaranteed unhackable. The local and hosted applications have security controls and verification, but have not undergone an independent penetration test.

## Protections implemented

- The standard Windows launcher binds only to 127.0.0.1, limits concurrent requests and omits the server-version header. Unknown hosts and remote plain HTTP are rejected.
- Passwords use salted scrypt (N=2^17, r=8, p=1). Only hashes of session tokens are stored. Password replacement rotates the current session and revokes other sessions, including protection against a concurrent old-password login.
- Sessions expire after seven days absolutely or 30 minutes without API activity. At most five sessions remain active per account. Browser background requests count as activity.
- Session cookies are HttpOnly and SameSite=Lax; HTTPS sessions also use Secure. CSRF cookies are HttpOnly, SameSite=Strict and Secure under HTTPS. Signed, expiring CSRF tokens are bound to the login cookie and cannot be substituted between sessions. A bearer token does not bypass CSRF in account mode.
- Remote self-registration is disabled by default. Local creation remains available. The first owner must register from a loopback client. NEWSROOM_ALLOW_REMOTE_REGISTRATION=true explicitly opts into remote registration after owner setup; this requires further public-deployment controls.
- Account records, conversations, saved articles, payment data and audio grants are scoped by account. Only the owner can manually refresh shared news/YouTube sources. Existing public reporting and briefing snapshots remain shared content.
- CSP limits scripts to this origin, blocks framing and objects, and allows the existing YouTube embeds. Inline styles remain allowed for the existing animation/UI system. Additional headers restrict browser permissions, MIME sniffing, cross-origin resource use and referrers. HTTPS responses include HSTS. API and account-shell responses use no-store.
- API bodies are bounded to 128 KiB, or 1 MB for Stripe webhooks, including streamed/chunked bodies. Body reading has a 15-second timeout. Request, write, authentication, AI and billing controls limit abuse; rate storage is bounded. Local rate limits assume one worker; hosted instances share PostgreSQL-backed limits. These controls do not replace edge DDoS protection.
- Source fetching rechecks an outbound domain allowlist on redirects and metadata requests. Arbitrary/private-address URLs are blocked. This is not a substitute for outbound network policy or protection against compromise of an approved publisher/DNS.
- Stripe amounts and monthly recurrence are server-controlled. Customer/account ownership, paid invoice status, price and quantity are verified before membership activation. Webhook signatures, timestamp tolerance and duplicate event handling protect the callback. Test/restricted-test keys are identified correctly; both live-key types require HTTPS.
- Unhandled request errors return an opaque reference and log only that reference and exception type, rather than request bodies or credentials. API documentation/schema endpoints are disabled.
- Secrets and local data are excluded from the source archive. Docker is configured with a fixed non-root user, read-only root filesystem, writable data volume, dropped capabilities and no privilege escalation.

## Verification on 19 October 2026

191 backend tests pass, including CSRF substitution/expiry, cross-site requests, body limits, forged forwarding headers, HTTPS cookies, idle expiry, registration restrictions, audio isolation, owner permissions, rate bounds and safe errors. The cloud ingress tests also cover authenticated proxy login/logout, secure cookies, canonical origin, direct-backend denial, visitor IP validation and public readiness probes. Existing payment and account-isolation tests remain passing.

The npm dependency-tree audit reports no known vulnerabilities. The installed 30-package Python application runtime closure was checked with pip-audit and reports no known vulnerabilities. These results describe the advisory databases and versions checked, not proof that unknown vulnerabilities do not exist. Reports are retained locally under ignored output/.

Docker configuration was inspected; the container was not built or run. PostgreSQL and public TLS deployment were not exercised at this local-only checkpoint; the 20 October verification below covers the hosted deployment. A third-party penetration test was not performed. MFA, email verification and password recovery are not implemented. The operating system, reverse proxy, DNS, provider accounts and backup access require their own security controls.

## Operating a separate local-server deployment

Keep local binding until TLS and a correctly configured trusted reverse proxy are in place. Trust forwarded headers only from that proxy. Add account verification/recovery, MFA, provider-spend quotas, shared rate limiting for multiple workers, operational monitoring and an external assessment before opening general registration. Do not expose development servers or copy .env.local into frontend builds.

The Docker user is UID/GID 10001. Existing data volumes created by an older root-based container need ownership corrected during a controlled migration before using this image; back up the volume first. The app will not automatically change host filesystem permissions.

Guidance used: [OWASP HTTP headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html) and [CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
## Native Vercel deployment â€” 20 October 2026

The live app uses Vercel Functions and a connected Neon free PostgreSQL database.
Schema version 6 persists private narration, distributed job leases and bounded
security windows. A stable server-only CSRF key works across instances; HTTPS
cookies, account/audio isolation and exact-origin checks remain active. Native
Cron routes require a separate secret. Remote self-registration remains closed.

199 backend tests and 13 frontend checks pass. Live staging verification covered
login/logout, closed registration, account isolation, saved articles, official
YouTube uploads, a researched 4,313-character CEO explanation with follow-ups,
saved chat retrieval and private narration. Existing account hashes and history
were verified during an atomic migration; local active sessions were not copied.
Production-domain access uses the app's sign-in screen while Vercel Standard
Protection retains its preview/unique-deployment access checks.

The Gemini credential and configured video model both returned HTTP 200 to
read-only service-access checks. A complete live video-analysis request was not
part of this deployment check. Stripe remains disconnected until its webhook
secret is verified. No paid hosting plan was purchased. Operational MFA/recovery,
spend quotas, backup policies and external assessment remain separate work. See
[native deployment](docs/vercel.md).

## Optional external-proxy mode (unused by the hosted app)

The Vercel deployment preparation adds an authenticated ingress mode using
`NEWSROOM_PROXY_SECRET`, a configured canonical HTTPS origin, and Vercel's
overwritten visitor IP header. Direct backend app access fails closed; only a
minimal database readiness probe is public. The local mode remains unchanged
when this secret is absent. This path has local tests and an official-schema
configuration check, but has not been verified on the hosting providers. See
`docs/vercel.md` for setup, storage, cost and verification requirements.
