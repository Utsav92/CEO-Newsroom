# CEO Newsroom 3.0

An independently operated technology news group chat with eight AI-simulated presenters. Built with React, TypeScript, Vite, Tailwind, Motion, Lucide, FastAPI, SQLAlchemy, SQLite, HTTPX, Feedparser, and APScheduler. The supplied anime illustration is the only portrait source.

## Open the running app

Hosted app: **[ceo-newsroom.vercel.app](https://ceo-newsroom.vercel.app)**. Sign in with the existing account. Vercel runs the Python backend and React UI; the connected Neon free database preserves accounts and history. Render is not used. See [native deployment](docs/vercel.md).

Development preview: **http://127.0.0.1:5178/**. Built app and API: **http://127.0.0.1:8788/**. These URLs work while the local servers are running.

## Founder-style video introduction

[Watch the 45-second explainer](media/CEO-Newsroom-founder-intro.mp4) · [English subtitles](media/CEO-Newsroom-founder-intro.srt)

The clip uses first-person synthetic narration, branded product illustrations and captions to introduce article questions, company perspectives, official videos, saved articles and chat history. It is a founder-style demonstration, not a recording of the owner or a featured executive.

## Windows setup

Python 3.11+ and Node.js 20+ are required. No GPU is needed.

```powershell
cd 'C:\Users\Utsav\OneDrive\Documents\ea sports\CEO-Newsroom'
.\scripts\setup_windows.ps1 -Run
```

For subsequent starts, run `.\scripts\run.ps1`. This serves the built frontend and API together on port 8788. Stop with Ctrl+C. If another copy is already running, use that copy or stop it before starting another.

The server reads `.env.local`, then `.env`, then the existing parent workspace `.env.local`, without copying secrets. Environment variables take precedence. The existing OpenAI key was reused with permission. Credentials never enter the browser bundle.

For frontend development, start the backend using `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8788`, then run `npm run dev` inside `frontend`.

## What works

- Eight extracted portraits, circular profiles, and chat thumbnails, with company colors and disclosed simulations.
- Company questions show the corresponding CEO's small avatar thinking while sources are checked, then keep that CEO beside the cited answer. Comparisons show both presenters; failed requests clear the thinking state and preserve the question.
- Separate Article feed and Chats sections, plus company news, daily briefing, official-channel videos, Saved articles, and source status views.
- Conversations save automatically after each answer. Search Chat history, reopen article/video context and follow-ups, or start a New chat while keeping earlier conversations. Load older chats beyond the first 100.
- Use Back to articles to restore your feed filters and reading position. Answers can finish while you browse; Open chat takes you back. The feed checks for updates every minute and offers Show updates when new stories arrive, without refreshing the page or moving your current reading position. Server ingestion continues every 30 minutes.
- Tap an article’s 🤍 Like button to turn it into ❤️ Liked and save the original article link in Saved articles. Tap again to remove it. Likes persist with your account, including older saved articles outside the latest feed window. Saved articles has its own count, search and date/topic filters, and a reloadable `?view=saved` link.
- Live RSS/Atom ingestion, public announcement metadata, source availability checks, UTC publication dates, URL/title deduplication, and 30-minute refreshes.
- Multi-company entity routing plus embedding classification; unrelated reporting uses a neutral narrator.
- Embedding and lexical retrieval; OpenAI Responses API answers with database-validated article IDs, source URLs, and publication dates; comparison mode and persistent conversation history.
- Bounded grounded AI summaries, with remaining cards explicitly labeled as source excerpts. No invented sample news or fallback AI answers.
- Morning, evening, and weekly briefings; editable IANA timezone and schedule; DST-aware local time; company-specific briefing filters and history.
- Eight generic synthetic voice assignments, audio caching, play/pause/stop, speed selection, and optional playback after a Listen action.
- Explicit company/topic preferences, saved-story similarity recommendations, and optional in-browser notifications. Personalization and notifications are off by default.
- Single-user local authorization, same-origin mutation checks, bearer-token protection for remote API access, basic AI rate limiting, versioned initial database migration, and automated tests.

## Article questions and company perspectives

**Detailed answers by default:** substantive CEO questions normally receive about 450–700 words per company, with a direct answer, evidence, step-by-step mechanisms, benefits and trade-offs, limitations, and practical implications. General chats use five readable research sections; article and video chats develop What it means, How it works, and Likely impact in depth. Follow-ups focus on the new question rather than repeating the previous answer. Evidence gaps take precedence over a length target.

Live research uses the configured OpenAI key for two focused searches covering original documentation and independent evidence/limitations. Up to six tool-cited web sources from company, research, public-record, and established-news domains supplement collected reporting or actual video observations. Source links and research coverage are shown with each answer; permitted public source excerpts and AI source syntheses are labeled separately. A bounded set of tool-returned original pages is read directly where access rules permit; blocked or inaccessible pages are skipped. Identical research is cached in memory for 15 minutes. Turning off related reporting in an article/video chat restricts it to the selected material. A failed or unavailable live search is disclosed and the answer uses available evidence plus labeled general reasoning. Search and generation incur normal provider usage; there is no new key to configure. Long answers open at their beginning, and Listen includes the full explanation across consecutive audio tracks.

**Interactive CEO follow-ups:** each new chat, article or video answer includes one contextual question from its presenter, 2–3 quick replies, and 2–3 recommended questions under **Explore next**. Tap a reply or question to continue the same conversation, or type your own answer. The presenter uses your goal and constraints to move toward practical options and next steps, without repeating information already supplied. Shared-company answers have their own follow-ups for each company's perspective. Earlier questions remain readable; only the latest matching conversation/source offers active choices. Follow-ups persist with chat history, and Listen includes the CEO's question.

Questions can ask for judgment and predictions, such as **“Is this a problem?”** or **“What could happen next?”** The LLM combines reported background with general reasoning and labels its answer **Reasoned assessment**, **Prediction · uncertain**, or **General explanation**. Assumptions and unknown outcomes remain explicit. When no reporting is available, it can still explain general principles or conditional scenarios without claiming an event occurred. Source links support the reported background, not proof that a forecast will happen.

Short follow-ups retain the previous answer's actual article records, even when a fresh ranking or date filter would omit them. Old AI answers and their citation strings are not treated as evidence. Citation IDs are constrained to the current source list; invalid drafts are regenerated automatically, with a fresh conditional general assessment if citation repair fails. Provider/network failures can still require retry. Repeated retries of the same unanswered question reuse its existing chat bubble.

Choose **Ask this article** on a story, enter a topic, and choose whether to include relevant reporting for context. Publisher titles and permitted excerpts are split into passages with cached embeddings. The selected article remains the anchor across follow-ups; AI summaries are never used as source evidence.

Each relevant company's AI CEO gives a separate answer with **What it means**, **How it works**, and **Likely impact**. NVIDIA/OpenAI supply questions distinguish supplier demand from customer compute access; Anthropic/Google partnership questions distinguish each company's benefits, dependencies and risks. A company mention does not prove a partnership. Missing mechanisms are explicitly marked unavailable, and likely benefits are conditional assessments.

An independent model pass reviews company focus and grounding. Reported facts and source explanations cite validated passages. General reasoning and predictions can be uncited when clearly labeled and conditional. Drafts and reviews with invalid citations are repaired before display. Expand **View source passages** to inspect the evidence, or open the original article for the full report. Article focus and topic persist in the browser; **Clear selected article** or **New conversation** resets the scope. Listen narrates the direct answer and explanation sections.

Passages are indexed during ingestion and on demand. Backfill an existing collection with `python scripts/index_articles.py` using the authorized server key. The additive version-2 migration creates the passage table. Related context is bounded to at most three supporting articles, and the app only retains the permitted source excerpts, not full articles.

## Configuration and limits

**Video questions:** choose **Ask about this video** in Watch & learn or the video player. The server re-verifies public status and official channel ownership, then sends the public YouTube URL and your question to Gemini's supported Interactions API to understand actual speech and visuals. No video download or caption scraping is used. The resulting timestamped AI observations are embedded and retrieved as evidence; OpenAI prepares and independently reviews each relevant company's explanation. Supporting news is optional and labeled separately. Follow-up questions retain the selected video. The CEO avatar shows **Understanding video…** while analysis and explanation run; Listen reads the resulting answer with a generic AI voice.

Each video card and player offers **Chat with [CEO name]**, with that CEO’s avatar. It opens a video conversation in Chats, where you can ask about audio, visuals, demonstrations, or timestamps. **Continue with [CEO name]** resumes an existing saved conversation for that video; history labels these as **Video**. **Back to videos** returns to Watch & learn.

Configure server-only `GEMINI_API_KEY` and optional `GEMINI_VIDEO_MODEL` (default `gemini-3.5-flash-lite`) separately from `YOUTUBE_API_KEY`. The YouTube key supplies the official feed; the Gemini key must permit Generative Language API access and have quota. Restart after configuration changes. Video URLs and question context go to Google for analysis; structured explanations go to OpenAI. Google interactions set `store: false`. Exact repeated video questions reuse a bounded 24-hour in-memory analysis cache; a different question or follow-up context is analyzed again. Chat answers persist locally as before.

Analysis is an AI interpretation, not a verified transcript or a real CEO statement. Timestamp links are approximate, and fast visual changes or small slide text may be missed. Company claims, demonstrations, uncertainty and projected impacts remain qualified. Only public, completed, official uploads under three hours are supported. Provider, quota, access and incomplete-evidence failures withhold answers instead of falling back to titles/descriptions. Availability of YouTube URL processing is subject to Google's service. [Video understanding documentation](https://ai.google.dev/gemini-api/docs/video-understanding).

**YouTube:** the server reads `YOUTUBE_API_KEY` from ignored `.env.local`. Enable YouTube Data API v3 for its Google Cloud project. Only the eight curated official company handles are allowed. `channels.list` resolves each handle and pins its returned channel ID; `playlistItems.list` reads that channel's uploads, and `videos.list` confirms each video's owner, public status, publication date, and embed permission. Fan channels, third-party playlists, private/unlisted/deleted videos, and unverified legacy cache entries are excluded.

All companies refresh daily at **07:30 in the configured timezone** (Europe/London by default), with DST handling, startup catch-up, and on-access catch-up. The server must be running for the scheduled job; reopening catches up after downtime. The Watch & learn screen shows all companies or a selected company, searches cached titles/descriptions, offers an authorized manual refresh, and displays update times and per-channel status. Up to 50 latest uploads per channel are retained. Refresh failures preserve previously verified uploads, retry after 15 minutes, and show a warning. Metadata older than 30 days is removed. Videos that forbid embedding provide an official YouTube watch link.

Implementation references: [official upload retrieval](https://developers.google.com/youtube/v3/guides/implementation/videos), [channel handles](https://developers.google.com/youtube/v3/docs/channels/list), [public status and embedding](https://developers.google.com/youtube/v3/docs/videos).

Live verification retrieved 400 public uploads across all eight companies, with 50 per channel and no channel warnings. Each record's channel ID matches its verified company channel. Playback remains subject to YouTube's player, region and account restrictions.

**TLDR:** its accessible archive adapter is implemented, but this machine currently receives a TLS error from `tldr.tech`. It is marked unavailable and retried on later ingestions. No restrictions are bypassed and no TLDR stories are fabricated.

**Artwork:** the supplied RGB image contains a baked checkerboard. A background-connected neutral mask removes it. Faces and visible hair/clothing are preserved, but the original overlapping shoulders cannot be perfectly separated or reconstructed. See `assets/extraction-report.json`.

**Runtime:** schedules run while the server is running. Browser notifications require explicit permission and an open app. A closed browser receives no push/email notification. Briefings omit companies with no dated reporting for the selected period. Historical briefings are snapshots; reopening a briefing for today regenerates today's view.

**Accounts and settings:** create the first account on this computer to retain existing saved articles, preferences and chat history. Additional accounts have separate saved stories and conversations. Settings contains Account (including Sign out), Pricing, Language and Preferences. Sessions expire after seven days or 30 minutes without API activity, are capped at five per account, and are revoked on logout. Passwords use salted scrypt; session tokens are stored as hashes. Account settings supports display-name editing and changing your password with the current password; other sessions are revoked. Email verification and password reset are not implemented.

**Monthly memberships:** Silver **USD $2/month**, Gold **$3/month**, Platinum **$5/month**. Payment choices include Google Pay, Apple Pay, credit card, debit card, Mastercard, bank transfer and a QR code opening a real Stripe checkout page. Wallets depend on eligibility; transfers use monthly invoices. No tier quotas are assigned. Stripe activation is pending local credentials. See [Stripe setup](docs/payments.md). A return URL never activates membership: the server verifies a paid invoice/active subscription and signed webhooks. Open **Billing history & renewal** for owned payment attempts, paginated Stripe invoices and PDFs, billing dates, and confirmed end-of-period renewal cancellation/resumption.

**Language:** select one of 12 CEO answer languages at registration or in Settings. New answers and their follow-up questions use that choice. The interface, publisher reporting and existing answers retain their original language.

**Deployment:** the hosted app uses native Vercel Functions, a connected Neon free PostgreSQL database, shared security limits/job leases and native daily Cron endpoints. The Windows version retains SQLite and its single-process scheduler. Account login protects private APIs. Remote registration remains closed; the migrated owner signs in with the original credentials. Stripe activation still needs its verified webhook signing secret. See [deployment](docs/vercel.md) for tested flows and limits.

**Copyright:** stores only publisher metadata and short feed excerpts, not full copyrighted articles. NVIDIA RSS is restricted to personal, non-commercial use by its published terms. Check source licensing before commercial operation.

## Verify

```powershell
python -m pytest backend\tests -q
cd frontend
npm run build
```

`python scripts\validate_sources.py` ingests and reports availability; `python scripts\generate_briefing.py` creates a morning briefing. `python scripts\live_smoke.py` checks the running backend, including a small billed OpenAI chat and TTS request, and writes safe results to `output/live-verification.json`. Unit tests use isolated temporary SQLite data and mock provider responses; they do not call paid APIs.

## Docker

```powershell
docker compose --env-file ..\.env.local up --build
```

Open port 8788. Credentials are injected at runtime. Local data persists in the named volume. Docker configuration is provided but the Docker build was not run in this session.

More detail: [architecture](docs/architecture.md), [setup](docs/setup.md), [sources](docs/sources.md), [deployment](docs/deployment.md), [Vercel preparation](docs/vercel.md), [testing](docs/testing.md).


Security protections and verification limits are documented in [SECURITY.md](SECURITY.md). Remote self-registration is disabled by default; the Windows launcher binds only to localhost.
