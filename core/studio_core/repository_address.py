"""Whether a repository address given from a phone names another computer (GitHub issue #539).

What a caller needs to know
---------------------------
    repository_address.web_repository(address) -> bool

- One rule for a caller on Marketing Studio's private link, the same in every studio: such a
  caller cannot set or ask about a folder on the computer the studios run on, and may still
  give a repository web address. An address is accepted only when it is `https://` or
  `ssh://` with a host, or `user@host:path`; it holds no whitespace or control character; its
  host is letters, digits, dots and dashes, or a bracketed IPv6 address of hexadecimal digits
  and colons with an optional zone (a percent sign anywhere else is refused, as Git would
  decode it into another host); neither its host nor its user name starts with a dash; and
  its host is not this computer.
- This computer is `localhost` or a name ending in `.localhost`, a loopback address
  (127.0.0.0/8, ::1, an IPv4 loopback in a short numeric form), the unspecified address
  (0.0.0.0, ::), an IPv6 address that carries a loopback or unspecified IPv4 one (mapped,
  compatible, 6to4, Teredo, NAT64), or this computer's own host name, compared without
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

_SCP = re.compile(r'^([^@/:\s]+)@([^@/:\s\[\]]+):(.+)$')
_NUMERIC = re.compile(r'[0-9a-fx.]+')
# A host as a phone may write it: letters, digits, dots and dashes, or a bracketed IPv6
# address of hexadecimal digits and colons with an optional zone. A percent sign or any other
# character, which Git may decode into another host, is refused.
_NAME = re.compile(r'[A-Za-z0-9.-]+')
_BRACKETED = re.compile(r'\[([0-9A-Fa-f:]+)(?:%[A-Za-z0-9._~-]+)?\]')
_PORT = re.compile(r'[0-9]{1,5}')


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


def _embedded(found):
    """The IPv4 addresses an IPv6 address carries: mapped, compatible (::a.b.c.d), 6to4,
    Teredo and the NAT64 well-known prefix."""
    if found.version != 6:
        return []
    carried = [found.ipv4_mapped, found.sixtofour, *(found.teredo or ())]
    value = int(found)
    if value >> 32 == 0 or value >> 32 == 0x0064ff9b0000000000000000:
        carried.append(ipaddress.IPv4Address(value & 0xFFFFFFFF))
    return [one for one in carried if one is not None]


def this_computer(host) -> bool:
    """Whether a repository host is the computer the studios run on."""
    name = str(host or '').strip().lower().rstrip('.')
    if name.startswith('[') and name.endswith(']'):
        name = name[1:-1]
    if not name or name == 'localhost' or name.endswith('.localhost'):
        return True
    found = _address(name)
    if found is not None:
        return any(one.is_loopback or one.is_unspecified for one in (found, *_embedded(found)))
    own = socket.gethostname().strip().lower().rstrip('.')
    bare = own.removesuffix('.local')
    return bool(bare) and name in (bare, bare + '.local')


def _host(written: str):
    """The host in `host[:port]` as a phone may write it, or None."""
    bracketed = _BRACKETED.match(written)
    if bracketed:
        host, rest = bracketed.group(0), written[bracketed.end():]
    else:
        host, _, port = written.partition(':')
        rest = ':' + port if _ else ''
        if not _NAME.fullmatch(host):
            return None
    if rest and not (rest.startswith(':') and _PORT.fullmatch(rest[1:])):
        return None
    return host


def web_repository(address) -> bool:
    """Whether a phone may give `address` as a repository: https or ssh, or user@host:path,
    of a computer other than this one."""
    if not isinstance(address, str) or not address \
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in address):
        return False
    if '://' in address:
        try:
            parts = urlsplit(address)
        except ValueError:
            return False
        if parts.scheme.lower() not in ('https', 'ssh'):
            return False
        user, at, written = parts.netloc.rpartition('@')
        host = _host(written)
    else:
        found = _SCP.match(address)
        if not found:
            return False
        user, at, written = found.group(1), '@', found.group(2)
        host = written if _NAME.fullmatch(written) else None
    if not host or host.startswith('-') or (at and (not user or user.startswith('-'))):
        return False
    return not this_computer(host)
