"""Explicit, additive migration of supported unfinished Blog Studio materials.

The old session and run remain immutable. Only this fixed desk format is written;
the pending journal is also an exclusion marker for workers and repository replay.
"""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re

import studio
from studio_core.blog_migration import (
    WRITES,
    dependencies,
    migration_supported,
    run_supported,
    session_supported,
)

META = 'migration.json'
JOURNAL = 'migration.pending.json'
MAX_FILES = 2000
MAX_BYTES = 32 * 1024 * 1024
CHANGED = 'This blog or its inputs changed. Preview Open on the desk again before applying.'
REFUSAL = 'Your saved flow remains available. No writing or approval has changed.'
PENDING = 'Opening this blog on the desk was interrupted. Repeat desk migrate with its preview token to recover before continuing or sharing.'


def _json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _fixed(directory, name):
    path = directory / 'desk' / name
    if directory.is_symlink() or path.parent.is_symlink() or path.is_symlink():
        raise ValueError('Blog Studio migration cannot use linked desk records.')
    return path


def pending(root, ident):
    directory = studio.inside(root, 'articles', studio.identifier(ident))
    path = directory / 'desk' / JOURNAL
    return os.path.lexists(path) or (directory / 'desk').is_symlink()


def metadata(directory):
    """Recognize only this fixed sidecar; never fall back from a damaged migration."""
    marker = _fixed(directory, META)
    if os.path.lexists(_fixed(directory, JOURNAL)):
        raise ValueError(PENDING)
    if not os.path.lexists(marker):
        draft = _fixed(directory, 'draft.json')
        if draft.is_file():
            saved = studio.read_json(draft)
            if isinstance(saved, dict) and saved.get('unfinished_migration'):
                raise ValueError('Restore this blog’s missing migration record before continuing.')
        return None
    try:

        def bounded(path):
            if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
                raise ValueError('missing or linked migration record')
            with path.open('rb') as handle:
                raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('oversized migration record')
            return raw

        value = json.loads(bounded(marker))
        original = bounded(directory / 'session.json')
        run = bounded(directory / 'derived/blog-run.json')
        draft = json.loads(bounded(_fixed(directory, 'draft.json')))
        if not migration_supported(value, original, run, draft, directory.name):
            raise ValueError('unsupported migration metadata or original records')
        for name in dependencies(value, draft):
            if not _fixed(directory, name.split('/')[1]).is_file():
                raise ValueError('missing desk dependency')
        return value
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(
            'This Blog Studio migration is incomplete or unreadable. Restore its saved desk records before continuing; no work was started.'
        ) from error


def blocked(root, ident):
    """Fail closed before worker acquisition, including partial or damaged sidecars."""
    if pending(root, ident):
        return True
    directory = studio.inside(root, 'articles', studio.identifier(ident))
    return metadata(directory) is not None  # Invalid never falls back to older work.


