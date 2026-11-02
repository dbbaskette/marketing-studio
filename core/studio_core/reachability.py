"""Whether an assistant's service can be reached from this network, and whether the error
lines of an assistant's failed run say it could not connect to its service.

`reachable(host)` and `blocked(host)` connect over TLS and check the service's certificate,
within one time limit, sending no request and starting no agent. The shared runner's
`ready()` and Blog Studio's Status → Check this computer both use them.
`connection_failure(error_lines(lines))` reads what a failed run printed: it is a best
effort, and `blocked(host)` is the real check.
"""

from __future__ import annotations

import base64
import http.client
import re
import socket
import ssl
import threading
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
    """Why `host` cannot be reached over TLS from this network, or None when it can or
    when that could not be told in time: ('intercepted', why) when the connection is made
    but its certificate is not trusted, as on a network that decrypts the connection, else
    ('unreachable', why). It goes through this computer's proxy when it has one, sends no
    request and never raises.

    `seconds` bounds the whole look, finding the address included: a look still going
    then is left to end by itself, and says nothing."""
    found: list = []
    look = threading.Thread(target=lambda: found.append(_look(host, seconds)), daemon=True)
    look.start()
    look.join(seconds)
    return found[0] if found else None


def _look(host: str, seconds: float) -> tuple[str, str] | None:
    context = ssl.create_default_context()
    try:
        proxy = urllib.request.getproxies().get('https')
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
    except TimeoutError:
        return None  # Too slow to tell, which is not the same as blocked.
    except (OSError, http.client.HTTPException, ValueError) as failure:
        return 'unreachable', str(failure)
    except Exception:  # A look that fails in another way says nothing about the network.
        return None
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


# How a failed run's own error lines say the assistant could not connect to its service:
# the lines a CLI marks as errors ("ERROR: ...", "API Error: ..."), or a Claude Code error
# result, never what the assistant thought or wrote. Codex gives up after "Reconnecting...
# 5/5", often with "workspace routing discovery failed"; Claude Code says "Connection error"
# or "Unable to connect", with a certificate error on a network that intercepts it.
NETWORK = (
    'routing discovery failed',
    'error sending request',
    'connection error',
    'connection failed',
    'connection refused',
    'connection reset',
    'unable to connect',
    'failed to connect',
    'network is unreachable',
    'could not resolve host',
    'dns error',
    'econnrefused',
    'econnreset',
    'econnaborted',
    'etimedout',
    'enotfound',
    'certificate',
    'self_signed_cert',
    'unable_to_get_issuer_cert',
    'unable_to_verify_leaf_signature',
    'unknownissuer',
)
# A connection that dropped: it may be this network, or the service itself.
DROPPED = ('stream disconnected',)
# Words that mean sign-in, an account limit, the model or the request: those keep their own
# advice, even when the connection was being retried at the time.
NOT_CONNECTION = (
    'not logged in',
    'not signed in',
    'please run /login',
    'unauthorized',
    'forbidden',
    'invalid api key',
    'authentication',
    'usage limit',
    'rate limit',
    'rate_limit',
    'too many requests',
    'quota',
    'insufficient',
    'credit',
    'context window',
    'context length',
    'model is not supported',
    'model not found',
    'model_not_found',
    'bad request',
    'invalid_request',
)
STATUS = re.compile(r'\bstatus(?: code)?:?\s*4\d\d\b', re.I)  # a 4xx answer: the request
ERROR_LINE = re.compile(
    r'(?:\[[^\]]*\]\s*)?(?:\d{4}-\d\d-\d\d[T ][\d:.]+Z?\s+)?(?:api\s+)?error\b', re.I
)
RETRY = re.compile(r'reconnecting\.{3}\s*(\d+)\s*/\s*(\d+)', re.I)


def error_lines(lines) -> list[str]:
    """The lines a CLI marked as errors: 'ERROR: ...', 'Error: ...', 'API Error: ...'."""
    return [str(line) for line in lines if ERROR_LINE.match(str(line).strip())]


def connection_failure(errors) -> str | None:
    """From a failed run's error lines alone (see `error_lines`), whether the assistant could
    not connect to its service: 'network' when a line names a connection or certificate
    failure, 'dropped' when its connection kept dropping and it gave up retrying, which may
    be the service as much as this network, else None. A retry notice ('Reconnecting...
    2/5') counts only as the last retry; sign-in, limit, model and request errors win."""
    low = [str(line).lower() for line in errors]
    text = '\n'.join(low)
    if any(mark in text for mark in NOT_CONNECTION) or STATUS.search(text):
        return None
    gave_up = False
    for line in low:
        retry = RETRY.search(line)
        if retry and retry.group(1) != retry.group(2):
            continue  # An earlier retry is not why it failed: the last one says.
        gave_up = gave_up or bool(retry)
        if any(mark in line for mark in NETWORK):
            return 'network'
        gave_up = gave_up or any(mark in line for mark in DROPPED)
    return 'dropped' if gave_up else None
