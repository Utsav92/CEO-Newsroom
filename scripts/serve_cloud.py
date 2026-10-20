"""One persistent cloud worker; authenticated ingress handles proxy identity."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

if __name__ == '__main__':
    from app.config import PROXY_SECRET, PUBLIC_APP_URL, DATA
    from urllib.parse import urlsplit
    import uvicorn

    origin = urlsplit(PUBLIC_APP_URL)
    if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
            or origin.path not in ('', '/') or origin.query or origin.fragment):
        raise SystemExit('Set PUBLIC_APP_URL to the exact public HTTPS origin before cloud startup.')
    if len(PROXY_SECRET) < 64:
        raise SystemExit('Set NEWSROOM_PROXY_SECRET to at least 64 random characters.')
    # Test storage before starting ingestion or accepting requests.
    marker = DATA / '.write-check'
    marker.write_text('ok', encoding='utf-8')
    marker.unlink()
    uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '10000')),
                workers=1, proxy_headers=False, server_header=False,
                limit_concurrency=64, timeout_keep_alive=5)
