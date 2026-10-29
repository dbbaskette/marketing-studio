"""Lossless shared settings storage with isolated product contexts."""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import time
from contextlib import contextmanager
from json import decoder
from pathlib import Path

from studio_core.modules import fresh_module

PRODUCT = globals().get("PRODUCT", "Studio")
WorkspaceError = globals().get("WorkspaceError", ValueError)
ADDRESS_CHECK = globals().get("ADDRESS_CHECK")
STRICT_GROUPS = globals().get("STRICT_GROUPS", False)

SCHEMA = 1
PATH = Path.home() / '.config' / 'studios-config.json'
GROUPS = ('team', 'person', 'assistant', 'brand', 'local', 'render', 'models', 'review',
          'research')   # keys whose value is an object
WORDS = ('output', 'share')                         # keys whose value is a word
SECRET = ('That address carries a password or token. Give the address without it; git '
          'signs in with your own credentials.')
SPACE = decoder.WHITESPACE
DECODE = json.JSONDecoder()
WAIT = 10.0     # seconds a write waits for another studio's to finish


def path() -> Path:
    """Where the file is: the one STUDIOS_CONFIG names, else in ~/.config."""
    named = os.environ.get('STUDIOS_CONFIG')
    if named:
        return Path(named).expanduser()
    return Path.home() / '.config' / 'studios-config.json'


def shown(where: Path) -> str:
    """A path as a person would write it: from ~ when it is in their home folder."""
    try:
        return '~/' + Path(where).relative_to(Path.home()).as_posix()
    except ValueError:
        return str(where)


USING = (f', so {PRODUCT} uses its built-in defaults for the values every studio '
         'shares, and saves none of them, until it can be read.')
REFUSED = (', so no value every studio shares can be saved until it can, and the file was '
           'left as it is.')


def _unreadable(where: Path, why: str) -> str:
    return f'{shown(where)} could not be read ({why}){USING}'


def _parsed(where: Path, text: str) -> tuple[dict, str | None]:
    try:
        found = json.loads(text)
    except ValueError:
        return {}, _unreadable(where, 'it is not valid JSON')
    if not isinstance(found, dict):
        return {}, _unreadable(where, 'it does not hold a JSON object')
    schema = found.get('schema', SCHEMA)
    if type(schema) is not int or schema != SCHEMA:
        return {}, _unreadable(where, 'it is written for a newer version of the studios')
    # Retired review data is preserved even when malformed; its reader falls back safely.
    if STRICT_GROUPS and any(key in found and not isinstance(found[key], dict)
                             for key in GROUPS if key != 'review'):
        return {}, _unreadable(where, 'a settings section is not an object')
    return found, None


def _text(where: Path) -> tuple[str | None, str | None]:
    """The file's text, or None when there is none; and why it could not be read."""
    try:
        return where.read_text(encoding='utf-8'), None
    except FileNotFoundError:
        return None, None
    except UnicodeDecodeError:
        return None, _unreadable(where, 'it is not text in UTF-8')
    except OSError as failure:
        return None, _unreadable(where, str(failure.strerror or 'it cannot be opened').lower())


def read() -> tuple[dict, str | None]:
    """What the file holds, and a sentence when it could not be used. No file is ({}, None);
    a file that cannot be used is ({}, the sentence)."""
    where = path()
    text, problem = _text(where)
    if text is None:
        return {}, problem
    return _parsed(where, text)


# --- writing -----------------------------------------------------------------------------

def _plain(value) -> bool:
    return value is None or isinstance(value, (str, bool, int, float))


def _check(changes) -> None:
    """Refuse what is not for this file: a value that is not plain, or a secret."""
    if not isinstance(changes, dict) or 'schema' in changes:
        raise WorkspaceError('Give the shared values as the studios config names them.')
    for key, value in changes.items():
        if key == 'review':
            from studio_core.review_policy import check
            try:
                check(value)
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
            continue
        if key == 'research':
            from studio_core.research_sites import check_shared
            try:
                check_shared(value)
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
            continue
        if key == 'models':
            from studio_core.model_profiles import check_changes
            try:
                check_changes(value)
            except ValueError as error:
                raise WorkspaceError(str(error)) from error
            continue
        whole = isinstance(value, dict) and all(
            isinstance(name, str) and _plain(inner) for name, inner in value.items())
        if not isinstance(key, str) or (key in GROUPS and not whole) or (
                key in WORDS and not (value is None or isinstance(value, str))) or (
                not whole and not _plain(value)):
            raise WorkspaceError(f'"{key}" cannot be written to the studios config as it is.')
    for group in ('team', 'brand'):
        address = (changes.get(group) or {}).get('repository')
        if isinstance(address, str) and ADDRESS_CHECK:
            ADDRESS_CHECK(address)


def _object(text: str, at: int) -> tuple[list, int]:
    """The members of the object whose brace is at `at`, each as (key, key_at, colon,
    value_at, value_end), and where its closing brace is. The text is known to be JSON."""
    members = []
    at = SPACE.match(text, at + 1).end()
    while text[at] != '}':
        key_at = at
        key, key_end = decoder.scanstring(text, at + 1)
        value_at = SPACE.match(text, SPACE.match(text, key_end).end() + 1).end()
        _, value_end = DECODE.raw_decode(text, value_at)
        members.append((key, key_at, text[key_end:value_at], value_at, value_end))
        at = SPACE.match(text, value_end).end()
        if text[at] == ',':
            at = SPACE.match(text, at + 1).end()
    return members, at


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _same(one, other) -> bool:
    return type(one) is type(other) and one == other


