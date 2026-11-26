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
REFUSAL = 'Nothing was changed: its saved writing, decisions and files stay as they are.'
PENDING = 'Opening this blog on the desk was interrupted. Repeat desk migrate with its preview token to recover before continuing or sharing.'
NOTHING_MADE = (
    'There is no usable manuscript or supported outline yet, so there is nothing to open on '
    'the writing desk.'
)
FINISHED = 'This blog already finished. Use its existing finished-blog Open on the desk action.'
NO_RUN = (
    'This blog has no saved step-by-step run to move. Use Open on the desk in Edit manuscript '
    'to bring its saved draft to the desk.'
)
OUTLINE_LOSS = (
    'This outline cannot yet be moved losslessly. Its saved files stay readable here; start '
    'new work from them.'
)
NOTES_FINISHED = (
    'This finished outline is notes the desk cannot read as sections, and an outline-only '
    'request has no later step on the desk to keep them with. Its outline stays readable here.'
)
# A condition of the workspace or of this computer, never of the blog: it waits until cleared.
OLDER_HUB = (
    'This workspace is connected to an older Team Hub, which the writing desk does not share '
    'through. Leave that Team Hub for this workspace (hub leave keeps its clone and queued '
    'work), then open this blog on the desk.'
)
NEWER_RUNTIME = (
    'This workspace needs a newer Blog Studio. Update Blog Studio, then open this blog on the desk.'
)
IDENTITY = (
    'This computer’s Blog Studio identity cannot be read. Take this blog on this computer, '
    'which records a new identity, then open it on the desk.'
)
MARKER = (
    'This workspace’s sharing record (hub.json) cannot be read by this Blog Studio. Update '
    'Blog Studio or restore that record, then open this blog on the desk.'
)
LINKED_WORKSPACE = (
    'This workspace or its blog folder is a link. Open the workspace from its real folder, '
    'then open this blog on the desk.'
)
# Conditions of the blog itself that a person clears: Take it, Stop its step, or a job ends.
DRIVER = (
    'Another computer drives this blog, or it has no driver. Take it before opening on the desk.'
)
JOB_BUSY = (
    'A saved job is under way or waiting to land. Stop or finish it before opening on the desk.'
)
STEP_BUSY = 'A step of this blog is under way. Stop it before opening on the desk.'
KEPT_HERE = 'Its saved files stay readable here.'


