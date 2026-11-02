"""Whether an assistant's service can be reached from this network, and whether the error
output of an assistant's failed run says it could not connect to its service.

`reachable(host)` connects over TLS and checks the service's certificate, sending no
request and starting no agent. The shared runner's `ready()` and Blog Studio's Status →
Check this computer both use it. `cannot_connect(lines)` reads what a failed run printed:
it is a best effort, and `blocked(host)` is the real check.
"""

from __future__ import annotations

import base64
import http.client
import re
import socket
import ssl
import urllib.parse
import urllib.request

# The service each assistant uses, by the host its sign-in talks to, as a person knows it.
HOSTS = {'claude': 'api.anthropic.com', 'codex': 'chatgpt.com'}
SERVICES = {'api.anthropic.com': 'Anthropic', 'chatgpt.com': 'OpenAI', 'api.openai.com': 'OpenAI'}


def codex_host(login_status: str) -> str:
    """The host Codex uses, from what `codex login status` printed: OpenAI's API when it is
    signed in with an API key, else ChatGPT."""
    return 'api.openai.com' if 'api key' in str(login_status).lower() else HOSTS['codex']


def blocked(host: str, seconds: float = 8) -> tuple[str, str] | None:
    """Why `host` cannot be reached over TLS from this network, or None when it can:
    ('intercepted', why) when the connection is made but its certificate is not trusted, as
    on a network that decrypts the connection, else ('unreachable', why). It goes through
    this computer's proxy when it has one, sends no request and never raises."""
    context = ssl.create_default_context()
    proxy = urllib.request.getproxies().get('https')
    try:
        if proxy and not urllib.request.proxy_bypass(host):
            via = urllib.parse.urlsplit(proxy if '//' in proxy else f'//{proxy}')
            headers = {}
            if via.username:
                secret = f'{via.username}:{via.password or ""}'.encode()
                headers['Proxy-Authorization'] = 'Basic ' + base64.b64encode(secret).decode()
            link = http.client.HTTPSConnection(
                via.hostname, via.port or 80, timeout=seconds, context=context
            )
            link.set_tunnel(host, 443, headers=headers)
            try:
                link.connect()
            finally:
                link.close()
        else:
            with socket.create_connection((host, 443), timeout=seconds) as plain:
                context.wrap_socket(plain, server_hostname=host).close()
    except ssl.SSLCertVerificationError as failure:
        return 'intercepted', str(failure.verify_message)
    except (OSError, http.client.HTTPException, ValueError) as failure:
        return 'unreachable', str(failure)
    return None


def why(host: str, found: tuple[str, str]) -> str:
    """What `blocked(host)` found, in words."""
    kind, said = found
    if kind == 'intercepted':
        return (
            f'the connection to {host} is being intercepted on this network, or its '
            f'certificate is not trusted here ({said})'
        )
    return f'{host} cannot be reached from this network ({said})'


def reachable(host: str, seconds: float = 8) -> str | None:
    """Why a service cannot be reached over TLS from this network, or None when it can.

    It connects and checks the service's certificate, through this computer's proxy when
    it has one, and sends no request. A network that intercepts the connection fails here
    even though the agent is signed in.
    """
    found = blocked(host, seconds)
    return None if found is None else why(host, found)


# How a failed run's error output says the assistant could not connect to its service.
# Codex retries a dropped connection five times ("Reconnecting... 5/5") and then gives up,
# often with "workspace routing discovery failed"; Claude Code says "Connection error" or
# "Unable to connect", with a certificate error on a network that intercepts it. Words that
# mean sign-in or an account limit win: those keep their own advice.
CONNECTION = (
    'stream disconnected',
    'error sending request',
    'routing discovery failed',
    'connection failed',
    'connection error',
    'connection refused',
    'connection reset',
    'unable to connect',
    'failed to connect',
    'network is unreachable',
    'could not resolve host',
    'econnrefused',
    'econnreset',
    'etimedout',
    'enotfound',
    'certificate verify failed',
    'self-signed certificate',
    'self signed certificate',
    'unable to get local issuer certificate',
    'invalid peer certificate',
    'unknownissuer',
    'self_signed_cert_in_chain',
    'unable_to_get_issuer_cert_locally',
    'unable_to_verify_leaf_signature',
)
NOT_CONNECTION = (
    'not logged in',
    'not signed in',
    'please run /login',
    'unauthorized',
    'invalid api key',
    'authentication',
    'usage limit',
    'rate limit',
    'quota',
)
RETRY = re.compile(r'reconnecting\.{3}\s*(\d+)\s*/\s*(\d+)')


def cannot_connect(lines) -> bool:
    """Whether a failed run's error output says the assistant could not connect to its
    service. A retry notice ("Reconnecting... 2/5") counts only when it is the last retry:
    a connection that dropped once and came back is not why a run failed."""
    kept, gave_up = [], False
    for line in lines:
        low = str(line).lower()
        retry = RETRY.search(low)
        if retry:
            gave_up = gave_up or retry.group(1) == retry.group(2)
            continue
        kept.append(low)
    text = '\n'.join(kept)
    if any(mark in text for mark in NOT_CONNECTION):
        return False
    return gave_up or any(mark in text for mark in CONNECTION)
