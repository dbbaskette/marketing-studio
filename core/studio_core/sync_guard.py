"""Conservative exclusion of canonical Studio workers during repository replay."""
import json
import base64
import os
import re
import stat
from pathlib import Path

from .blog_migration import dependencies, migration_supported
from . import presentation_migration, training_migration

SYNC_WAIT = ('A Studio step is still in progress in this repository. Stop it or wait for it '
             'to finish, then share again. A stopped or interrupted step can leave a marker; '
             'if sharing still waits, reopen the Studio to recover the saved work first.')

# The refusal when the repository cannot be checked, in one place: `unchecked` adds the
# folder (relative to the repository) and the reason. Callers and tests match its first
# sentence.
UNCHECKED = 'The repository could not be checked for running Studio steps.'
UNCHECKED_NEXT = 'Check its saved worker records and folder permissions, then share again.'
# Why a folder could not be checked, each completing "In the folder <folder>, ...".
UNKNOWN_DECK = 'its Presentation Studio run record cannot be understood'
UNREADABLE = '{name} cannot be read'
LINKED_RECORDS = 'its Blog Studio worker records are linked'
ODD_RECORD = 'a Blog Studio worker record is linked or too large'
NO_STATUS = 'a Blog Studio worker record has no readable status'
BLOG_MIGRATION = 'a Blog Studio desk migration is incomplete'
BLOG_DEPENDENCY = 'a file a Blog Studio desk migration needs is missing'
BLOG_UNFINISHED = 'a Blog Studio draft is marked as migrating but has no migration record'
LINKED_CACHE = 'its work or sources folder is a link'
LARGE_CACHE = 'its work or sources folder holds too many folders to check'
TRAINING_CHAIN = 'the Training Studio update record cannot be understood'
PRESENTATION_MIGRATION = 'the Presentation Studio desk migration record cannot be verified'
TRAINING_MIGRATION = 'the Training Studio desk migration record cannot be verified'

# Training Studio's material scheduling pin (studios/training/runner/material_flow.py PIN).
MATERIAL_FLOW = {'schema': 1, 'order': 'readable-first'}


def unchecked(folder=None, reason=None) -> str:
    """The refusal sentence: what failed, the folder relative to the repository ('.' for its
    top folder) and why, when known, then what to do."""
    if folder is None or reason is None:
        return f'{UNCHECKED} {UNCHECKED_NEXT}'
    place = "the repository's top folder" if folder in ('', '.') else f'the folder {folder}'
    return f'{UNCHECKED} In {place}, {reason}. {UNCHECKED_NEXT}'


def training_written(record) -> bool:
    """Whether this is a run record the Training Studio engine writes (schemas 1 to 8, from
    its runner and conversation starts), checked as its reader (`runner/engine.py`
    `read_record`) checks each schema. It only recognises a training for the running-step
    check; it never makes a record eligible to migrate."""
    if not isinstance(record, dict) or type(record.get('schema')) is not int \
            or record['schema'] not in range(1, 9) or not isinstance(record.get('steps'), dict):
        return False
    schema, desk = record['schema'], record.get('flow') == 'desk'
    if schema == 2:
        policy = record.get('review_policy')
        if not isinstance(policy, dict) or policy.get('schema') != 1 \
                or policy.get('level') not in ('balanced', 'automatic', 'step_by_step'):
            return False
    outline = record.get('outline_first')
    outline_on = schema in (7, 8) and isinstance(outline, dict) and outline.get('schema') == 1
    flow = record.get('material_flow')
    if 'material_flow' in record and not (isinstance(flow, dict) and flow == MATERIAL_FLOW
                                         and type(flow.get('schema')) is int
                                         and desk and outline_on):
        return False
    if schema == 8:
        # Imported only where a schema needs them: research_session's own imports are
        # heavy, and the shared runner imports this module while it is itself being imported.
        from studio_core import research_sections
        if not research_sections.enabled(record):
            return False
    if schema in (6, 7, 8) and not (desk and _training_plan(record, outline_on)):
        return False
    contract = record.get('research_contract')
    contracted = isinstance(contract, dict) and contract.get('schema') == 2
    if schema == 4:
        # Runner desk records need a contract; a conversation may start without one.
        contracted = desk and (contracted or record.get('execution') == 'conversation')
    parallel = schema in (5, 7, 8) or (schema == 6 and 'research_execution' in record)
    if parallel:
        from studio_core import research_session
        if not research_session.protocol(record):
            return False
    return schema < 3 or contracted


