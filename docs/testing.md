# Testing

Automated suite: `python -m pytest backend/tests -q`. The final suite contains 175 tests, with one third-party Starlette/httpx deprecation warning. Tests exercise all eight routes, neutral/multi-company routing, semantic classification, canonical URLs, publication dates, missing dates, distinction between update and publication dates, preservation of date-only precision, deduplication, source outage handling, exclusion of Perplexity categories, date/company/saved filters, privacy defaults, briefings, DST schedules, source-validated chat IDs/history, rejected fabricated citations, correction of unrelated presenters, insufficient evidence, missing keys, local authorization/origin protection, input validation, all portrait variants, and removal of the baked checkerboard. The additional video checks are detailed below.

## Separate Chats and article browsing

Five history tests cover recency ordering, pagination, independent conversations, restoring article/topic/follow-ups without writes, expired video metadata, missing articles, and read-only list/detail API validation. The production build passes. Browser QA checks filtered-feed reading position, returning without reload during an answer, an answer-ready shortcut, saved conversation search, reopening article context, selection after reload, and 390px layout. A browser-only incoming-story fixture verifies the background update banner without inserting rows into the reading position. The fixture is never stored as news or used as AI evidence. Screenshots are ignored `output/playwright/feed-chat-return.png`, `saved-chat-history-desktop.png`, and `saved-chat-history-mobile.png`.

Frontend: `npm run build` performs TypeScript checking and a Vite production build. Browser QA uses Playwright CLI for the actual running application, desktop/mobile screenshots, navigation, filters, saved stories, settings, and chat. Screenshots live under ignored `output/playwright`.

YouTube CEO chat controls: the production build and 27 focused video/history tests pass. Browser QA verifies named chat buttons and matching avatars for all eight companies, opening a new video conversation from both a card and the player, the video-specific composer, returning through Back to videos, resuming a real saved video conversation with its source context, video labels in history, and no overflow at 390px. This UI check reopens stored answers and makes no new AI calls. Screenshots: ignored `output/playwright/youtube-ceo-chat-option.png`, `youtube-ceo-conversation.png`, and `youtube-ceo-chat-mobile.png`.

`scripts/live_smoke.py` makes bounded live OpenAI chat and generic TTS requests. It records the actual status, citation count, presenters, audio bytes, company counts, briefing count, and expected missing-YouTube-key response in `output/live-verification.json`. This script is explicitly billed API verification; unit tests are offline fixtures and do not spend API credits.

Remaining verification limits: YouTube playback remains subject to player, regional, and account restrictions; TLDR fails TLS here; Docker and PostgreSQL were not run. Scheduler trigger timing is tested across DST; no claim is made that a future scheduled run has already occurred. Notifications require an open browser and opt-in permission.

## CEO thinking state

`npm run test:routing` inside `frontend` runs thirteen browser-independent routing and narration checks (Node.js 22.18+). They cover all eight companies, company product aliases, directly addressed CEOs, explicit-company precedence over the selected filter, comparisons, selected-company questions, follow-ups, and neutral general questions. Backend tests also check that a selected CEO delivers the answer or explains when supporting reporting is missing.

The thinking indicator captures the responding CEO(s) when the question is submitted. It shows the existing circular portrait with a thought bubble and a subtle animation while the request is pending. It is removed on either success or failure. Responses keep the company CEO's portrait and source citations; failed questions stay in the composer for retry. Reduced-motion preferences disable the CSS animation.

Browser verification passed with a real NVIDIA request: Jensen's thinking portrait transitioned to the same portrait on an answer containing five source citations. A second browser request used an explicitly simulated API failure to verify that an OpenAI/Anthropic comparison shows both thinking portraits, clears both on failure, and restores the question. That failure fixture ran only in the QA browser and was removed afterward. Screenshots: `output/playwright/jensen-thinking.png` and `output/playwright/jensen-answer.png`.


## Article RAG and shared company perspectives

Offline fixtures verify publisher-only passage indexing, vector reuse and source-change reindexing; preservation of the selected article outside date filters; optional related reporting and unrelated-company exclusion; section citations and persisted context; two- and three-company perspectives; company additions in a question; general-topic follow-ups retaining all presenters; rejection of unknown passage IDs, uncited supported sections and answers that omit the selected source; honest no-reporting responses; and missing-article HTTP 404 handling. These provider fixtures make no paid calls.

The date-only “today” fixture uses the user's configured timezone rather than UTC, so it remains correct around midnight during British Summer Time.


The SQLite migration uses WAL; a file-backed test confirms concurrent readers see committed source data while an indexing transaction writes. An independent model pass reviews explanations, and a test ensures its citations are validated again before any messages are saved.