def prepare_migration(record, saved_inputs):
    """Pure bounded transform; callers supply saved bytes, never output paths."""
    import blog_runner
    import desk
    import desk_images

    blockers, writes = [], {}
    retained = [
        'Original session and run, decisions and real approvals',
        'History, source and guidance pins, Google baselines and team ownership',
        'Saved research, reviews and handoff remain historical; unfinished work stays Draft',
    ]
    run = saved_inputs.get('run')
    files = saved_inputs.get('files', {})
    try:
        if not session_supported(record):
            raise ValueError('Restore a supported original Blog Studio session record first.')
        if not run_supported(run):
            raise ValueError(
                'Restore a supported saved Blog Studio run, including its review level and research contract, before opening on the desk.'
            )
        pipeline, stages = run['pipeline'], run['stages']
        if all(stages.get(stage, {}).get('status') == 'approved' for stage in pipeline):
            raise ValueError(
                'This blog already finished. Use its existing finished-blog Open on the desk action.'
            )
        for stage, value in stages.items():
            if value.get('hash') and blog_runner.STAGES[stage][1] not in files:
                raise ValueError(
                    'Restore the missing saved '
                    + blog_runner.STAGES[stage][0].lower()
                    + ' before opening on the desk.'
                )
        material = next(
            (
                name
                for name in ('DRAFT.md', 'ORIGINAL.md', 'OUTLINE.md')
                if files.get(name, b'').strip()
            ),
            None,
        )
        if material is None:
            raise ValueError(
                'There is no usable manuscript or supported outline yet. Continue the saved flow until one is saved.'
            )
        text = files[material].decode('utf-8')
        parsed = desk_images.fitted(desk.split(text, title=record['title']))
        if (
            len(desk.join(parsed, images=False)) > desk.LIMIT
            or len(parsed['sections']) > desk.SECTIONS
        ):
            raise ValueError('Use supported materials up to 200,000 characters and 60 sections.')
        # Random identities in the general parser are replaced by stable migration IDs.
        for index, section in enumerate(parsed['sections']):
            section['id'] = _hash((material + '\0' + str(index) + '\0' + text).encode())[:8]
        kind = {'DRAFT.md': 'draft', 'ORIGINAL.md': 'original', 'OUTLINE.md': 'outline'}[material]
        scope = (
            'outline' if pipeline[-1] == 'outline' else 'draft' if 'draft' in pipeline else 'part'
        )
        at = saved_inputs.get('at', record.get('updated_at', record.get('created_at', '')))
        draft = {
            'schema': 1,
            'id': record['id'],
            'revision': 1,
            **parsed,
            'style': copy.deepcopy(record.get('style')),
            'tone': ((record.get('voice') or {}).get('tone') or '').strip(),
            'length': run.get('length') if run.get('length') in desk.LENGTHS else 'style',
            'sources': desk._citable(record.get('sources', [])),
            'gaps': [],
            'from_run': True,
            'unfinished_migration': True,
            'created_at': at,
            'updated_at': at,
            'brief': copy.deepcopy(run.get('brief', {})),
        }
        # Retain every publishing gap as unresolved, without turning the old
        # assistant's notes or automatic continuation into a person's approval.
        for stage in blog_runner.STAGES:
            raw = files.get('derived/blog-' + stage + '-notes.json')
            if raw is None:
                continue
            notes = json.loads(raw)
            gaps = notes.get('gaps', []) if isinstance(notes, dict) else None
            if not isinstance(gaps, list) or any(
                not isinstance(g, str) or len(g) > 2000 for g in gaps
            ):
                raise ValueError(
                    'Restore readable saved publishing notes before opening on the desk.'
                )
            for gap in gaps:
                if gap.strip() and gap not in draft['gaps']:
                    draft['gaps'].append(gap)
            if len(draft['gaps']) > 100:
                raise ValueError(
                    'This saved work has more publishing notes than the desk supports. Keep using its saved flow.'
                )
        if kind == 'outline':
            # The fixed Markdown outline format must round-trip before interpreting its
            # complete text as briefs. Lists, shortened headings and images are refused.
            if (
                len(parsed['sections']) < 2
                or parsed.get('images')
                or desk.join(parsed).strip() != text.replace('\r\n', '\n').strip()
                or len(parsed['opening']) > desk.BRIEF
                or any(len(s['text']) > desk.BRIEF for s in parsed['sections'])
            ):
                raise ValueError(
                    'This outline cannot yet be moved losslessly. Keep using the saved flow or supply a supported manuscript.'
                )
            draft.update(opening='', opening_brief=parsed['opening'])
            draft['sections'] = [{**s, 'brief': s['text'], 'text': ''} for s in parsed['sections']]
            writes['desk/start.json'] = {
                'schema': 1,
                'way': 'outline',
                'steps': ['draft'],
                'step': 'draft',
                'job': None,
                'execution': 'conversation',
                'started_at': at,
                'ended_at': None,
                'open': 'draft',
                'notes': text,
                'research_from': None,
            }
            if scope != 'draft':
                # An outline-only or review request grants no later drafting plan.
                writes.pop('desk/start.json')
        session = copy.deepcopy(record)
        session.update(flow='desk', execution='conversation', conversation_scope=scope)
        writes['desk/migration.json'] = {
            'schema': 1,
            'product': 'Blog Studio',
            'id': record['id'],
            'material': kind,
            'session': session,
            'historical_stages': copy.deepcopy(stages),
            'historical_pipeline': list(pipeline),
        }
        images = desk_images.data_of(draft, {})
        if images:
            writes['desk/images.json'] = images
        writes['desk/draft.json'] = desk_images.stored(draft)
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        blockers.append(str(error) or 'Restore readable supported saved materials first.')
        writes = {}
    return {'blockers': blockers, 'retained': retained, 'writes': writes}


