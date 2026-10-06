"""Validate browser origins independently of CORS response permissions.

Browser unsafe requests and WebSocket handshakes carry Origin. Non-browser
clients without browser headers still authenticate with the opaque session.
"""
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from app.core.config import settings


def trusted_browser_request(headers: Headers) -> bool:
    origins = headers.getlist("origin")
    if origins:
        return len(origins) == 1 and origins[0] in settings.CORS_ORIGINS
    referers = headers.getlist("referer")
    if referers:
        if len(referers) != 1:
            return False
        try:
            source = urlsplit(referers[0])
            origin = f"{source.scheme}://{source.netloc}"
        except ValueError:
            return False
        return origin in settings.CORS_ORIGINS
    # Browsers declaring a fetch without a usable source must fail closed.
    # Header-less local API clients are not ambient browser-cookie requests.
    return not headers.get("sec-fetch-site")


class BrowserOriginMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http"
                and scope["method"] not in {"GET", "HEAD", "OPTIONS"}
                and not trusted_browser_request(Headers(scope=scope))):
            response = JSONResponse(status_code=403, content={"detail": {
                "code": "untrusted_browser_origin", "message": "Browser origin is not permitted."}})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
