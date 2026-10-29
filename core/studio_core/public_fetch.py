"""Explicit bounded HTTPS reads, with every DNS answer checked and the connection pinned."""

from __future__ import annotations
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit
from . import research_sites

LIMIT = 16_000_000


def canonical(value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or any(c.isspace() for c in value)
    ):
        raise ValueError("Use a bounded public HTTPS page address.")
    parts = urlsplit(value)
    if parts.fragment or parts.query:
        # Query credentials are too easy to leak into saved provenance. Select a public canonical page.
        raise ValueError(
            "Use the public page address without query parameters or a fragment."
        )
    return research_sites.site(value)


def resolve(host):
    return list(
        dict.fromkeys(
            info[4][0]
            for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    )


def once(url, address):
    parts = urlsplit(url)
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(
        parts.hostname, 443, timeout=20, context=context
    )
    # Bypass proxy/environment and DNS rebinding; retain original TLS hostname verification.
    plain = socket.create_connection((address, 443), timeout=20)
    try:
        connection.sock = context.wrap_socket(plain, server_hostname=parts.hostname)
        connection.request(
            "GET",
            urlunsplit(("", "", parts.path or "/", parts.query, "")),
            headers={
                "Accept": "text/html,text/plain,application/pdf",
                "Accept-Encoding": "identity",
                "User-Agent": "Infographic-Studio/0.2",
            },
        )
        response = connection.getresponse()
        return (
            response.status,
            {k.lower(): v for k, v in response.headers.items()},
            response.read(LIMIT + 1),
        )
    finally:
        connection.close()
        plain.close()


def fetch(value, *, resolver=resolve, transport=once, scope=None):
    current = canonical(value)
    for _ in range(5):
        if scope is not None:
            reason = scope.refuse(current)
            if reason:
                raise ValueError(reason)
        addresses = resolver(urlsplit(current).hostname)
        if not addresses or not all(
            (getattr(a := ipaddress.ip_address(v), "ipv4_mapped", None) or a).is_global
            for v in addresses
        ):
            raise ValueError(
                "This address resolves to a private or reserved network. No page was read."
            )
        status, headers, raw = transport(current, addresses[0])
        headers = {k.lower(): v for k, v in headers.items()}
        if status in (301, 302, 303, 307, 308):
            current = canonical(urljoin(current, headers.get("location", "")))
            continue
        if (
            status != 200
            or len(raw) > LIMIT
            or headers.get("content-encoding", "identity") not in ("", "identity")
        ):
            raise ValueError(
                "The public page is unavailable, compressed unexpectedly, or exceeds 16 MB. Upload a selected text copy instead."
            )
        kind = headers.get("content-type", "").split(";")[0].lower()
        if kind not in ("text/html", "text/plain", "application/pdf"):
            raise ValueError(
                "This URL is not a supported public text, HTML or PDF page."
            )
        return {"url": current, "mime": kind, "raw": raw}
    raise ValueError(
        "This public page redirected too many times. Choose its canonical address."
    )