class Wait(ValueError):
    """A refusal that ends without restoring anything: a step or job under way, another
    computer driving the blog, or this blog's own interrupted opening, which its recovery
    finishes. Its words are the same as any other refusal's."""


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
        if (
            all(stages.get(stage, {}).get('status') == 'approved' for stage in pipeline)
            and files.get('DRAFT.md', b'').strip()
        ):
            # A finished blog with a draft has its own Open on the desk. Finished ideas or an
            # outline-only run have no draft, so they move as their waiting outline does.
            raise ValueError(FINISHED)
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
            raise ValueError(NOTHING_MADE)
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
                    'This saved work has more publishing notes than the desk supports. ' + KEPT_HERE
                )
        if kind == 'outline' and (
            # The fixed Markdown outline format must round-trip before interpreting its
            # complete text as briefs. Lists, shortened headings and images do not.
            len(parsed['sections']) >= 2
            and not parsed.get('images')
            and desk.join(parsed).strip() == text.replace('\r\n', '\n').strip()
            and len(parsed['opening']) <= desk.BRIEF
            and all(len(s['text']) <= desk.BRIEF for s in parsed['sections'])
        ):
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
        elif kind == 'outline':
            # Outline notes the desk cannot read as briefs move as the desk's own outline
            # start keeps notes it cannot parse: every word kept as the start's notes, no
            # briefs or prose invented, and the outline step still to do. Notes holding
            # image data, or a review request that has no outline step, are not moved.
            if scope == 'part' or desk_images.holds(text) or len(text) > desk.LIMIT:
                raise ValueError(OUTLINE_LOSS)
            # Notes the person already approved stay approved: their next step is the draft.
            approved = stages.get('outline', {}).get('status') == 'approved'
            if approved and scope != 'draft':
                # A finished outline-only request has no later step to keep its notes with.
                raise ValueError(NOTES_FINISHED)
            draft.update(opening='', opening_brief='', sections=[])
            steps = (
                ['draft'] if approved else ['outline', 'draft'] if scope == 'draft' else ['outline']
            )
            writes['desk/start.json'] = {
                'schema': 1,
                'way': 'outline' if scope == 'draft' else 'shape',
                'steps': steps,
                'step': steps[0],
                'job': None,
                'execution': 'conversation',
                'started_at': at,
                'ended_at': None,
                'open': 'draft' if scope == 'draft' else 'outline',
                'notes': text,
                'research_from': None,
            }
        session = copy.deepcopy(record)
        session.update(flow='desk', execution='conversation', conversation_scope=scope)
        if 'DRAFT.md' in files:
            # The desk took its draft from this DRAFT.md as it is, hand edits and all: that
            # text is what the desk last wrote (google_handoff refuses only a later change).
            session['artifact_hashes'] = {
                **(session.get('artifact_hashes') or {}),
                'draft': _hash(files['DRAFT.md']),
            }
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
        raise ValueError('Linked saved files cannot be moved safely. ' + KEPT_HERE)
    for folder, directories, names in os.walk(
        directory, followlinks=False, onerror=lambda error: (_ for _ in ()).throw(error)
    ):
        here = Path(folder)
        if any((here / name).is_symlink() for name in directories + names):
            raise ValueError('Linked saved files cannot be moved safely. ' + KEPT_HERE)
        for name in sorted(names):
            path = here / name
            if not path.is_file():
                raise ValueError('Saved materials must be ordinary files.')
            size = path.stat().st_size
            if budget[0] + 1 > MAX_FILES or budget[1] + size > MAX_BYTES:
                raise ValueError(
                    'Saved work is too large to check safely for this migration. ' + KEPT_HERE
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
        'discarded_at',  # A ready result the person discarded (tool_jobs.discard).
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
            for key in ('started_at', 'finished_at', 'settled_at', 'discarded_at')
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
        raise Wait(LINKED_WORKSPACE)
    directory = studio.inside(root, 'articles', ident)
    files, budget = {}, [0, 0]
    if pending(root, ident):
        raise Wait(PENDING)
    if not directory.is_dir():
        raise ValueError('Choose a saved Blog Studio blog.')
    _read_tree(directory, files, 'article/', budget)
    original = {name.removeprefix('article/'): raw for name, raw in files.items()}
    if 'session.json' not in original:
        raise ValueError('Choose a saved Blog Studio blog.')
    if blog_runner.STATE not in original:
        raise ValueError(NO_RUN)
    if any(len(original[name]) > 1_000_000 for name in ('session.json', blog_runner.STATE)):
        raise ValueError('The original records exceed the supported migration size. ' + KEPT_HERE)
    record = json.loads(original['session.json'])
    run = json.loads(original[blog_runner.STATE])
    if not session_supported(record, ident) or not isinstance(run, dict):
        raise ValueError('Restore this blog’s supported original session and run records first.')
    driver = _driver_record(original['run.json']) if 'run.json' in original else {}
    if os.path.lexists(root / '.team-hub.json') or os.path.lexists(root / '.hub-workspace.json'):
        raise Wait(OLDER_HUB)
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
            'This blog was saved with an older Team Hub context, which cannot yet be moved to '
            'the desk without loss. ' + KEPT_HERE
        )
    if run.get('research_contract') and run.get('stages', {}).get('research', {}).get('hash'):
        from studio_core import research_contract

        research_contract.read_bundle(directory / 'research')
    marker = root / 'hub.json'
    if os.path.lexists(marker):
        if marker.is_symlink() or marker.stat().st_size > 1_000_000:
            raise Wait(MARKER)
        files['workspace/hub.json'] = marker.read_bytes()
        try:
            hub = json.loads(files['workspace/hub.json'])
        except (ValueError, UnicodeError):
            raise Wait(MARKER) from None
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
            raise Wait(MARKER)
        try:
            newer = support.as_tuple(hub['minimum_runtime']) > support.as_tuple(
                support.runtime_version()
            )
        except (ValueError, TypeError):
            raise Wait(MARKER) from None
        if newer:
            raise Wait(NEWER_RUNTIME)
        computer_path = support.data_root() / 'computer.json'
        if (
            computer_path.is_symlink()
            or computer_path.exists()
            and (not computer_path.is_file() or computer_path.stat().st_size > 1_000_000)
        ):
            raise Wait(IDENTITY)
        computer = (
            computer_path.read_bytes()
            if computer_path.is_file() and not computer_path.is_symlink()
            else b'null'
        )
        files['ownership/computer.json'] = computer
        try:
            identity = json.loads(computer)
        except (ValueError, UnicodeError):
            raise Wait(IDENTITY) from None
        if identity is not None and (
            not isinstance(identity, dict)
            or set(identity) != {'schema', 'id'}
            or type(identity.get('schema')) is not int
            or identity['schema'] != 1
            or not isinstance(identity.get('id'), str)
            or re.fullmatch(r'[a-f0-9]{16}', identity['id']) is None
        ):
            raise Wait(IDENTITY)
        if hub.get('repository'):
            if not driver.get('computer') or driver.get('computer') != (identity or {}).get('id'):
                raise Wait(DRIVER)
    local = root / '.blog-runs' / (ident + '.json')
    if local.is_symlink() or local.parent.is_symlink():
        raise ValueError('Restore an ordinary saved worker record first.')
    busy = False
    if local.exists():
        if local.stat().st_size > 1_000_000:
            raise ValueError('Restore a supported saved worker record first.')
        files['worker/run.json'] = local.read_bytes()
        state = json.loads(files['worker/run.json'])
        # Only a step that will really run keeps a blog waiting. The manuscript editor's own
        # runs go on, so their marker counts; any other saved run's marker, even enabled or
        # queued, is left from the earlier flow and no runner picks it up again
        # (blog_runner.continues): only a step running now (below) waits.
        busy = _worker_state(state) and blog_runner.continues(run)
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
                raise Wait(JOB_BUSY)
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
        raise Wait(STEP_BUSY)
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
        failure = None
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        shown['blockers'] = [str(error) or 'Restore the missing saved records first.']
        failure = error
    shown.update(_verdict(root, ident, shown, failure))
    if shown['reason'] in (UNREAD_SESSION, UNREAD_RUN):
        # A record that cannot be read is said in its plain sentence, never in the JSON
        # reader's own words or with a path.
        shown['blockers'] = [shown['reason']]
    return shown


