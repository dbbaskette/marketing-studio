"""The single source of shared studios settings, with lossless writes and local migration."""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

KEYS = {
    'team': {'repository', 'branch'},
    'person': {'name'},
    'assistant': {'agent', 'model', 'effort'},
    'brand': {'repository', 'release', 'brand', 'variant'},
    'output': None,
    'share': None,
}


def check_brand_repository(value):
    if value in (None, ''):
        return None
    value = repository(value).strip()
    if len(value) > 2000 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Give the brand skill repository as one https or ssh address.')
    if not re.match(r'^(https?://|ssh://|[\w.-]+@[\w.-]+:)', value):
        if not Path(value).expanduser().is_absolute():
            raise ValueError('Use an https or ssh repository address, or an absolute folder path.')
    return value


def check_brand_release(value, repository=None):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[\w][\w.+-]{0,99}', value) or '..' in value:
        raise ValueError('Give a release tag such as v1.4.0, or leave it empty for the newest.')
    if not repository:
        raise ValueError('Give the brand skill repository before choosing a release.')
    return value


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
    if (
        not isinstance(value, dict)
        or type(value.get('schema', 1)) is not int
        or value.get('schema', 1) != 1
    ):
        raise ValueError('Unsupported studios config.')
    for key in ('team', 'person', 'assistant', 'brand'):
        if key in value and not isinstance(value[key], dict):
            raise ValueError('Invalid studios config section.')
    if 'repository' in value.get('team', {}):
        if value['team']['repository'] not in (None, ''):
            repository(value['team']['repository'])
    brand = value.get('brand', {})
    address = check_brand_repository(brand.get('repository'))
    check_brand_release(brand.get('release'), address)
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
            'Shared studios settings could not be read; this studio is using built-in defaults.',
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


def update(changes, missing_only=False, expected=None):
    """Saving Settings is consent. Merge only changed members, or absent legacy values."""
    if not isinstance(changes, dict) or set(changes) - KEYS.keys():
        raise ValueError('Only shared settings belong in studios config.')
    leaves = []
    for section, value in changes.items():
        if KEYS[section] is None:
            if section == 'share' and value not in ('decision', 'asked', None):
                raise ValueError('Choose sharing after each decision or when asked.')
            if value is not None and (not isinstance(value, str) or len(value) > 2000):
                raise ValueError('Use a short shared setting.')
            leaves.append(([section], value))
        else:
            if not isinstance(value, dict) or set(value) - KEYS[section]:
                raise ValueError('Unknown shared setting.')
            for key, text in value.items():
                if text is not None and (
                    not isinstance(text, str)
                    or len(text) > 2000
                    or any(c in text for c in '\r\n\x00')
                ):
                    raise ValueError('Use a short shared setting without control characters.')
                if section == 'team' and key == 'repository' and text not in (None, ''):
                    repository(text)
                if (
                    section == 'assistant'
                    and key == 'agent'
                    and text not in ('codex', 'claude', None)
                ):
                    raise ValueError('Choose Codex or Claude.')
                if (
                    section == 'team'
                    and key == 'branch'
                    and text is not None
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
                'Shared settings are a link; keep that file and choose a regular config file.'
            )
        try:
            raw = target.read_text(encoding='utf-8')
            existing = _decode(raw)
        except FileNotFoundError:
            raw = '{"schema": 1}\n'
            existing = {}
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError(
                'Shared settings could not be updated; keep the existing file and correct it first.'
            ) from exc
        original = raw
        for section, value in (expected or {}).items():
            current = existing.get(section)
            if isinstance(value, dict):
                matches = isinstance(current, dict) or current is None
                matches = matches and all(
                    (current or {}).get(key) == member for key, member in value.items()
                )
            else:
                matches = current == value
            if not matches:
                raise ValueError('Shared settings changed in another studio. Reload before saving.')
        for keys, value in leaves:
            current = existing
            for key in keys[:-1]:
                current = current.get(key, {})
            if keys[-1] in current and (missing_only or current[keys[-1]] == value):
                continue
            raw = _patch(raw, keys, value)
        _decode(raw)
        if raw != original:
            studio.atomic(target, raw.encode('utf-8'))
            target.chmod(0o600)
    return read()[0]


