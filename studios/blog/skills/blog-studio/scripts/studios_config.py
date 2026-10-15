"""Optional defaults shared by the studios; local settings always take precedence."""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

KEYS = {'team': {'repository', 'branch'}, 'person': {'name'}, 'assistant': {'agent'}, 'share': None}


def path():
    return Path(
        os.environ.get('STUDIOS_CONFIG', Path.home() / '.config/studios-config.json')
    ).expanduser()


def repository(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or value.startswith('-')
        or any(c in value for c in '\r\n\x00')
    ):
        raise ValueError('Give a repository address without credentials.')
    parsed = urlsplit(value)
    if (
        (parsed.scheme in ('http', 'https') and (parsed.username or parsed.password))
        or parsed.password
        or parsed.query
        or parsed.fragment
        or '::' in value
    ):
        raise ValueError('A repository address must not contain credentials or a remote helper.')
    return value


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Repeated config key.')
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or value.get('schema', 1) != 1:
        raise ValueError('Unsupported studios config.')
    for key in ('team', 'person', 'assistant', 'brand'):
        if key in value and not isinstance(value[key], dict):
            raise ValueError('Invalid studios config section.')
    if 'repository' in value.get('team', {}):
        repository(value['team']['repository'])
    return value


def read():
    target = path()
    try:
        if target.is_symlink():
            raise ValueError('Config is a link.')
        return _decode(target.read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError, UnicodeError):
        return (
            {},
            'Shared studios defaults could not be read; this studio is using its own settings.',
        )


def _patch(raw, keys, value):
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
                _patch(raw[at:after], keys[1:], value)
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


def update(changes):
    """Explicit consent is supplied by the caller. Merge only supported leaf keys atomically."""
    if not isinstance(changes, dict) or set(changes) - KEYS.keys():
        raise ValueError('Only shared settings belong in studios config.')
    leaves = []
    for section, value in changes.items():
        if KEYS[section] is None:
            if value not in ('decision', 'asked'):
                raise ValueError('Choose sharing after each decision or when asked.')
            leaves.append(([section], value))
        else:
            if not isinstance(value, dict) or set(value) - KEYS[section]:
                raise ValueError('Unknown shared setting.')
            for key, text in value.items():
                if (
                    not isinstance(text, str)
                    or len(text) > 2000
                    or any(c in text for c in '\r\n\x00')
                ):
                    raise ValueError('Use a short shared setting without control characters.')
                if section == 'team' and key == 'repository':
                    repository(text)
                if section == 'assistant' and text not in ('codex', 'claude'):
                    raise ValueError('Choose Codex or Claude.')
                if (
                    section == 'team'
                    and key == 'branch'
                    and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/._-]*', text)
                ):
                    raise ValueError('Use a valid team branch.')
                leaves.append(([section, key], text))
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    from studio_sync.support import locked
    import studio

    with locked(target.with_name(target.name + '.lock')):
        if target.is_symlink():
            raise ValueError(
                'Shared defaults are a link; keep that file and choose a regular config file.'
            )
        try:
            raw = target.read_text(encoding='utf-8')
            _decode(raw)
        except FileNotFoundError:
            raw = '{"schema": 1}\n'
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError(
                'Shared defaults could not be updated; keep the existing file and correct it first.'
            ) from exc
        for keys, value in leaves:
            raw = _patch(raw, keys, value)
        _decode(raw)
        studio.atomic(target, raw.encode('utf-8'))
        target.chmod(0o600)
    return read()[0]