# What becomes of a saved blog, decided once for the preview and the page (classify).
OUTCOMES = ('migrates', 'finished', 'read-only', 'wait', 'current', 'desk')
MIGRATES = 'Its saved outline or draft can be opened on the writing desk.'
ON_DESK = 'This blog is on the writing desk.'
EDITOR = 'The manuscript editor made this run, and continues it in Edit manuscript.'
EARLY = (
    'Its earlier step-by-step flow stopped before an outline or draft was saved, so there is '
    'nothing to open on the writing desk.'
)
UNREAD_SESSION = 'Its saved blog record cannot be read.'
UNKNOWN_SESSION = 'Its saved blog record is in a format this Blog Studio does not support.'
UNREAD_RUN = 'Its saved run record cannot be read.'
UNKNOWN_RUN = 'Its saved run record is in a format this Blog Studio does not support.'
NOT_A_RUN = 'Its saved run record holds no run: it is not a record this Blog Studio can read.'


def _a_blog(directory):
    """A saved blog's own folder: an ordinary folder holding its session or run record. In
    a team workspace, where blogs sit at the top, no other folder is taken for one."""
    import blog_runner

    return (
        directory.is_dir()
        and not directory.is_symlink()
        and any(os.path.lexists(directory / name) for name in ('session.json', blog_runner.STATE))
    )


def _made(directory):
    """Whether a saved blog holds a manuscript or outline to open on the desk: a non-blank
    DRAFT.md, ORIGINAL.md or OUTLINE.md, an ordinary file in its folder. Only reads."""
    for name in ('DRAFT.md', 'ORIGINAL.md', 'OUTLINE.md'):
        path = directory / name
        try:
            if path.is_symlink() or not path.is_file():
                continue
            with path.open('rb') as handle:
                if handle.read(1_000_000).strip():
                    return True
        except OSError:
            continue
    return False


def _small_json(path):
    """A saved record's value, or raise: missing, linked, oversized or not JSON."""
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or linked record')
    with path.open('rb') as handle:
        raw = handle.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('oversized record')
    return json.loads(raw)


# What a from-files run holds as its brief until an angle is chosen: not a point or audience.
PLACEHOLDERS = ('Write a blog from the uploaded files.', 'To be chosen with the angle.')