def migrate(root=None):
    """Copy missing legacy preferences first, then remove local copies. Safe to retry."""
    from studio_sync.support import data_root, locked
    import studio

    notice_path = data_root() / 'config-migration.json'
    with locked(data_root() / 'config-migration.lock'):
        sources = []
        if root is not None:
            sources += [
                (
                    Path(root) / '.blog-run-settings.json',
                    'defaults',
                    {
                        'engine': ('assistant', 'agent'),
                        'author': ('person', 'name'),
                        'model': ('assistant', 'model'),
                        'effort': ('assistant', 'effort'),
                        'output': ('output',),
                    },
                ),
                (Path(root) / '.team-sync.json', None, {'share': ('share',)}),
            ]
        sources += [
            (
                data_root() / 'brand.json',
                None,
                {key: ('brand', key) for key in ('repository', 'release', 'brand', 'variant')},
            ),
            (
                data_root() / 'workspace.json',
                None,
                {
                    'address': ('team', 'repository'),
                    'branch': ('team', 'branch'),
                    'share': ('share',),
                },
            ),
        ]
        changes, cleanups, kept = {}, [], []
        current, problem = read()
        for source, section, mapping in sources:
            if not source.is_file():
                continue
            try:
                if source.is_symlink():
                    raise ValueError('Legacy settings are a link.')
                original = source.read_bytes()
                saved = json.loads(original)
                if not isinstance(saved, dict) or saved.get('schema', 1) != 1:
                    raise ValueError('Legacy settings use an unsupported schema.')
                values = saved.get(section, {}) if section else saved
                if not isinstance(values, dict):
                    raise ValueError('Legacy settings are not an object.')
                selected = {key: value for key, value in values.items() if key in mapping}
                if not selected:
                    continue
                for key, value in selected.items():
                    destination = mapping[key]
                    existing = current
                    for member in destination[:-1]:
                        existing = existing.get(member, {})
                    if destination[-1] in existing and existing[destination[-1]] != value:
                        kept.append('.'.join(destination))
                    if len(destination) == 1:
                        changes.setdefault(destination[0], value)
                    else:
                        changes.setdefault(destination[0], {}).setdefault(destination[1], value)
                    values.pop(key)
                cleanups.append((source, saved, original))
            except (OSError, ValueError, TypeError, AttributeError):
                problem = (
                    problem
                    or 'Legacy shared settings could not be migrated; existing shared values are kept.'
                )
        if cleanups and not problem:
            try:
                shared = update(changes, missing_only=True)
                for section, value in changes.items():
                    if isinstance(value, dict):
                        kept.extend(
                            section + '.' + key
                            for key, member in value.items()
                            if shared.get(section, {}).get(key) != member
                        )
                    elif shared.get(section) != value:
                        kept.append(section)
                for source, saved, original in cleanups:
                    if source.read_bytes() != original:
                        raise ValueError('Local settings changed during migration. Retry shortly.')
                    studio.write_json(source, saved)
                message = 'Moved this studio’s shared settings into studios-config.json.'
                if kept:
                    message += (
                        ' Existing shared values were kept for '
                        + ', '.join(sorted(set(kept)))
                        + '.'
                    )
                studio.write_json(notice_path, {'notice': message})
            except (OSError, ValueError):
                problem = 'Shared settings migration could not finish. Existing shared values were kept; correct studios-config.json and retry.'
        notice = None
        if notice_path.is_file():
            try:
                notice = studio.read_json(notice_path).get('notice')
            except (OSError, ValueError, AttributeError):
                pass
        return notice, problem
