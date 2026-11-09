"""SSRF-safe HTTP fetching for user-supplied links.

Every hop (including redirects) must be http(s) to a host that resolves only to public
addresses. Redirects are followed manually so each target is checked before connecting.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

# An honest, contactable identity: sites such as Wikipedia reject clients without one
# (https://meta.wikimedia.org/wiki/User-Agent_policy). We never pose as a browser.
USER_AGENT = "LifeLibrary/1.0 (+https://github.com/Swaraj52/top-50-claude-projects; personal read-later app)"
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/pdf")
MAX_REDIRECTS = 5


class FetchError(Exception):
    """A user-facing problem fetching a link."""


@dataclass
class FetchResult:
    url: str
    content_type: str
    body: bytes
    encoding: str

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")


def resolve_host(host: str) -> list[str]:
    """All addresses a host resolves to (separate so tests can stub DNS)."""
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})
    except socket.gaierror as exc:
        raise FetchError(f"Couldn't find the site '{host}'") from exc


def check_public(url: str, allow_private: bool = False) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchError("Only http and https links can be saved")
    if not parts.hostname:
        raise FetchError("That link has no host name")
    if allow_private:
        return
    for addr in resolve_host(parts.hostname):
        ip = ipaddress.ip_address(addr.split("%")[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise FetchError("That link points to a private or local network address and can't be fetched")


def fetch(
    url: str,
    *,
    timeout: float = 15.0,
    max_bytes: int = 8 * 1024 * 1024,
    allow_private: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> FetchResult:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers, transport=transport) as client:
            for _ in range(MAX_REDIRECTS + 1):
                check_public(url, allow_private)
                with client.stream("GET", url) as resp:
                    if resp.is_redirect and resp.headers.get("location"):
                        url = urljoin(url, resp.headers["location"])
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"The site answered HTTP {resp.status_code}")
                    ctype = resp.headers.get("content-type", "text/html").split(";")[0].strip().lower()
                    if not any(ctype.startswith(t) for t in ALLOWED_TYPES):
                        raise FetchError(f"Unsupported content type '{ctype}' (web pages, text and PDF only)")
                    body, size = [], 0
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise FetchError(f"The page is larger than {max_bytes // (1024 * 1024)} MB")
                        body.append(chunk)
                    return FetchResult(str(resp.url), ctype, b"".join(body), resp.charset_encoding or "utf-8")
            raise FetchError("Too many redirects")
    except httpx.TimeoutException as exc:
        raise FetchError("The site took too long to respond") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"Couldn't download the page ({exc.__class__.__name__})") from exc
