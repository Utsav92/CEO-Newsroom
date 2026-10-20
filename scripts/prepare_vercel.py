"""Create a minimal Vercel ingress project, containing no app data or API keys."""
import argparse
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def backend_origin(value):
    origin = urlsplit(value)
    host = origin.hostname or ''
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Use the backend public HTTPS hostname, not an IP address.')
    if (origin.scheme != 'https' or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host)
            or '.' not in host or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid'))
            or origin.username or origin.password or origin.port not in (None, 443)
            or origin.path not in ('', '/') or origin.query or origin.fragment):
        raise ValueError('Use only the backend public HTTPS origin, with no path, credentials or query.')
    return 'https://' + host


def configuration(backend):
    backend = backend_origin(backend)
    return {
        '$schema': 'https://openapi.vercel.sh/vercel.json',
        'framework': None,
        'outputDirectory': 'public',
        'buildCommand': '',
        'installCommand': '',
        'routes': [{
            'src': '/(.*)',
            'dest': backend + '/$1',
            'headers': {'Cache-Control': 'private, no-store', 'Vercel-CDN-Cache-Control': 'no-store'},
            'transforms': [{
                'type': 'request.headers', 'op': 'set',
                'target': {'key': 'x-newsroom-origin-secret'},
                'args': '$NEWSROOM_PROXY_SECRET', 'env': ['NEWSROOM_PROXY_SECRET']
            }]
        }]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-url', required=True)
    args = parser.parse_args()
    try:
        config = configuration(args.backend_url)
    except ValueError as exc:
        parser.error(str(exc))
    target = ROOT / 'output' / 'vercel'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'public').mkdir(exist_ok=True)
    (target / 'public' / '.gitkeep').touch()
    (target / 'vercel.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {target}. Configure NEWSROOM_PROXY_SECRET in Vercel before deploying.')


if __name__ == '__main__':
    main()