def _start_from(session, run):
    """The start form a read-only record can begin new work from: its title, and the point
    and audience its run was given. Nothing it researched or made is carried."""
    if not isinstance(session, dict):
        return None
    title = session.get('title')
    if not isinstance(title, str) or not title.strip():
        return None
    brief = run.get('brief') if isinstance(run, dict) else None
    brief = brief if isinstance(brief, dict) else {}
    start = {'title': title.strip()[:500]}
    for key, said in (('point', 'goal'), ('audience', 'audience')):
        value = brief.get(said)
        if isinstance(value, str) and value.strip() and value.strip() not in PLACEHOLDERS:
            start[key] = value.strip()[: 2000 if key == 'point' else 500]
    return start


def _verdict(root, ident, shown, failure):
    """Migrates, finished, read-only, wait, current or desk, with its reason sentence; for a
    read-only record also its next action (`copy` starts new work from its start form,
    `new` an empty one) and that start form. Only reads, as the preview it serves does."""
    import blog_runner

    def said(outcome, reason, session=None, run=None):
        start = _start_from(session, run) if outcome == 'read-only' else None
        return {
            'outcome': outcome,
            'reason': reason,
            'next': ('copy' if start else 'new') if outcome == 'read-only' else None,
            'start': start,
        }

    try:
        directory = studio.inside(root, 'articles', studio.identifier(ident))
        if not _a_blog(directory):
            raise ValueError('not a saved blog')
    except (OSError, ValueError):
        return {**said(None, ' '.join(shown['blockers'])), 'next': None}  # No saved blog.
    if pending(root, ident):
        return said('wait', PENDING)
    try:
        session = _small_json(directory / 'session.json')
        if not isinstance(session, dict):
            raise ValueError('not a record')
    except (OSError, ValueError, UnicodeError):
        return said('read-only', UNREAD_SESSION)  # Missing counts: which flow made it is unknown.
    if session.get('flow') == 'desk':
        return said('desk', ON_DESK)
    run = None
    try:
        if metadata(directory) is not None:
            return said('desk', ON_DESK)
    except ValueError as error:
        return said('read-only', str(error), session)
    if (directory / 'desk' / 'draft.json').is_file():
        return said('desk', ON_DESK)  # A finished blog opened on the desk.
    if not os.path.lexists(directory / blog_runner.STATE):
        if session_supported(session, directory.name):
            return said('current', NO_RUN)  # A registered manuscript: the editor's.
        return said('read-only', UNKNOWN_SESSION, session)
    try:
        run = _small_json(directory / blog_runner.STATE)
    except (OSError, ValueError, UnicodeError):
        return said('read-only', UNREAD_RUN, session)
    if not isinstance(run, dict):
        return said('read-only', NOT_A_RUN, session)  # JSON, but not a run record.
    if not session_supported(session, directory.name):
        return said('read-only', UNKNOWN_SESSION, session, run)
    try:
        blog_runner.load(root, ident)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return said('read-only', str(error) or UNKNOWN_RUN, session, run)
    if not run_supported(run):
        return said('read-only', UNKNOWN_RUN, session, run)
    if isinstance(failure, Wait):
        if not _made(directory):
            # What the blog is comes first: with nothing made it is read-only, whatever its
            # workspace or a leftover waits on. Waiting is for a blog that would open on the desk.
            return said('read-only', EARLY, session, run)
        return said('wait', str(failure))
    if shown['eligible']:
        return said('migrates', MIGRATES)
    blocker = ' '.join(shown['blockers'])
    if blocker == FINISHED:
        return said('finished', FINISHED)
    if isinstance(run.get('editor_check'), str):
        return said('current', EDITOR)  # The editor's own run is current work.
    if blocker == NOTHING_MADE:
        return said('read-only', EARLY, session, run)
    return said('read-only', blocker or UNKNOWN_RUN, session, run)


# The files a read-only record lists and serves: only these names, only inside its folder.
SAVED_FILES = (
    'DRAFT.md',
    'ORIGINAL.md',
    'OUTLINE.md',
    'derived/blog-angles.md',
    'derived/blog-research-plan.md',
    'derived/blog-research.md',
    'derived/blog-claims-map.md',
    'derived/blog-review.md',
    'derived/blog-package.md',
)
SAVED_TEXT = 200_000
SAVED_RECORD = (
    'This blog was saved by the earlier step-by-step flow, and it can be neither continued '
    'nor opened on the desk. Its saved files are kept as they are.'
)
UNREAD_RECORD = (
    'This blog’s saved record cannot be read, so it can be neither continued nor opened on '
    'the desk. Its saved files are kept as they are.'
)
MOVES_RECORD = (
    'This blog was saved by the earlier step-by-step flow, which no longer continues it. Its '
    'saved writing continues on the writing desk.'
)
FINISHED_RECORD = (
    'This blog was finished in the earlier step-by-step flow, which no longer continues it. '
    'Open it on the writing desk to keep editing; it stays readable here.'
)
# What lists and the editorial board say of a saved blog of the earlier flow: what its small
# records prove. Its record, opened, says what becomes of it.
BOARD_WORDS = 'Saved by the earlier step-by-step flow: open it to see what becomes of it.'