def _training_plan(record, outline_on):
    """Training Studio's saved plan (and outline-first) workflow, as its
    `training_plan.enabled` reads it."""
    value = record.get('training_plan')
    if not isinstance(value, dict) or (record['schema'] in (7, 8) and not outline_on) \
            or (record['schema'] == 6 and 'outline_first' in record):
        return False
    if type(value.get('schema')) is not int or value['schema'] != 1:
        return False
    if 'outline_first' in record:
        from studio_core import research_quality, scope_scan
        pin = record['outline_first']
        if not isinstance(pin, dict) or type(pin.get('schema')) is not int or pin['schema'] != 1:
            return False
        if 'research_policy' in pin and not research_quality.valid_policy(pin['research_policy']):
            return False
        try:
            if pin.get('outline') is not None:
                scope_scan.checked(pin['outline'])
        except (ValueError, TypeError, KeyError, AttributeError):
            return False
    revision, approval = value.get('revision', 0), value.get('approved')
    return (type(revision) is int and revision >= 0 and (approval is None or
        isinstance(approval, dict) and isinstance(approval.get('signature'), str)
        and re.fullmatch(r'[0-9a-f]{64}', approval['signature']) is not None
        and approval.get('by') == 'page' and isinstance(approval.get('at'), str)))


def worker_in_progress(repo: Path, refusal=ValueError, *, recovering_presentation=None, recovering_training=None) -> bool:
    """Check known canonical worker records without following directory links.

    A missing marker is idle; unreadable scope or a malformed Blog Studio worker
    record is unknown and refuses replay. Output caches and Git internals are not
    candidates. Leftover markers remain busy until the existing recovery runs.
    """
    def where(path):
        # Only ever a path relative to the repository; anything else is left unnamed.
        try:
            return Path(os.path.relpath(path, repo)).as_posix() \
                if Path(path).is_relative_to(repo) else None
        except (TypeError, ValueError):
            return None

    def unknown(error, folder=None, reason=None):
        if folder is None and isinstance(error, OSError) and error.filename is not None:
            # A folder or file the walk or a check could not read names itself.
            try:
                path = Path(os.fsdecode(error.filename))
                folder, reason = path.parent, UNREADABLE.format(name=path.name)
            except (TypeError, ValueError):
                folder = reason = None
        named = where(folder) if folder is not None else None
        raise refusal(unchecked(named, reason if named is not None else None)) from error

    def present(path):
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            unknown(error, path.parent, UNREADABLE.format(name=path.name))

    def blog_busy(folder):
        for directory in (folder, folder / 'tools'):
            if not present(directory):
                continue
            if directory.is_symlink():
                unknown(ValueError('Linked worker records'), folder.parent, LINKED_RECORDS)
            try:
                for path in directory.iterdir():
                    if path.suffix != '.json' or (directory == folder and path.stem in (
                            'voice-guides', 'desk-step-times')):
                        continue
                    if path.is_symlink() or path.stat().st_size > 1_000_000:
                        unknown(ValueError('Unsupported worker record'), folder.parent, ODD_RECORD)
                    try:
                        value = json.loads(path.read_text(encoding='utf-8'))
                    except ValueError as error:
                        unknown(error, folder.parent, NO_STATUS)
                    if not isinstance(value, dict) or not isinstance(value.get('status'), str):
                        unknown(ValueError('Unreadable worker status'), folder.parent, NO_STATUS)
                    if value['status'] == 'working':
                        return True
            except OSError as error:
                unknown(error, directory.parent, UNREADABLE.format(name=directory.name))
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
            # Every record the Presentation Studio engine writes is a known deck; whether
            # it may migrate is a separate question (presentation_migration.supported).
            if not presentation_migration.written(deck):
                unknown(ValueError('Unsupported Presentation Studio worker metadata'),
                        folder, UNKNOWN_DECK)
            return True
        if named_record(deck, (1, 2, 3)) and known_run(deck, (1, 2, 3)) \
                and isinstance(deck.get('form'), dict) \
                and deck.get('route') in ('idea', 'document', 'existing'):
            return True
        run = small_record(folder / '.training-studio/run.json')
        session = small_record(folder / '.training-studio/session.json')
        if not training_written(run) or not isinstance(run.get('agent'), str) \
                or not run['agent'].strip() or not named_record(session, (1,)):
            return False
        shape = {'levels': list, 'sizing': dict, 'stage': str, 'settings': dict,
                 'unavailable': dict, 'pins': dict, 'artifacts': dict, 'exports': dict,
                 'decisions': list, 'events': list}
        return (all(isinstance(session.get(key), kind) for key, kind in shape.items())
                and all(key in session['settings']
                        for key in ('deck_target', 'brand', 'brief_kind', 'stages')))

    def blog_record(folder):
        # A desk migration record that says it is Blog Studio's, with no Presentation Studio
        # receipt claiming the folder: blog_migration verifies it in full, and
        # presentation_busy leaves it alone. Any other record is read as before.
        value = small_record(folder / 'desk/migration.json')
        return isinstance(value, dict) and value.get('product') == 'Blog Studio'

    def blog_migration(folder):
        desk = folder / 'desk'
        if present(desk / 'migration.pending.json'):
            return True
        marker = desk / 'migration.json'
        if present(marker):
            value = small_record(marker)
            if blog_record(folder):
                # A Blog Studio migration record is verified whatever sits beside it: in a
                # Blog Studio team repository every blog also holds a run.json driver record.
                if present(desk / 'migration-origin.json'):
                    # A Presentation Studio receipt beside a Blog Studio record: neither can
                    # be told from the other.
                    unknown(ValueError('Two products\' migration records'), folder, BLOG_MIGRATION)
            elif present(folder / 'run.json') or present(desk / 'migration-origin.json') \
                    or (isinstance(value, dict) and value.get('product') == 'Presentation Studio'):
                return False
            draft = small_record(desk / 'draft.json')
            if not migration_supported(value, small_bytes(folder / 'session.json'),
                                       small_bytes(folder / 'derived/blog-run.json'), draft, folder.name):
                unknown(ValueError('Incomplete Blog Studio migration'), folder, BLOG_MIGRATION)
            for name in dependencies(value, draft):
                path = folder / name
                if not present(path) or path.is_symlink() or path.parent.is_symlink() or not path.is_file():
                    unknown(ValueError('Missing Blog Studio migration dependency'), folder, BLOG_DEPENDENCY)
        elif present(desk / 'draft.json'):
            draft = small_record(desk / 'draft.json')
            if isinstance(draft, dict) and draft.get('unfinished_migration'):
                unknown(ValueError('Missing Blog Studio migration record'), folder, BLOG_UNFINISHED)
        return False

    def migration_in_cache(cache):
        # Recognized items need not have both caches. Inspect the entry once;
        # absent caches contain no migration and linked roots are never traversed.
        try:
            info = cache.lstat()
        except FileNotFoundError:
            return False
        except OSError as error:
            unknown(error, cache.parent, UNREADABLE.format(name=cache.name))
        if stat.S_ISLNK(info.st_mode):
            unknown(ValueError('Linked Studio cache'), cache.parent, LINKED_CACHE)
        if not stat.S_ISDIR(info.st_mode):
            return False
        # Only Blog Studio's fixed migration records override structural cache
        # pruning. Bound this uncertainty check; never silently skip an oversized
        # or unreadable candidate tree and declare replay safe.
        if not present(cache):
            return False
        if cache.is_symlink():
            unknown(ValueError('Linked Studio cache'), cache.parent, LINKED_CACHE)
        count = 0
        for folder, directories, _ in os.walk(cache, followlinks=False, onerror=unknown):
            count += 1
            if count > 2000:
                unknown(ValueError('Migration scope too large'), cache.parent, LARGE_CACHE)
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
        workspace = '@training-workspace/hub.json'
        fields = {'schema', 'product', 'id', 'expected', 'originals', 'after', 'before_workspace',
                  'index_before', 'index_prepared', 'head_before'}
        if not (isinstance(value, dict) and set(value) == fields and type(value.get('schema')) is int and value['schema'] == 1
                and value.get('product') == 'Training Studio' and value.get('id') == folder.name
                and isinstance(value.get('expected'), str) and value['expected'].startswith('tm1.')
                and isinstance(value.get('after'), dict) and set(value['after']) ==
                    {*training_migration.WRITES, workspace}
                and isinstance(value['index_before'], str) and isinstance(value['index_prepared'], str)
                and isinstance(value['head_before'], dict) and set(value['head_before']) == {*training_migration.WRITES, workspace}
                and all(value['head_before'][name] == '' for name in training_migration.WRITES)):
            return False
        try:
            head = value['head_before'][workspace]
            if not isinstance(head, str) or head and not re.fullmatch(r'100(?:644|755) blob [a-f0-9]{40,64}\t[^\0]+\0', head):
                return False
            if value['originals'] != {name: training_migration.digest(small_bytes(folder / name))
                                      for name in (training_migration.SESSION, training_migration.RUN)}:
                return False
            before_workspace = base64.b64decode(value['before_workspace'], validate=True)
            if len(before_workspace) > 1_000_000 or not isinstance(json.loads(before_workspace), dict):
                return False
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
        if present(origin) or (present(marker) and not blog_record(folder) and (present(folder / 'run.json') or
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
                unknown(error, folder, PRESENTATION_MIGRATION)
        return False

    def training_busy(folder):
        pending = folder / training_migration.PENDING
        record = small_record(folder / training_migration.RUN)
        if isinstance(record, dict):
            drafts = record.get('drafts', {})
            if not isinstance(drafts, dict) or not training_migration.update_chain_supported(drafts.get('update_chain', {})):
                unknown(ValueError('Unknown Training Studio update chain'), folder, TRAINING_CHAIN)
            if drafts.get('update_chain', {}).get('status') == 'working':
                return True
        if pending == recovering_presentation and present(folder / 'run.json'):
            value = small_record(pending, 8_000_000)
            fields = {'schema', 'expected', 'original', 'after', 'before_workspace', 'index_before'}
            if isinstance(value, dict) and set(value) in (fields, fields | {'shared', 'index_prepared'}, fields | {'shared', 'index_prepared', 'head_before'}) and str(value.get('expected', '')).startswith('pm1.'):
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
                unknown(error, folder, TRAINING_MIGRATION)
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
