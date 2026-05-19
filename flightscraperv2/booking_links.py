from __future__ import annotations

import re
from html import unescape
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


META_REFRESH_RE = re.compile(
    r"""<meta[^>]+content=["'][^"']*url=(?P<quote>['"]?)(?P<url>.+?)(?P=quote)["']""",
    re.IGNORECASE,
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_google_deeplink(url: str | None, timeout_seconds: float = 20.0) -> str | None:
    if not url:
        return None
    opener = build_opener(_NoRedirect)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = opener.open(request, timeout=timeout_seconds)
        return _extract_target_url(url, response.headers.get("Content-Type"), response.read().decode("utf-8", "ignore"))
    except HTTPError as exc:
        location = exc.headers.get("Location")
        if location:
            return location
        body = exc.read().decode("utf-8", "ignore")
        return _extract_target_url(url, exc.headers.get("Content-Type"), body)
    except Exception:
        return None


def _extract_target_url(source_url: str, content_type: str | None, body: str) -> str | None:
    match = META_REFRESH_RE.search(body)
    if match:
        return unescape(match.group("url")).strip()
    if content_type and "text/html" not in content_type.lower():
        return None
    parsed = urlparse(source_url)
    return source_url if parsed.netloc else None