def saved_flow(directory, record=None):
    """Whether a blog folder is a saved blog of the earlier flow: a saved run that is not the
    manuscript editor's, not desk work and not opened on the desk. Reads only the small
    records (session and run); a run that cannot be read counts. Never raises."""
    import blog_runner

    try:
        if record is None:
            record = _small_json(directory / 'session.json')
        if not isinstance(record, dict) or record.get('flow') == 'desk':
            return False
        if (directory / 'desk' / 'draft.json').is_file():
            return False
        if not os.path.lexists(directory / blog_runner.STATE):
            return False
    except (OSError, ValueError, UnicodeError):
        return False
    return not blog_runner.continues(saved_run(directory))


WAIT_RECORD = (
    'This blog was saved by the earlier step-by-step flow, which no longer continues it. It '
    'opens on the writing desk once what it waits on is cleared.'
)
# A saved blog the page shows as a saved record, by its one classification. `desk` and
# `current` (the manuscript editor's own work) keep their own screens.
RECORDS = ('migrates', 'finished', 'read-only', 'wait')


def _saved_files(directory):
    """Each listed name that is an ordinary file inside the blog's folder, never a link."""
    inside, found = directory.resolve(), []
    for name in SAVED_FILES:
        path = directory / name
        try:
            real = path.resolve()
        except (OSError, RuntimeError):
            continue
        if (
            not path.is_symlink()
            and not path.parent.is_symlink()
            and inside in real.parents
            and real.is_file()
        ):
            found.append(name)
    return found


def _waiting_job(root, ident):
    """The tool job of this blog that keeps it waiting (queued, working, or ready and not yet
    applied), as the blog's Tools list shows it: {'id', 'kind', 'status'}, or None. Only reads."""
    folder = root / '.blog-runs' / 'tools'
    if folder.is_symlink() or not folder.is_dir():
        return None
    for path in sorted(folder.glob('*.json')):
        try:
            job = _small_json(path)
            article, busy = _tool_state(job, path.name)
        except (OSError, ValueError, UnicodeError, KeyError, TypeError):
            continue
        if article == ident and busy:
            return {'id': job['id'], 'kind': job['kind'], 'status': job['status']}
    return None


def _clears(root, ident, reason):
    """What a waiting saved blog's screen offers to clear what it waits on: `recover` (finish
    an interrupted opening with the token its journal kept), `stop` (a step running now),
    `take` (another computer drives it, or this computer's identity is recorded by taking
    it), `job` (its waiting tool job, to finish or cancel where the blog's Tools list it), or
    None (nothing on the page clears a workspace or computer condition); with the token
    `recover` repeats, or the job."""
    if reason == PENDING:
        directory = studio.inside(root, 'articles', studio.identifier(ident))
        try:
            journal = _small_json(_fixed(directory, JOURNAL))
        except (OSError, ValueError, UnicodeError):
            return None, None
        token = journal.get('expected') if isinstance(journal, dict) else None
        if isinstance(token, str) and token.startswith('bm1.') and len(token) == 47:
            return 'recover', token
        return None, None
    if reason == STEP_BUSY:
        return 'stop', None
    if reason in (DRIVER, IDENTITY):
        return 'take', None
    if reason == JOB_BUSY:
        job = _waiting_job(root, ident)
        return ('job', job) if job else (None, None)
    return None, None


def saved_run(directory):
    """A blog folder's saved run record as it is stored, or None when there is none or it
    cannot be read (missing, linked, oversized or not JSON). Only reads."""
    import blog_runner

    try:
        return _small_json(directory / blog_runner.STATE)
    except (OSError, ValueError, UnicodeError):
        return None


