"""Conservative exclusion of canonical Studio workers during repository replay."""
import json
import base64
import os
import stat
from pathlib import Path

from .blog_migration import dependencies, migration_supported
from . import presentation_migration, training_migration

SYNC_WAIT = ('A Studio step is still in progress in this repository. Stop it or wait for it '
             'to finish, then share again. A stopped or interrupted step can leave a marker; '
             'if sharing still waits, reopen the Studio to recover the saved work first.')


def worker_in_progress(repo: Path, refusal=ValueError, *, recovering_presentation=None, recovering_training=None) -> bool:
    """Check known canonical worker records without following directory links.

    A missing marker is idle; unreadable scope or a malformed Blog Studio worker
    record is unknown and refuses replay. Output caches and Git internals are not
    candidates. Leftover markers remain busy until the existing recovery runs.
    """
    def unknown(error):
        raise refusal('The repository could not be checked for running Studio steps. '
                      'Check its saved worker records and folder permissions, then '
                      'share again.') from error

    def present(path):
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            unknown(error)

    def blog_busy(folder):
        for directory in (folder, folder / 'tools'):
            if not present(directory):
                continue
            if directory.is_symlink():
                unknown(ValueError('Linked worker records'))
            try:
                for path in directory.iterdir():
                    if path.suffix != '.json' or (directory == folder and path.stem in (
                            'voice-guides', 'desk-step-times')):
                        continue
                    if path.is_symlink() or path.stat().st_size > 1_000_000:
                        unknown(ValueError('Unsupported worker record'))
                    value = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(value, dict) or not isinstance(value.get('status'), str):
                        unknown(ValueError('Unreadable worker status'))
                    if value['status'] == 'working':
                        return True
            except (OSError, ValueError) as error:
                unknown(error)
        return False

    def small_bytes(path, limit=1_000_000):
        try:
            # Metadata reached through a link cannot prove this folder owns caches.
            # Stop at the scanned root; ancestors outside it are not scan evidence.
            for candidate in (path, *path.parents):
                if candidate.is_symlink():
                    return None
                if candidate == repo:
                    break
            with path.open('rb') as handle:
                text = handle.read(limit + 1)
            return text if len(text) <= limit else None
        except (OSError, ValueError):
            return None

    def small_record(path, limit=1_000_000):
        raw = small_bytes(path, limit)
        try:
            return json.loads(raw) if raw is not None else None
        except (ValueError, UnicodeError):
            return None

    def named_record(record, schemas):
        return (isinstance(record, dict) and type(record.get('schema')) is int
                and record['schema'] in schemas
                and all(isinstance(record.get(key), str) and record[key].strip()
                        for key in ('id', 'title')))

    def known_run(record, schemas):
        if not isinstance(record, dict) or type(record.get('schema')) is not int \
                or record['schema'] not in schemas or not isinstance(record.get('steps'), dict):
            return False
        if record['schema'] == 2:
            policy = record.get('review_policy')
            if not isinstance(policy, dict) or policy.get('schema') != 1 \
                    or policy.get('level') not in ('balanced', 'automatic', 'step_by_step'):
                return False
        if record['schema'] in (3, 4):
            contract = record.get('research_contract')
            if not isinstance(contract, dict) or contract.get('schema') != 2:
                return False
        return record['schema'] != 4 or record.get('flow') == 'desk'

    def item_has_caches(folder):
        # work/sources are legal workspace and container names. A filename alone,
        # or an unknown/partial record, never proves an output/source cache.
        deck = small_record(folder / 'run.json')
        if isinstance(deck, dict) and deck.get('route') in ('scratch', 'document', 'existing'):
            if not presentation_migration.supported(deck):
                unknown(ValueError('Unsupported Presentation Studio worker metadata'))
            return True
        if named_record(deck, (1, 2, 3)) and known_run(deck, (1, 2, 3)) \
                and isinstance(deck.get('form'), dict) \
                and deck.get('route') in ('idea', 'document', 'existing'):
            return True
        run = small_record(folder / '.training-studio/run.json')
        session = small_record(folder / '.training-studio/session.json')
        if not known_run(run, (1, 2, 3, 4)) or not isinstance(run.get('agent'), str) \
                or not run['agent'].strip() or not named_record(session, (1,)):
            return False
        shape = {'levels': list, 'sizing': dict, 'stage': str, 'settings': dict,
                 'unavailable': dict, 'pins': dict, 'artifacts': dict, 'exports': dict,
                 'decisions': list, 'events': list}
        return (all(isinstance(session.get(key), kind) for key, kind in shape.items())
                and all(key in session['settings']
                        for key in ('deck_target', 'brand', 'brief_kind', 'stages')))

    def blog_migration(folder):
        desk = folder / 'desk'
        if present(desk / 'migration.pending.json'):
            return True
        marker = desk / 'migration.json'
        if present(marker):
            value = small_record(marker)
            if present(folder / 'run.json') or present(desk / 'migration-origin.json') \
                    or (isinstance(value, dict) and value.get('product') == 'Presentation Studio'):
                return False
            draft = small_record(desk / 'draft.json')
            if not migration_supported(value, small_bytes(folder / 'session.json'),
                                       small_bytes(folder / 'derived/blog-run.json'), draft, folder.name):
                unknown(ValueError('Incomplete Blog Studio migration'))
            for name in dependencies(value, draft):
                path = folder / name
                if not present(path) or path.is_symlink() or path.parent.is_symlink() or not path.is_file():
                    unknown(ValueError('Missing Blog Studio migration dependency'))
        elif present(desk / 'draft.json'):
            draft = small_record(desk / 'draft.json')
            if isinstance(draft, dict) and draft.get('unfinished_migration'):
                unknown(ValueError('Missing Blog Studio migration record'))
        return False

    def migration_in_cache(cache):
        # Recognized items need not have both caches. Inspect the entry once;
        # absent caches contain no migration and linked roots are never traversed.
        try:
            info = cache.lstat()
        except FileNotFoundError:
            return False
        except OSError as error:
            unknown(error)
        if stat.S_ISLNK(info.st_mode):
            unknown(ValueError('Linked Studio cache'))
        if not stat.S_ISDIR(info.st_mode):
            return False
        # Only Blog Studio's fixed migration records override structural cache
        # pruning. Bound this uncertainty check; never silently skip an oversized
        # or unreadable candidate tree and declare replay safe.
        if not present(cache):
            return False
        if cache.is_symlink():
            unknown(ValueError('Linked Studio cache'))
        count = 0
        for folder, directories, _ in os.walk(cache, followlinks=False, onerror=unknown):
            count += 1
            if count > 2000:
                unknown(ValueError('Migration scope too large'))
            if blog_migration(Path(folder)):
                return True
            if training_busy(Path(folder)):
                return True
            if presentation_busy(Path(folder)):
                return True
            if any(present(Path(folder) / name) for name in ('.harness-slides/design/.lock', '.studio-research/lock')):
                return True
            directories[:] = [name for name in directories if name != '.git'
                              and not (Path(folder) / name).is_symlink()]
        return False

    def training_recovery(folder, pending):
        value = small_record(pending, 8_000_000)
        if not (isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1
                and value.get('product') == 'Training Studio' and value.get('id') == folder.name
                and isinstance(value.get('expected'), str) and value['expected'].startswith('tm1.')
                and isinstance(value.get('after'), dict) and set(value['after']) ==
                    {*training_migration.WRITES, '@training-workspace/hub.json'}):
            return False
        try:
            after = {name: base64.b64decode(data, validate=True) for name, data in value['after'].items()}
            if any(len(data) > 1_000_000 for data in after.values()):
                return False
            origin = json.loads(after[training_migration.ORIGIN])
            training_migration.validated(origin, json.loads(after[training_migration.DESK_SESSION]),
                json.loads(after[training_migration.DESK_RUN]), small_bytes(folder / training_migration.SESSION),
                small_bytes(folder / training_migration.RUN), folder.name)
            return origin['expected'] == value['expected']
        except (ValueError, TypeError, KeyError):
            return False

    def presentation_busy(folder):
        pending = folder / presentation_migration.PENDING
        if pending == recovering_training and present(folder / training_migration.RUN):
            if not training_recovery(folder, pending):
                return True
            return False  # verified product/id; domain verifies the exact locked journal
        if present(pending) and pending != recovering_presentation:
            return True
        marker, origin = folder / presentation_migration.RECORD, folder / presentation_migration.ORIGIN
        value = small_record(marker)
        if pending == recovering_presentation:
            return False  # explicit locked recovery validates the exact journal itself
        if present(origin) or (present(marker) and (present(folder / 'run.json') or
                isinstance(value, dict) and value.get('product') == 'Presentation Studio')):
            try:
                value = small_record(marker)
                presentation_migration.validated(value, small_bytes(folder / 'run.json'),
                                                  folder.name, small_record(origin))
                for name in value['required']:
                    path = folder / name
                    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents) if p != folder.parent):
                        raise ValueError('Missing saved Presentation Studio dependency')
                    with path.open('rb') as stream:
                        stream.read(1)
                    presentation_migration.shared_material(name, small_bytes(path))
            except (ValueError, TypeError, KeyError, OSError) as error:
                unknown(error)
        return False

    def training_busy(folder):
        pending = folder / training_migration.PENDING
        record = small_record(folder / training_migration.RUN)
        if isinstance(record, dict):
            drafts = record.get('drafts', {})
            if not isinstance(drafts, dict) or not training_migration.update_chain_supported(drafts.get('update_chain', {})):
                unknown(ValueError('Unknown Training Studio update chain'))
            if drafts.get('update_chain', {}).get('status') == 'working':
                return True
        if pending == recovering_presentation and present(folder / 'run.json'):
            value = small_record(pending)
            if isinstance(value, dict) and set(value) == {'schema', 'expected', 'original', 'after', 'before_workspace', 'index_before'} and str(value.get('expected', '')).startswith('pm1.'):
                return False  # its exact product format is validated under the caller lock
            return True
        if present(pending) and pending != recovering_training:
            return True
        if pending == recovering_training:
            return not training_recovery(folder, pending)
        if any(present(folder / name) for name in training_migration.WRITES):
            try:
                origin = small_record(folder / training_migration.ORIGIN)
                session, record = training_migration.validated(origin,
                    small_record(folder / training_migration.DESK_SESSION),
                    small_record(folder / training_migration.DESK_RUN),
                    small_bytes(folder / training_migration.SESSION),
                    small_bytes(folder / training_migration.RUN), folder.name)
                training_migration.shared_inputs(origin, lambda name: small_bytes(folder / name, training_migration.input_limit(name)), session)
                if record.get('drafts', {}).get('update_chain', {}).get('status') == 'working':
                    return True
            except (ValueError, TypeError, KeyError, OSError) as error:
                unknown(error)
        return False

    for folder, directories, _ in os.walk(repo, followlinks=False, onerror=unknown):
        here = Path(folder)
        if training_busy(here):
            return True
        if presentation_busy(here):
            return True
        if blog_migration(here):
            return True
        if any(present(here / name) for name in ('work/step.lock', '.training-studio/step.lock',
                'work/.harness-slides/design/.lock', '.studio-research/lock')):
            return True
        if present(here / '.blog-runs') and blog_busy(here / '.blog-runs'):
            return True
        caches = {'work', 'sources'} if item_has_caches(here) else set()
        if any(migration_in_cache(here / name) for name in caches):
            return True
        directories[:] = [name for name in directories
                          if name not in {'.git', '.training-studio', '.presentation-studio',
                                          '.blog-runs'} | caches
                          and not (here / name).is_symlink()]
    return False