def _read_tree(directory, files, prefix, budget):
    if directory.is_symlink():
        raise ValueError('Linked saved files cannot be moved safely. Keep using the saved flow.')
    for folder, directories, names in os.walk(
        directory, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)
    ):
        here = Path(folder)
        if any((here / name).is_symlink() for name in directories + names):
            raise ValueError(
                'Linked saved files cannot be moved safely. Keep using the saved flow.'
            )
        for name in sorted(names):
            path = here / name
            if not path.is_file():
                raise ValueError('Saved materials must be ordinary files.')
            size = path.stat().st_size
            if budget[0] + 1 > MAX_FILES or budget[1] + size > MAX_BYTES:
                raise ValueError(
                    'Saved work is too large to check safely for this migration. Keep using the saved flow.'
                )
            with path.open('rb') as handle:
                raw = handle.read(MAX_BYTES - budget[1] + 1)
            budget[0] += 1
            budget[1] += len(raw)
            if budget[1] > MAX_BYTES:
                raise ValueError('Saved work changed or is too large to check safely.')
            files[prefix + str(path.relative_to(directory))] = raw


def _worker_state(state):
    """The runner's implicit/schema-1 local format, before interpreting inactivity."""
    fields = {
        'schema',
        'enabled',
        'status',
        'error',
        'reason',
        'started_at',
        'notes',
        'research',
        'jobs',
    }
    if (
        not isinstance(state, dict)
        or set(state) - fields
        or type(state.get('schema', 1)) is not int
        or state.get('schema', 1) != 1
        or type(state.get('enabled')) is not bool
        or state.get('status')
        not in (
            'queued',
            'working',
            'paused',
            'stopped',
            'failed',
            'complete',
            'waiting-for-approval',
            'needs-attention',
            'in-chat',
        )
        or any(not isinstance(state[key], str) for key in ('error', 'started_at') if key in state)
        or state.get('reason') is not None
        and not isinstance(state['reason'], str)
        or not isinstance(state.get('notes', {}), dict)
        or any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in state.get('notes', {}).items()
        )
        or not isinstance(state.get('research', {}), dict)
        or not isinstance(state.get('jobs', []), list)
        or any(not isinstance(job, dict) for job in state.get('jobs', []))
    ):
        raise ValueError(
            'Restore a supported saved worker record with a known status and ownership before opening on the desk.'
        )
    return state['enabled'] or state['status'] in ('queued', 'working')


