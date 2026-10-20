"""Authenticated ingress for the optional Vercel -> persistent server deployment."""
import hmac
import ipaddress
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse


class CloudProxy:
    def __init__(self, app, origin_provider, secret_provider):
        self.app = app
        self.origin_provider = origin_provider
        self.secret_provider = secret_provider

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        secret = self.secret_provider()
        if not secret:
            return await self.app(scope, receive, send)

        # The hosting platform needs a small readiness response without browser
        # credentials. It exposes no account, provider or ingestion information.
        if scope['path'] == '/healthz' and scope['method'] in ('GET', 'HEAD'):
            from .database import Session
            from sqlalchemy import text
            try:
                with Session() as db:
                    db.execute(text('SELECT 1'))
                response = JSONResponse({'status': 'ok'}, headers={'Cache-Control': 'no-store'})
            except Exception:
                response = JSONResponse({'status': 'unavailable'}, status_code=503,
                                        headers={'Cache-Control': 'no-store'})
            return await response(scope, receive, send)

        headers = Headers(scope=scope)
        supplied = headers.getlist('x-newsroom-origin-secret')
        valid = (len(secret) >= 64 and len(supplied) == 1 and
                 hmac.compare_digest(supplied[0].encode(), secret.encode()))
        origin = urlsplit(self.origin_provider())
        if not valid or origin.scheme != 'https' or not origin.hostname:
            return await JSONResponse({'detail': 'Use the public newsroom address.'}, status_code=403,
                                      headers={'Cache-Control': 'no-store'})(scope, receive, send)

        # Never take Host or scheme from client-supplied forwarded headers. The
        # configured canonical HTTPS origin keeps cookies and CSRF same-origin.
        scope = dict(scope)
        scope['headers'] = list(scope['headers'])
        mutable = MutableHeaders(scope=scope)
        mutable['host'] = origin.netloc
        del mutable['x-newsroom-origin-secret']
        scope['scheme'] = 'https'
        scope['server'] = (origin.hostname, origin.port or 443)
        # Vercel overwrites x-real-ip with the visitor address. Only use it after
        # authenticating ingress; otherwise every visitor shares a proxy limit.
        try:
            address = ipaddress.ip_address(headers.get('x-real-ip', ''))
            if address.is_loopback or address.is_private or address.is_unspecified:
                raise ValueError('Non-public visitor address')
            scope['client'] = (str(address), 0)
        except ValueError:
            return await JSONResponse({'detail': 'Invalid proxy visitor address.'}, status_code=403,
                                      headers={'Cache-Control': 'no-store'})(scope, receive, send)
        return await self.app(scope, receive, send)
