"""Local brand choice and page-driven installation; blogs retain their own contract."""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
import tempfile
import threading
import time

import studio
import studios_config
from studio_brand import brand, companion, source, settings
from studio_sync.support import data_root, locked

_CACHE = {}
_CACHE_LOCK = threading.Lock()
_JOB = None
_JOB_LOCK = threading.Lock()


def home():
    return Path.home()


def _path():
    return data_root() / 'brand.json'


def _read():
    notice, migration_problem = studios_config.migrate()
    shared, problem = studios_config.read()
    try:
        value = studio.read_json(_path()) if _path().is_file() else {}
        if not isinstance(value, dict):
            raise ValueError('Invalid local brand settings.')
        # checked is an observation about a release, not another preference.
        preferences = shared.get('brand', {})
        value['shared_before'] = {key: preferences.get(key) for key in ('repository', 'release')}
        value.update({key: preferences.get(key) or '' for key in ('repository', 'release')})
        checked = value.get('checked') or {}
        selection = studio.digest(json.dumps([value['repository'], value['release']]).encode())
        if checked.get('selection') != selection:
            value.pop('checked', None)
        value['problem'] = problem or migration_problem
        value['migration_notice'] = notice
        return value
    except (OSError, ValueError):
        return {'problem': 'Brand settings could not be read. Check and save them again.'}


def _save(value):
    private = {
        key: member
        for key, member in value.items()
        if key not in ('repository', 'release', 'problem', 'migration_notice', 'shared_before')
    }
    # Failed migration must not lose legacy shared values during a local skill choice.
    previous = studio.read_json(_path()) if _path().is_file() else {}
    private.update(
        {
            key: member
            for key, member in previous.items()
            if key in ('repository', 'release', 'brand', 'variant')
        }
    )
    studio.write_json(_path(), private)
    _path().chmod(0o600)


def installed(refresh=False):
    key = (str(home()), str(brand.locations(home())))
    with _CACHE_LOCK:
        found = _CACHE.get(key)
        if not refresh and found and time.monotonic() - found[0] < 300:
            return found[1]
        result = brand.found(home=home())
        _CACHE[key] = (time.monotonic(), result)
        return result


def status(refresh=False):
    kept = _read()
    skills = installed(refresh)
    chosen = next((row for row in skills if row['runtime'] == kept.get('runtime')), None)
    problem = kept.get('problem')
    if kept.get('runtime') and chosen is None:
        problem = 'The selected brand skill is no longer installed. Choose one in Settings.'
    elif not kept.get('runtime') and skills:
        chosen = skills[0]
    return {
        **kept,
        'repository': kept.get('repository', ''),
        'release': kept.get('release', ''),
        'runtime': chosen['runtime'] if chosen else '',
        'skills': [{**row, 'chosen': row == chosen} for row in skills],
        'brands': chosen['brands'] if chosen else [],
        'name': chosen['name'] if chosen else None,
        'version': chosen['version'] if chosen else None,
        'problem': problem,
        'job': dict(_JOB or {}),
        'checked': kept.get('checked'),
        'shared_before': kept.get('shared_before', {'repository': None, 'release': None}),
    }


def defaults(found=None):
    import studios_config

    shared, _ = studios_config.read()
    preferred = shared.get('brand', {})
    if not preferred.get('brand'):
        return {'brand': '', 'variant': ''}
    found = found or status()
    chosen = next((row for row in found['brands'] if row['brand'] == preferred['brand']), None)
    if not chosen:
        return {'brand': '', 'variant': ''}
    variant = preferred.get('variant')
    return {
        'brand': chosen['brand'],
        'variant': variant if variant in chosen['variants'] else chosen['variants'][0],
    }


@contextmanager
def using(quiet=False):
    """Shared by writing/export jobs; an installer needs exclusive use of this computer."""
    path = data_root() / 'brand-use.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            if quiet:
                yield False
                return
            raise ValueError(
                'The brand skill is being installed. Wait until it finishes.'
            ) from None
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def configure(data):
    global _JOB
    with using():
        _configure(data)
        _JOB = None
    return status()


def _configure(data):
    data = dict(data)
    before = data.pop('shared_before', None)
    if set(data) not in ({'repository', 'release'}, {'runtime'}):
        raise ValueError('Save either the brand repository and release or an installed skill.')
    with locked(_path().with_suffix('.lock')):
        previous = _read()
        previous.pop('problem', None)
        if 'runtime' in data:
            runtime = data['runtime']
            if runtime and runtime not in {row['runtime'] for row in installed(refresh=True)}:
                raise ValueError('Choose an installed brand skill from the list.')
            previous['runtime'] = runtime
        else:
            repository = settings.check_repository(data['repository'])
            release = settings.check_release(data['release'], repository)
            checked = source.check(repository, release, home()) if repository else {}
            current, _ = studios_config.read()
            previous_brand = current.get('brand', {})
            if before is None:
                before = {key: previous_brand.get(key) for key in ('repository', 'release')}
            if not isinstance(before, dict) or set(before) != {'repository', 'release'}:
                raise ValueError('Reload the brand settings before saving.')
            values = {
                'repository': checked.get('repository', ''),
                'release': checked.get('release') or '',
            }
            changes = {
                key: value for key, value in values.items() if (before.get(key) or '') != value
            }
            studios_config.update({'brand': changes} if changes else {}, expected={'brand': before})
            previous.update(
                checked={
                    **checked['chosen'],
                    'selection': studio.digest(
                        json.dumps([values['repository'], values['release']]).encode()
                    ),
                }
                if checked
                else None,
            )
        _save(previous)