def _tool_state(job, name):
    """Validate actual saved tool ownership before deciding relevance or settlement."""
    import tool_jobs

    fields = {
        'schema',
        'id',
        'kind',
        'payload',
        'basis',
        'metadata',
        'fingerprint',
        'guidance',
        'status',
        'created_at',
        'attempts',
        'engine',
        'seconds',
        'model_profiles',
        'result',
        'error',
        'started_at',
        'finished_at',
        'model_selection',
        'reason',
        'said',
        'applied',
        'saved_content',
        'settled_at',
        'angles',
        'checks',
    }
    problem = 'Restore supported saved tool records with known status and ownership before opening on the desk.'
    if (
        not isinstance(job, dict)
        or set(job) - fields
        or type(job.get('schema', 1)) is not int
        or job.get('schema', 1) != 1
        or not isinstance(job.get('id'), str)
        or re.fullmatch(r'[a-f0-9]{32}\.json', name) is None
        or name != job['id'] + '.json'
        or job.get('kind') not in tool_jobs.KINDS
        or job.get('status') not in ('queued', 'working', 'ready', 'failed', 'cancelled')
        or not isinstance(job.get('payload'), dict)
        or not isinstance(job.get('metadata'), dict)
        or not isinstance(job.get('basis'), str)
        or any(
            not isinstance(job.get(key), str)
            for key in ('fingerprint', 'guidance', 'created_at', 'error')
        )
        or type(job.get('attempts')) is not int
        or job['attempts'] < 0
        or job.get('engine') not in ('codex', 'claude')
        or type(job.get('seconds')) is not int
        or job['seconds'] <= 0
        or 'result' not in job
        or job['result'] is not None
        and not isinstance(job['result'], dict)
        or any(
            not isinstance(job[key], str) or not job[key]
            for key in ('started_at', 'finished_at', 'settled_at')
            if key in job
        )
        or any(
            not isinstance(job[key], dict)
            for key in ('model_profiles', 'model_selection', 'checks')
            if key in job
        )
        or job.get('reason') is not None
        and not isinstance(job['reason'], str)
    ):
        raise ValueError(problem)
    request = {key: job[key] for key in ('kind', 'payload', 'basis', 'metadata')}
    if job['fingerprint'] != studio.digest(json.dumps(request, sort_keys=True).encode()):
        raise ValueError(problem)
    meta, kind = job['metadata'], job['kind']
    if kind in tool_jobs.DESK:
        keys = {'article', 'desk'}
        if not isinstance(meta.get('desk'), dict) or 'article' not in meta:
            raise ValueError(problem)
        if 'applied' in job and type(job['applied']) is not bool:
            raise ValueError(problem)
        if 'settled_at' in job and (job['status'] != 'ready' or 'applied' not in job):
            raise ValueError(problem)
    else:
        keys = {
            'voice-learn': {'name', 'samples', 'profile', 'background'},
            'voice-guide': {'name', 'samples'},
            'style-learn': {'name', 'samples', 'style'},
            'voice-audition': {'profile', 'profile_revision'},
            'repurpose': {'article', 'format', 'words', 'source_sha256', 'voice'},
            'interview-question': {'article'},
            'interview-outline': {'article'},
        }[kind]
        if 'applied' in job and (not isinstance(job['applied'], dict) or not job['applied']):
            raise ValueError(problem)
        if 'settled_at' in job:
            raise ValueError(problem)
    if set(meta) - keys:
        raise ValueError(problem)
    article = meta.get('article')
    if article is not None:
        if not isinstance(article, str):
            raise ValueError(problem)
        studio.identifier(article)
    elif (
        kind in (*tool_jobs.DESK, 'repurpose', 'interview-question', 'interview-outline')
        and kind != 'desk-angles'
    ):
        raise ValueError(problem)
    if job['status'] == 'ready' and (
        not isinstance(job['result'], dict)
        or not isinstance(job['result'].get('content'), str)
        or not job['result']['content'].strip()
    ):
        raise ValueError(problem)
    busy = job['status'] in ('queued', 'working') or (
        job['status'] == 'ready'
        and not (job.get('settled_at') if kind in tool_jobs.DESK else job.get('applied'))
    )
    return article, busy


def _driver_record(raw):
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or set(value) != {'schema', 'driver'}
        or type(value.get('schema')) is not int
        or value['schema'] != 1
    ):
        raise ValueError('Restore a supported saved ownership record before opening on the desk.')
    driver = value['driver']
    if driver is not None and (
        not isinstance(driver, dict)
        or set(driver) != {'name', 'computer', 'since'}
        or any(
            not isinstance(driver.get(key), str) or not driver[key]
            for key in ('name', 'computer', 'since')
        )
        or re.fullmatch(r'[a-f0-9]{16}', driver['computer']) is None
    ):
        raise ValueError('Restore a supported saved driver before opening on the desk.')
    return driver or {}