Live article QA passed for the collected NVIDIA/OpenAI GPU story: both thinking portraits transitioned to distinct company answers with all three explanation sections and validated source citations. Retrieval supplied six passages including the selected article and three relevant supporting reports. Article/topic scope and structured history survived reload. At 390px there was no horizontal overflow. A separate browser-only simulated outage verified three thinking CEOs and preservation of the question and selected article; the interception was removed afterward. Results: output/article-rag-verification.json. Screenshots: output/playwright/article-*.png.


## Daily official YouTube uploads

Offline API fixtures cover all eight official handles, upload-playlist retrieval, owner-ID checks, public/processed status, exclusion of fan/reposted/private/unlisted/deleted videos and unrequested IDs, local search without additional quota, daily calendar refresh in London, partial channel outages, safe provider-error handling, preservation of verified cache on failure, retry backoff and recovery, changed-handle/ID rejection, removal of missing videos, expiry deletion, rejection of legacy unverified cache, DST at 07:30, authorized manual refresh, and secret-free status responses. The additive migration test now verifies versions 1–5.

Live API verification loaded 400 videos across all eight verified official channel IDs, with 50 uploads per company, no channel warnings, and no credentials returned to the browser. The next real scheduled job is shown in `/api/youtube/status`; this verifies scheduling, not that a future job has already run. Results are in ignored `output/youtube-live-verification.json`.

Browser QA passed with the real 400-upload feed: all-company display, 50 NVIDIA uploads, local title search and empty results, rapid company switching, official player/watch URLs, channel-status links, and no horizontal overflow at 390px. Player URLs and links were verified; successful streaming remains subject to YouTube. Screenshots are output/playwright/youtube-official-desktop.png and youtube-official-mobile.png. Results: output/youtube-ui-verification.json. A same-day missed-morning refresh test verifies catch-up when an earlier overnight update exists.


## Video speech and visual understanding

Offline tests cover direct public YouTube URL submission to the multimodal Interactions API, structured audio/visual observations, exclusion of private reasoning steps, elapsed timestamp conversion and duration bounds, incomplete/invalid evidence rejection, missing credentials, quota/access/provider failures without metadata fallback or secret exposure, in-memory reuse and concurrent request coalescing, fresh official-owner/public-status verification, video-specific citations and chat history, distinct company perspectives and follow-ups, and API scope validation. Provider mocks make no paid calls. All test startup jobs are isolated from live providers.

The browser offers Ask about this video on each official upload and in the player. Video focus and questions survive reload, selected evidence remains separate from related reporting, and the pending state shows the CEO portrait with Understanding video. AI observations are paraphrases with approximate timestamp links, not authenticated captions or real CEO statements. Live providers may return busy or quota errors; these are displayed without manufactured answers.

Verification for this change: **89 backend tests**, **11 frontend routing checks**, and a production build pass. A real 71-second official OpenAI Codex Originals upload was analyzed with `gemini-3.5-flash-lite`. Browser QA confirmed Sam Altman's pending avatar, a live three-section OpenAI explanation citing actual video observations, explicit absence of technical mechanisms in the promotional clip, valid timestamp links, persisted video/answer scope after reload, and no horizontal overflow at 390px. Other video models returned capacity/quota errors during evaluation; successful processing is not guaranteed for every upload or at every time. Screenshots: ignored `output/playwright/video-understanding-*.png`.


## Article hearts and Saved articles

The production build and all 90 backend tests pass. A regression fixture verifies that an old saved link remains available after more than 1,000 newer reports arrive. The saved-ID condition is applied before the feed query limit.

Real browser QA verified two sequential heart likes, red heart and accessible pressed states, protection against overlapping saves, original article links and the sidebar count, persistence after reload into `?view=saved`, reset of inherited date filters, removal of just one selected article, and a separate Saved articles page without the chat composer. A browser-only simulated save failure preserved the unliked state and allowed retry. The 390px layout has no horizontal overflow. QA-created likes were removed without changing previously saved articles or other preferences. Screenshots: ignored `output/playwright/article-heart-liked.png`, `saved-articles-desktop.png`, and `saved-articles-mobile.png`. Saved article search/topic/date filters remain available.


## LLM assessments, predictions and follow-up citation repair

All **96 backend tests** and the production build pass. Fixtures cover an older referenced story surviving a new retrieval/date filter, rehydration of real database records rather than trusting historical citation strings, per-request source-ID schemas, automatic regeneration of bad citations without saving the invalid draft, fresh conditional reasoning after repeated citation failures, useful general explanations without retrieved reporting or unnecessary embeddings, uncited inference versus sourced factual claims, third-person company voice, and repair/revalidation of article-review citations. Unit-test database fixtures disable real OpenAI credentials to prevent accidental live API use.

