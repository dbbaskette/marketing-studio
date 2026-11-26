"""Whether a repository address given from a phone names another computer (GitHub issue #539).

What a caller needs to know
---------------------------
    repository_address.web_repository(address) -> bool

- One rule for a caller on Marketing Studio's private link, the same in every studio: such a
  caller cannot set or ask about a folder on the computer the studios run on, and may still
  give a repository web address. An address is accepted only when it is `https://` or
  `ssh://` with a host, or `user@host:path`; it holds no whitespace or control character; its
  host does not start with a dash; and its host is not this computer.
- This computer is `localhost` or a name ending in `.localhost`, a loopback address
  (127.0.0.0/8, ::1, an IPv4 loopback written as IPv6 or in a short numeric form), the
  unspecified address (0.0.0.0, ::), or this computer's own host name, compared without
  regard to case, with and without a `.local` ending. Other hosts, including addresses on the
  local network, are allowed. `http://` is refused.
- A caller on the computer itself is not checked here. Nothing is looked up on the network:
  the only question asked of this computer is its own host name.
- Standard library only, and nothing from the deck studios' shared runner, so every studio
  can import it.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

_SCP = re.compile(r'^[^@/:\s]+@([^@/:\s\[\]]+):(.+)$')
_NUMERIC = re.compile(r'[0-9a-fx.]+')


def _address(host: str):
    """The IP address `host` is written as, in any form a resolver reads, or None."""
    try:
        return ipaddress.ip_address(host.split('%', 1)[0])
    except ValueError:
        pass
    if _NUMERIC.fullmatch(host):
        try:   # 127.1, 2130706433, 0x7f.0.0.1: the forms inet_aton, and so Git, accepts
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return None
    return None


def this_computer(host) -> bool:
    """Whether a repository host is the computer the studios run on."""
    name = str(host or '').strip().lower().rstrip('.')
    if name.startswith('[') and name.endswith(']'):
        name = name[1:-1]
    if not name or name == 'localhost' or name.endswith('.localhost'):
        return True
    found = _address(name)
    if found is not None:
        mapped = getattr(found, 'ipv4_mapped', None)
        return any(one.is_loopback or one.is_unspecified for one in (found, mapped) if one is not None)
    own = socket.gethostname().strip().lower().rstrip('.')
    bare = own.removesuffix('.local')
    return bool(bare) and name in (bare, bare + '.local')


def web_repository(address) -> bool:
    """Whether a phone may give `address` as a repository: https or ssh, or user@host:path,
    of a computer other than this one."""
    if not isinstance(address, str) or not address \
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in address):
        return False
    if '://' in address:
        try:
            parts = urlsplit(address)
            host = parts.hostname
        except ValueError:
            return False
        if parts.scheme.lower() not in ('https', 'ssh') or not host:
            return False
        # The host as written, for a dash: urlsplit keeps it, after any user name.
        written = parts.netloc.rpartition('@')[2]
    else:
        found = _SCP.match(address)
        if not found:
            return False
        host = written = found.group(1)
    if written.startswith('-') or host.startswith('-'):
        return False
    return not this_computer(host)