def _snapshot(root, ident):
    import blog_runner
    from studio_sync import support

    ident = studio.identifier(ident)
    if root.is_symlink() or (root / 'articles').is_symlink():
        raise ValueError('Choose an ordinary local Blog Studio workspace, without linked folders.')
    directory = studio.inside(root, 'articles', ident)
    files, budget = {}, [0, 0]
    if pending(root, ident):
        raise ValueError(PENDING)
    if not directory.is_dir():
        raise ValueError('Choose a saved Blog Studio blog.')
    _read_tree(directory, files, 'article/', budget)
    original = {name.removeprefix('article/'): raw for name, raw in files.items()}
    if any(len(original[name]) > 1_000_000 for name in ('session.json', blog_runner.STATE)):
        raise ValueError(
            'The original records exceed the supported migration size. Keep using the saved flow.'
        )
    record = json.loads(original['session.json'])
    run = json.loads(original[blog_runner.STATE])
    if not session_supported(record, ident) or not isinstance(run, dict):
        raise ValueError('Restore this blog’s supported original session and run records first.')
    driver = _driver_record(original['run.json']) if 'run.json' in original else {}
    if os.path.lexists(root / '.team-hub.json') or os.path.lexists(root / '.hub-workspace.json'):
        raise ValueError(
            'This older Team Hub workspace still needs its saved flow. A supported local ownership transform is required first.'
        )
    for entry in record.get('sources', []):
        source = studio.identifier(entry['source_id'])
        folder, current = studio.item(root, 'sources', source)
        _read_tree(folder, files, 'source/' + source + '/', budget)
        pinned, content = blog_runner.pinned_source(folder, current, entry['revision'])
        if pinned.get('status') != 'ready' or not content.strip():
            raise ValueError('Restore the readable pinned source before opening on the desk.')
    voice = record.get('voice') or {}
    if voice.get('mode') == 'profile':
        folder = studio.inside(root, 'profiles', studio.identifier(voice['profile_id']))
        _read_tree(folder, files, 'voice/', budget)
        for name in ('record.json', 'VOICE.md', 'rules.json'):
            if 'voice/revisions/' + str(voice['revision']) + '/' + name not in files:
                raise ValueError('Restore the pinned voice revision before opening on the desk.')
    if record.get('style'):
        import styles

        pin = record['style']
        folder = studio.inside(root, 'styles', studio.identifier(pin['style_id']))
        _read_tree(folder, files, 'style/', budget)
        styles.pinned(root, pin)
    if record.get('hub_context'):
        # These older adapters can fetch/materialize Hub data. No such operation is a preview.
        raise ValueError(
            'This saved Team Hub context still needs its saved flow. A local lossless context transform is required first.'
        )
    if run.get('research_contract') and run.get('stages', {}).get('research', {}).get('hash'):
        from studio_core import research_contract

        research_contract.read_bundle(directory / 'research')
    marker = root / 'hub.json'
    if os.path.lexists(marker):
        if marker.is_symlink() or marker.stat().st_size > 1_000_000:
            raise ValueError('Restore an ordinary Blog Studio workspace marker first.')
        files['workspace/hub.json'] = marker.read_bytes()
        hub = json.loads(files['workspace/hub.json'])
        if (
            not isinstance(hub, dict)
            or type(hub.get('schema')) is not int
            or hub['schema'] != 1
            or hub.get('tool') != 'blog-studio'
            or hub.get('folder') != root.name
            or any(
                not isinstance(hub.get(key), str) or not hub[key]
                for key in ('name', 'branch', 'minimum_runtime')
            )
            or hub.get('repository') is not None
            and (not isinstance(hub['repository'], str) or not hub['repository'])
        ):
            raise ValueError(
                'Restore a supported Blog Studio workspace marker before opening on the desk.'
            )
        if support.as_tuple(hub['minimum_runtime']) > support.as_tuple(support.runtime_version()):
            raise ValueError(
                'This workspace requires a newer Blog Studio runtime. Keep using its supported saved flow.'
            )
        computer_path = support.data_root() / 'computer.json'
        if (
            computer_path.is_symlink()
            or computer_path.exists()
            and (not computer_path.is_file() or computer_path.stat().st_size > 1_000_000)
        ):
            raise ValueError('Restore a supported local ownership record first.')
        computer = (
            computer_path.read_bytes()
            if computer_path.is_file() and not computer_path.is_symlink()
            else b'null'
        )
        files['ownership/computer.json'] = computer
        identity = json.loads(computer)
        if identity is not None and (
            not isinstance(identity, dict)
            or set(identity) != {'schema', 'id'}
            or type(identity.get('schema')) is not int
            or identity['schema'] != 1
            or not isinstance(identity.get('id'), str)
            or re.fullmatch(r'[a-f0-9]{16}', identity['id']) is None
        ):
            raise ValueError(
                'Restore a supported local computer identity before opening on the desk.'
            )
        if hub.get('repository'):
            if not driver.get('computer') or driver.get('computer') != (identity or {}).get('id'):
                raise ValueError(
                    'Another computer drives this blog, or it has no driver. Take it before opening on the desk.'
                )
    local = root / '.blog-runs' / (ident + '.json')
    if local.is_symlink() or local.parent.is_symlink():
        raise ValueError('Restore an ordinary saved worker record first.')
    busy = False
    if local.exists():
        if local.stat().st_size > 1_000_000:
            raise ValueError('Restore a supported saved worker record first.')
        files['worker/run.json'] = local.read_bytes()
        state = json.loads(files['worker/run.json'])
        busy = _worker_state(state)
    tools = root / '.blog-runs' / 'tools'
    if tools.is_symlink():
        raise ValueError('Restore ordinary saved worker records first.')
    tool_files = {}
    if tools.exists():
        _read_tree(tools, tool_files, '', budget)
    current = blog_runner.ENGINES.get(str(root))
    for name, raw in tool_files.items():
        if len(raw) > 1_000_000:
            raise ValueError('Restore bounded saved tool records before opening on the desk.')
        job = json.loads(raw)
        article, unsettled = _tool_state(job, name)
        if article == ident:
            files['worker/tools/' + name] = raw
            if unsettled or current and current.current == 'tool:' + job['id']:
                raise ValueError(
                    'A saved job is under way or waiting to land. Stop or finish it before opening on the desk.'
                )
    index = root / '.blog-runs/desk-jobs' / (ident + '.json')
    if index.parent.is_symlink() or index.is_symlink():
        raise ValueError('Restore an ordinary saved job index before opening on the desk.')
    if index.exists():
        if not index.is_file() or index.stat().st_size > 1_000_000:
            raise ValueError('Restore a supported saved job index before opening on the desk.')
        files['worker/index.json'] = index.read_bytes()
        indexed = json.loads(files['worker/index.json'])
        if (
            not isinstance(indexed, dict)
            or set(indexed) != {'jobs'}
            or not isinstance(indexed.get('jobs'), list)
            or len(indexed['jobs']) > 60
            or any(
                not isinstance(name, str) or re.fullmatch(r'[a-f0-9]{32}', name) is None
                for name in indexed['jobs']
            )
            or len(set(indexed['jobs'])) != len(indexed['jobs'])
            or any(
                name + '.json' not in tool_files
                or json.loads(tool_files[name + '.json'])['metadata'].get('article') != ident
                for name in indexed['jobs']
            )
        ):
            raise ValueError(
                'Restore this blog’s supported saved job index and owned tool records before opening on the desk.'
            )
    active = bool(current and current.current == ident)
    if busy or active:
        raise ValueError('A step of this blog is under way. Stop it before opening on the desk.')
    files['worker/acquired'] = str(active).encode()
    basis = {name: _hash(raw) for name, raw in sorted(files.items())}
    token = 'bm1.' + base64.urlsafe_b64encode(
        hashlib.sha256(_json(basis)).digest()
    ).decode().rstrip('=')
    return directory, record, run, original, token