def _companions():
    found = {}
    for name in ('harness-research', 'harness-slides'):
        for folder in companion.locations(
            name.upper().replace('-', '_') + '_RUNTIME',
            name,
            name.replace('-', ' ').title(),
            home=home(),
        ):
            script = folder / 'scripts' / (name + '.mjs')
            if script.is_file():
                try:
                    code, out, _ = companion.run_command(
                        ['node', str(script), 'version'], None, 10, name
                    )
                    version = re.search(r'\b(\d+\.\d+\.\d+)\s*$', out.strip())
                    if code == 0 and version:
                        found[name] = version[1]
                except ValueError:
                    pass
                break
    return found


def install(data):
    global _JOB
    if set(data) != {'confirmed', 'repository', 'tag', 'commit'} or data['confirmed'] is not True:
        raise ValueError('Confirm the displayed brand repository, release and commit first.')
    with _JOB_LOCK:
        if _JOB and _JOB.get('status') == 'working':
            raise ValueError('A brand skill installation is already running.')
        kept = _read()
        chosen = kept.get('checked') or {}
        if (data['repository'], data['tag'], data['commit']) != (
            kept.get('repository'),
            chosen.get('tag'),
            chosen.get('commit'),
        ):
            raise ValueError('The brand release changed. Check and save it before installing.')
        lock_path = data_root() / 'brand-use.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lease = lock_path.open('a')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise ValueError(
                'A blog is working on this computer. Pause it before installing.'
            ) from None
        # The stream stays locked in the background until installation ends.
        _JOB = {'status': 'working', 'message': 'Installing the brand skill…'}
        thread = threading.Thread(target=_install, args=(dict(kept), lease), daemon=True)
        try:
            thread.start()
        except Exception:
            lease.close()
            _JOB = None
            raise
    return status()


def _install(kept, lease):
    global _JOB
    try:
        chosen = kept['checked']
        checked = source.check(kept['repository'], chosen['tag'], home())
        if checked['chosen']['commit'] != chosen['commit']:
            raise ValueError('The release tag moved. Check and save it again before installing.')
        before = _companions()
        old = status()
        with tempfile.TemporaryDirectory(prefix='blog-brand-install-') as temporary:
            folder, _ = source.fetch(
                kept['repository'], chosen['tag'], chosen['commit'], Path(temporary)
            )
            for name, version in source.bootstraps(folder).items():
                if name in source.SKIPPED:
                    continue
                if source.order(before.get(name)) < source.order(version):
                    raise ValueError(
                        f'This installer would install or replace {name} with {version}. '
                        'Install a compatible companion yourself, then try again. Nothing was run.'
                    )
            code, late, _ = source.install(folder, home(), 900)
            if code or late:
                raise ValueError(
                    'The brand installer timed out. Check the installed skill before retrying.'
                    if late
                    else 'The brand installer failed. Check the installed skill before retrying.'
                )
        skills = installed(refresh=True)
        matches = [
            row
            for row in skills
            if row['version'] == chosen['version']
            and (not old['name'] or row['name'] == old['name'])
        ]
        with locked(_path().with_suffix('.lock')):
            current = _read()
            if len(matches) == 1 and current.get('runtime') == kept.get('runtime'):
                current['runtime'] = matches[0]['runtime']
                _save(current)
        changed = before != _companions()
        _JOB = {
            'status': 'complete',
            'message': 'Brand installation finished. '
            + (
                'Companion versions changed; check this computer before continuing.'
                if changed
                else 'New blogs can use the installed skill.'
            ),
        }
    except Exception as exc:
        _JOB = {
            'status': 'failed',
            'message': str(exc)[:500]
            if isinstance(exc, ValueError)
            else 'Brand installation failed. Check this computer before retrying.',
        }
    finally:
        fcntl.flock(lease, fcntl.LOCK_UN)
        lease.close()


def snapshot(brand_id, variant=''):
    """Resolve only an explicit identity; keep guides, without local runtime paths."""
    if not isinstance(brand_id, str) or not isinstance(variant, str):
        raise ValueError('Choose a listed brand and variant.')
    if not brand_id:
        if variant:
            raise ValueError('Choose a brand before its variant.')
        return None
    with using():
        found = status()
        if found['problem']:
            raise ValueError(found['problem'])
        selected = next((row for row in found['brands'] if row['brand'] == brand_id), None)
        if selected and not variant:
            variant = selected['variants'][0]
        if not selected or variant not in selected['variants']:
            raise ValueError('Choose a brand and variant offered by the selected brand skill.')
        with tempfile.TemporaryDirectory(prefix='blog-brand-contract-') as temporary:
            exported = brand.Brand(runtime=Path(found['runtime'])).export(
                Path(temporary) / 'contract', brand_id, variant
            )
            documents = {
                name: Path(path).read_text(encoding='utf-8') for name, path in exported.items()
            }
            if sum(map(len, documents.values())) > 100_000:
                raise ValueError('The brand contract is too large. Use a focused blog contract.')
            json.loads(documents['contract'])
            return {
                'skill': found['name'],
                'version': found['version'],
                'brand': brand_id,
                'variant': variant,
                **documents,
            }