def _edits(text: str, at: int, changes: dict, current: dict) -> list:
    """What to change in the object at `at` so that it holds `changes`: (start, end, text)
    each, touching nothing else. A key given twice is changed where JSON reads it, last."""
    members, close = _object(text, at)
    last = {member[0]: member for member in members}
    edits, added = [], []
    for key, value in changes.items():
        if key not in last:
            added.append((key, value))
            continue
        _, _, _, value_at, value_end = last[key]
        held = current.get(key)
        if isinstance(value, dict) and isinstance(held, dict):
            edits.extend(_edits(text, value_at, value, held))
        elif not _same(held, value):
            edits.append((value_at, value_end, _dump(value)))
    if added:
        if members:
            _, key_at, colon, _, value_end = members[-1]
            before = text[:key_at]
            space = text[len(before.rstrip(' \t\r\n')):key_at]
            # Beside a lone member written against its brace, a comma takes a space.
            space = space or (' ' if len(members) == 1 else '')
            edits.append((value_end, value_end, ''.join(
                f',{space}{_dump(key)}{colon}{_dump(value)}' for key, value in added)))
        else:
            edits.append((close, close, ', '.join(
                f'{_dump(key)}: {_dump(value)}' for key, value in added)))
    return edits


def writable() -> None:
    """Refuse, with a sentence, while the file cannot be read: nothing may be written then."""
    problem = read()[1]
    if problem:
        raise WorkspaceError(problem.removesuffix(USING) + REFUSED)




def lock_path() -> Path:
    """The file every studio locks while it writes the studios config: beside it."""
    where = path()
    return where.with_name(where.name + '.lock')


@contextmanager
def _locked():
    """Hold the lock every studio takes to write the file, or refuse once it stays taken.
    The lock goes with the process, so one that ends never leaves it held."""
    where = lock_path()
    try:
        where.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(where, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except OSError as failure:
        raise WorkspaceError(f'{shown(path())} could not be written '
                             f'({str(failure.strerror or failure).lower()}), so it was left '
                             'as it is.')
    try:
        deadline = time.monotonic() + WAIT
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise WorkspaceError(f'Another studio is changing {shown(path())}, so '
                                         'nothing was saved. Try again in a moment.')
                time.sleep(0.05)
        yield
    finally:
        os.close(handle)


def update(changes, guard=None) -> dict:
    """Write these values into the file, merged with what it holds, and return what it then
    holds. `changes` is shaped as the file is: {"share": ..., "team": {"branch": ...}}, or is
    a function that answers them from what the file holds under the lock. `guard`, when
    given, is called with what the file holds before anything is written, and refuses by
    raising. Nothing to change is no write at all."""
    if not callable(changes):
        _check(changes)
    with _locked():
        return _update(changes, guard)


def _update(changes: dict, guard) -> dict:
    where = path()
    target = where.resolve() if where.is_symlink() else where
    text, problem = _text(target)
    found = {}
    if text is not None:
        found, problem = _parsed(where, text)
    if problem:
        raise WorkspaceError(problem.removesuffix(USING) + REFUSED)
    if guard is not None:
        guard(found)
    if callable(changes):
        changes = changes(found)
        _check(changes)
    if not changes:
        return found
    if text is None:
        written = json.dumps({'schema': SCHEMA, **changes}, indent=2, ensure_ascii=False) + '\n'
    else:
        start = SPACE.match(text, 0).end()
        wanted = changes if 'schema' in found else {'schema': SCHEMA, **changes}
        written = text
        for begin, end, put in sorted(_edits(text, start, wanted, found), reverse=True):
            written = written[:begin] + put + written[end:]
        if written == text:
            return found
    mode = target.stat().st_mode & 0o7777 if text is not None else None
    pending = target.with_name(f'.{target.name}.pending-{secrets.token_hex(4)}')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with pending.open('x', encoding='utf-8') as stream:
            os.chmod(pending, mode if mode is not None else 0o600)
            stream.write(written)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(pending, mode)
        os.replace(pending, target)
    except OSError as failure:
        raise WorkspaceError(f'{shown(where)} could not be written '
                             f'({str(failure.strerror or failure).lower()}), so it was left '
                             'as it is.')
    finally:
        pending.unlink(missing_ok=True)
    return json.loads(written)


def for_product(name, product, error, address_check, strict_groups=False):
    return fresh_module(__file__, name, {"PRODUCT": product, "WorkspaceError": error,
                        "ADDRESS_CHECK": address_check, "STRICT_GROUPS": strict_groups})


def patch_json(raw, keys, value):
    """Replace only a selected JSON value; unrelated bytes, including formatting, survive."""
    decoder = json.JSONDecoder()
    start = len(raw) - len(raw.lstrip())
    _, end = decoder.raw_decode(raw, start)
    at = start + 1
    while at < end:
        while raw[at].isspace() or raw[at] == ',':
            at += 1
        if raw[at] == '}':
            break
        key, after = decoder.raw_decode(raw, at)
        at = after
        while raw[at].isspace() or raw[at] == ':':
            at += 1
        found, after = decoder.raw_decode(raw, at)
        if key == keys[0]:
            replacement = (
                patch_json(raw[at:after], keys[1:], value)
                if len(keys) > 1
                else json.dumps(value, ensure_ascii=False)
            )
            return raw[:at] + replacement + raw[after:]
        at = after
    nested = value
    for key in reversed(keys[1:]):
        nested = {key: nested}
    prefix = ',' if json.loads(raw).keys() else ''
    return (
        raw[: end - 1]
        + prefix
        + json.dumps(keys[0])
        + ': '
        + json.dumps(nested, ensure_ascii=False)
        + raw[end - 1 :]
    )
