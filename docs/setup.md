# Setup

Use `scripts/setup_windows.ps1 -Run` for a virtual environment, backend packages, reproducible npm install, production build, and single-server start. Subsequent starts use `scripts/run.ps1`. The setup script intentionally prints no credential values. Existing key configuration is read in place.

The backend reads the process environment, project `.env.local`, project `.env`, and parent workspace `.env.local` in that order without overwriting values already loaded. Keep all credential files ignored. Do not prefix server secrets with `VITE_`.

Ports: 8788 for the API and built UI; 5178 for Vite development. Set `NEWSROOM_DATA_DIR` to relocate data, or `DATABASE_URL` to a SQLAlchemy URL. PostgreSQL requires an appropriate driver such as psycopg and separate database provisioning; the tested deployment uses SQLite.

For YouTube, enable YouTube Data API v3 in your Google Cloud project and inject a restricted server API key as `YOUTUBE_API_KEY`. Restart the backend after changing credential configuration. [Official setup and API reference](https://developers.google.com/youtube/v3).

For actual video speech and visual understanding, create a [Gemini API key](https://aistudio.google.com/api-keys), keep it in ignored project `.env.local` as `GEMINI_API_KEY`, and restart. `GEMINI_VIDEO_MODEL` defaults to `gemini-3.5-flash-lite`; the key needs model/service access and quota. The YouTube feed credential alone does not grant this capability. GET `/api/video-understanding/status` reports configuration presence without exposing credentials; an actual video request verifies access. In Docker, use the project `.env.local` when injecting these variables, or set them explicitly in the process environment.

If a source is unavailable, inspect Our sources, check network access, and retry with Refresh news. Empty company/date views are valid when no dated reporting exists. OpenAI access/billing errors are surfaced clearly instead of replaced with simulated responses.

Open the app and create your first account to retain existing local history. Additional accounts start with separate saved stories and conversations. Use Settings → Account → Sign out to end a session. Payment activation is pending local Stripe credentials; see [Stripe setup](payments.md) to connect later. Language selection changes new CEO answers, while the interface and existing content remain in their original language.