def migration_preview(root, ident):
    """No locks, repair, settings migration, worker settlement, synchronization or writes."""
    shown = {
        'id': ident,
        'eligible': False,
        'expected': '',
        'blockers': [],
        'retained': [],
        'notice': REFUSAL,
    }
    try:
        directory, record, run, original, token = _snapshot(root, ident)
        if any(name.startswith('desk/') for name in original):
            raise ValueError(
                'This blog already has desk records. Open its existing desk or restore those records first.'
            )
        prepared = prepare_migration(record, {'run': run, 'files': original})
        shown.update(
            expected=token,
            eligible=not prepared['blockers'],
            blockers=prepared['blockers'],
            retained=prepared['retained'],
        )
        shown['held'] = (
            'Unfinished checks remain incomplete. No approval, research, writing job or delivery is started.'
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        shown['blockers'] = [str(error) or 'Restore the missing saved records first.']
    return shown


def _rollback(directory, journal):
    """Remove only matching outputs from this additive transaction, never old files."""
    if (
        not isinstance(journal, dict)
        or journal.get('schema') != 1
        or journal.get('product') != 'Blog Studio'
        or journal.get('id') != directory.name
        or not isinstance(journal.get('writes'), dict)
        or not journal['writes']
        or set(journal['writes']) - WRITES
        or not {'desk/migration.json', 'desk/draft.json'} <= set(journal['writes'])
        or not isinstance(journal.get('expected'), str)
    ):
        raise ValueError(PENDING)
    for name, digest in journal['writes'].items():
        path = _fixed(directory, name.split('/')[1])
        if path.exists() and (not path.is_file() or _hash(path.read_bytes()) != digest):
            raise ValueError(
                'Interrupted migration files changed. Restore its saved desk records before recovery; no files were removed.'
            )
    for name in reversed(list(journal['writes'])):
        _fixed(directory, name.split('/')[1]).unlink(missing_ok=True)
    _fixed(directory, JOURNAL).unlink()
    if not any((directory / 'desk').iterdir()):
        (directory / 'desk').rmdir()


def migrate(root, ident, expected):
    import desk_chat
    from team_workspace import guard

    if not isinstance(expected, str) or not expected.startswith('bm1.') or len(expected) != 47:
        raise ValueError('Use the opaque expected token returned by migration-preview.')
    with studio.locked(root):
        directory = studio.inside(root, 'articles', studio.identifier(ident))
        guard(root, ident)
        if pending(root, ident):
            journal = studio.read_json(_fixed(directory, JOURNAL))
            if journal.get('expected') != expected:
                raise ValueError(PENDING)
            _rollback(directory, journal)
        meta = metadata(directory)
        if meta is not None:
            if expected != meta['expected']:
                raise ValueError(CHANGED)
            return desk_chat._read(root, ident)
        directory, record, run, original, token = _snapshot(root, ident)
        if token != expected:
            raise ValueError(CHANGED)
        if any(name.startswith('desk/') for name in original):
            raise ValueError('Existing desk records must be restored or opened first.')
        prepared = prepare_migration(record, {'run': run, 'files': original, 'at': studio.now()})
        if prepared['blockers']:
            raise ValueError(' '.join(prepared['blockers']) + ' ' + REFUSAL)
        writes = prepared['writes']
        writes['desk/migration.json'].update(
            expected=expected,
            session_basis=_hash(original['session.json']),
            run_basis=_hash(original['derived/blog-run.json']),
            files=sorted(writes),
        )
        encoded = {name: _json(value) for name, value in writes.items()}
        if len(encoded['desk/migration.json']) > 1_000_000:
            raise ValueError(
                'This saved record is too large for supported desk migration. Keep using the saved flow.'
            )
        journal = {
            'schema': 1,
            'product': 'Blog Studio',
            'id': ident,
            'expected': expected,
            'writes': {name: _hash(raw) for name, raw in encoded.items()},
        }
        studio.write_json(_fixed(directory, JOURNAL), journal)
        try:
            # Ownership exists before registration. The journal prevents any pickup
            # during these writes or after an abrupt process exit.
            for name in (
                'desk/migration.json',
                'desk/images.json',
                'desk/start.json',
                'desk/draft.json',
            ):
                if name in encoded:
                    studio.atomic(_fixed(directory, name.split('/')[1]), encoded[name])
            _fixed(directory, JOURNAL).unlink()
        except BaseException:
            _rollback(directory, journal)
            raise
        return desk_chat._read(root, ident)