Real browser verification reproduced the reported flow against the collected Verge article **Eight states sue OpenAI, saying ChatGPT isn’t safe for kids**. After the article summary, **is this a problem?** returned Sam's labeled reasoned assessment with the original article citation. The assessment label and conversation survived reload. Two browser-only simulated connection failures and a successful real retry produced just one unanswered-question bubble and retained the OpenAI presenter. The 390px layout had no horizontal overflow. Interceptions were removed. Screenshots: ignored `output/playwright/reasoned-followup-answer.png` and `reasoned-answer-mobile.png`.

Separate bounded live calls verified a general hypothetical explanation with no sources and a third-person case assessment with a real source. Reasoning is explicitly labeled and can still be mistaken; no prediction-accuracy metric is claimed. Provider outages and invalid configuration remain genuine failure conditions, not grounds for fabricated reporting.


## Interactive CEO questions and recommended follow-ups

All **102 backend tests** and the production build pass. New fixtures cover generated follow-up fields and persistence without a separate generation call, typed answers without referential pronouns, clicked questions that explicitly name a company, preservation of the referenced source outside a fresh date filter, safe handling of malformed/duplicate suggestion metadata, distinct company follow-ups in shared article answers, and propagation of the CEO question into video analysis context.

Live browser QA completed three real turns: Sam answered a small-team OpenAI cost question, asked which task mattered, then used the selected **Automating document analysis** reply to offer a tailored explanation and ask about document types/outcomes. Clicking a recommended question continued the same session. Earlier choices became inactive, the newest suggestions survived reload, and the 390px layout had no horizontal overflow. A separate real OpenAI/NVIDIA article request returned different follow-up questions and reply options for Sam and Jensen. Existing source and video grounding checks remain in place. Screenshots: ignored `output/playwright/ceo-followup-desktop.png` and `ceo-followup-mobile.png`.


## Detailed researched answers

All 126 backend tests and 13 frontend checks pass. Research fixtures cover required live search, focused query inputs, provider-issued citation and source URL provenance, source registry filtering, public URL checks, cached research copies, source-only opt-out, provider failure disclosure, bounded original-page reads, robots and redirect restrictions, nested citation validation, internal-ID suppression, conditional impact labels, preservation of depth through review, answer token budgets, and persistence of structured research in saved chats. Narration checks ensure long answers split into bounded tracks without losing text. Production TypeScript/Vite builds pass.

Live verification uses a substantive RAG-versus-fine-tuning question with the existing authorized provider configuration. Final metrics and the complete answer are saved in ignored `output/deep-answer-live-verification.json` and `deep-answer-live-response.json`. Browser checks cover all five general research sections, visible source provenance, hidden internal citation IDs, research surviving reload, and a 390px layout. Screenshots are `output/playwright/deep-researched-answer-desktop.png` and `deep-researched-answer-mobile.png`. Research source identity and traceability do not independently prove every generated conclusion; sparse coverage and failed research are disclosed.


Accounts and payments checks cover registration, hashed passwords and sessions, logout revocation, expiry, CSRF and throttling, password redaction, cross-account chat isolation, saved preferences, answer-language instructions, exact USD monthly prices, disconnected payments, server-verified paid status, bank invoices, owned QR images, invalid prices, idempotent outage retries and signed/replayed webhooks. Stripe calls are mocked and create no merchant objects or charges. The older live provider smoke script requires an authenticated session before use and is not part of these offline checks.


The payment/account completion adds seven offline checks, including a concurrent password-change/sign-in guard: account-specific display-name editing, password rotation/revocation and redaction/reuse validation; customer-scoped invoice pagination with unsafe-link filtering; local history during provider outages; and owned stop/resume renewal operations. Browser QA uses a separate database with all provider credentials disabled. Real local requests verify profile/password changes; labeled invoice/renewal fixtures verify pagination, PDF links and confirmation before mutation. Desktop/mobile screenshots are ignored output/playwright/payment-*.png. 390px checks show no horizontal overflow. Stripe invoice/renewal browser intercepts are removed afterward; no merchant objects, email or charges are created.


Five Stripe mode checks cover standard/restricted test keys, HTTPS enforcement for both live prefixes, and rejection of publishable keys. Live test-key verification performs read-only access checks without printing account data. A bounded verification creates one unpaid test checkout/customer with no email or payment details, verifies USD $2 monthly pricing, expires the session, archives its generated price/product and removes its test customer. Local webhook preparation can require Debugging Tools Write on a restricted key. No real-money payment is made.


Security hardening adds 24 checks covering browser policies on success and errors, cross-site requests, signed/session-bound CSRF, malformed/oversized and streamed bodies, HTTPS and forged proxy headers, idle/session-count limits, registration policy, owner-only refresh, audio ownership, bounded identity throttles, outbound allowlists and safe unhandled errors. Full suite: 175 backend tests. The npm tree audit and 30-package Python runtime audit report no known vulnerabilities as of 19 October 2026. Reports live under ignored output/. Docker and public TLS were not run; this is not an external penetration-test certification.