def saved_record(root, ident, refusal=None):
    """What the page shows for a saved blog of the earlier step-by-step flow, which no longer
    continues: a saved record, by its one classification (classify). `saved_record` says its
    outcome, why, the saved files it holds, and its one next action: Open on the desk (the
    preview sheet) when it migrates, the finished Open on the desk when it finished, what
    clears what it waits on, or new work from it. A finished blog also carries its run as the
    run view reads it, for its Done card. None for desk work, for the manuscript editor's own
    work, which keep their screens, and where there is no saved blog. Only reads.

    `refusal`, the run view's own refusal when it had one, is not needed: the one
    classification decides."""
    shown = migration_preview(root, ident)
    outcome = shown['outcome']
    if outcome not in RECORDS:
        return None
    directory = studio.inside(root, 'articles', studio.identifier(ident))
    try:
        session = _small_json(directory / 'session.json')
    except (OSError, ValueError, UnicodeError):
        session = None
    title = session.get('title') if isinstance(session, dict) else None
    title = title.strip() if isinstance(title, str) and title.strip() else directory.name
    said = {
        'outcome': outcome,
        'why': shown['reason'],
        'files': _saved_files(directory),
        'next': shown['next'],
        'start': shown['start'],
    }
    found = {'id': directory.name, 'title': title, 'status': outcome}
    if outcome == 'read-only':
        found['sentence'] = SAVED_RECORD if isinstance(session, dict) else UNREAD_RECORD
    elif outcome == 'migrates':
        found['sentence'] = MOVES_RECORD
        said.update(retained=shown['retained'], held=shown.get('held'))
    elif outcome == 'finished':
        import blog_runner

        # The run as it ended, for the finished blog's Done card and its Open on the desk.
        found = {**blog_runner.engine(root).describe(directory.name), **found}
        found['sentence'] = FINISHED_RECORD
    else:
        found['sentence'] = WAIT_RECORD
        clear, token = _clears(root, directory.name, shown['reason'])
        if clear in ('stop', 'take'):
            import blog_runner
            from team_workspace import driver, space

            # The version a Stop or a Take is checked against, and who drives the blog.
            found['expected'] = blog_runner.survey(root, directory.name)['expected']
            found['team'] = bool(space(root) and space(root).address)
            found['driver'] = driver(root, directory.name) if space(root) else None
            if clear == 'take' and not found['team']:
                clear = None  # Taking needs a joined team repository: nothing here clears it.
        said.update(clear=clear, token=token if clear == 'recover' else None)
        if clear == 'job':
            # Its task is finished where the blog's Tools list it; new work is there meanwhile
            # (a task whose source changed since cannot be finished).
            said.update(job=token, start=_start_from(session, saved_run(directory)))
        if clear is None:
            # Nothing on the page clears it: new work can start from it meanwhile.
            start = _start_from(session, saved_run(directory))
            said.update(next='copy' if start else 'new', start=start)
    found['saved_record'] = said
    return found


def saved_file(root, ident, name):
    """One saved file of a saved record, read in place: a name SAVED_FILES lists, an ordinary
    file inside the blog's folder, its text shortened past SAVED_TEXT characters. Only reads."""
    directory = studio.inside(root, 'articles', studio.identifier(ident))
    if (
        name not in SAVED_FILES
        or not _a_blog(directory)
        or name not in _saved_files(directory)
        or classify(root, directory.name)['outcome'] not in RECORDS
    ):
        # Only a saved record's files are served here; other blogs have their own views.
        raise ValueError('Choose a saved file this blog holds.')
    with (directory / name).open('rb') as handle:
        raw = handle.read(SAVED_TEXT * 4 + 1)
    text = raw.decode('utf-8', errors='replace')
    return {
        'id': directory.name,
        'name': name,
        'text': text[:SAVED_TEXT],
        'truncated': len(text) > SAVED_TEXT or len(raw) > SAVED_TEXT * 4,
    }


def classify(root, ident):
    """What becomes of one saved blog, as its migration preview decides it: `outcome`
    (OUTCOMES, or None when there is no saved blog by that name), `reason` (one sentence),
    and for a read-only record `next` and `start`.

    migrates: the explicit migration opens it on the desk. finished: a finished blog with a
    draft, which its own Open on the desk takes there. read-only: nothing was made yet, or a
    record or dependency cannot be read or understood. wait: a refusal that ends by itself or
    by Stop or Take (a step or job under way, another computer driving, an interrupted
    opening's recovery). current: the manuscript editor's own work. desk: desk work already."""
    shown = migration_preview(root, ident)
    return {key: shown[key] for key in ('outcome', 'reason', 'next', 'start')}


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
                'This saved record is too large for supported desk migration. ' + KEPT_HERE
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
