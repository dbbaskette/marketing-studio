"""Bounded conversation commands over Blog Studio's locked desk domain operations."""

import json
from pathlib import Path
import sys

import desk
import desk_jobs
import studio

KINDS = {'draft': 'text', 'outline': 'outline', 'research': 'research'}
SCOPES = ('draft', 'outline', 'research', 'part')
CHANGED = 'The blog or its inputs changed. Read desk context again before submitting.'


def migration_preview(root, ident):
    from desk_migration import migration_preview as preview

    _workspace(root)
    return preview(root, ident)


def migrate(root, ident, expected):
    from desk_migration import migrate as apply

    _workspace(root)
    return apply(root, ident, expected)


def _owner(root, ident):
    return studio.item(root, 'articles', ident)[1].get('execution', 'runner')


def _guard(root, ident):
    from team_workspace import guard

    guard(root, ident)
    desk_jobs._busy(root, ident)


def _read(root, ident):
    draft = desk.read(root, ident)
    _, record = studio.item(root, 'articles', ident)
    removed = desk.removed(root, ident)
    return {
        'id': ident,
        'execution': record.get('execution', 'runner'),
        'scope': record.get('conversation_scope', 'draft'),
        'draft': draft,
        'markdown': desk.join(draft, images=False),
        'start': desk.read_start(root, ident),
        'editorial_notes': _notes(root, ident),
        'research': desk_jobs._research_extra(root, ident)[0],
        'removed': removed,
        'history': {
            part: desk.versions(root, ident, part)
            for part in ['title', 'opening']
            + [s['id'] for s in draft['sections']]
            + [s['id'] for s in removed]
        },
    }


def _notes(root, ident):
    directory, _ = studio.item(root, 'articles', ident)
    path = studio.inside(directory, 'desk', 'conversation-notes.json')
    return studio.read_json(path) if path.is_file() else {'notes': '', 'gaps': []}


def _workspace(root):
    if not (root / 'studio.json').is_file():
        raise ValueError(
            'Initialize this Blog Studio workspace first with studio.py --root PATH init.'
        )


def create(root, data):
    """Make desk work owned by this conversation; never queue a worker."""
    from team_workspace import before, saved

    _workspace(root)
    if not isinstance(data, dict):
        raise ValueError('Supply a JSON object for desk creation.')
    data = dict(data)
    scope = data.pop('scope', 'outline' if data.get('way') == 'shape' else 'draft')
    if scope not in SCOPES:
        raise ValueError('Choose scope draft, outline, research or part.')
    if scope in ('outline', 'research') and data.get('way', 'draft') == 'draft':
        raise ValueError('An outline or research scope starts from a topic or notes.')
    if scope == 'part' and data.get('way', 'draft') != 'draft':
        raise ValueError('A part scope starts with a supplied draft.')
    before(root)
    with studio.locked(root):
        made = desk.create(root, data)
        ident = made['id']
        directory, record = studio.item(root, 'articles', ident)
        record.update(execution='conversation', conversation_scope=scope)
        studio.persist(directory, 'articles', record)
        start = desk.read_start(root, ident)
        if start:
            steps = [s for s in start['steps'] if scope == 'draft' or s == scope]
            if not steps:
                steps = [scope]
            start.update(steps=steps, step=steps[0], execution='conversation')
            desk.write_start(root, ident, start)
        result = _read(root, ident)
    saved(root, ident, 'Start Blog Studio work in conversation')
    return result


def read(root, ident):
    _workspace(root)
    with studio.locked(root):
        # No settlement, recovery, queue wake or execution handoff on inspection.
        return _read(root, ident)


def save(root, ident, seen, part, text):
    from team_workspace import before, saved

    _workspace(root)
    before(root, ident)
    with studio.locked(root):
        _guard(root, ident)
        _context(root, ident, part)
        desk.save(root, ident, seen, part, text, source='chat')
        result = _read(root, ident)
    saved(root, ident, 'Keep a Blog Studio conversation edit')
    return result


def outline_save(root, ident, request):
    """Edit the complete ordered outline while retaining the desk's section identities."""
    from team_workspace import before, saved

    _workspace(root)
    if not isinstance(request, dict) or set(request) != {'expected_basis', 'rows'}:
        raise ValueError('An outline save takes expected_basis and the complete ordered rows.')
    before(root, ident)
    with studio.locked(root):
        _guard(root, ident)
        current = _context(root, ident, 'outline')
        if request['expected_basis'] != current['expected_basis']:
            raise ValueError(CHANGED)
        desk.outline_save(root, ident, current['inputs']['draft']['revision'], request['rows'])
        result = _read(root, ident)
    saved(root, ident, 'Keep a checked Blog Studio outline edit')
    return result


def _context(root, ident, target):
    draft = desk.read(root, ident)
    directory, record = studio.item(root, 'articles', ident)
    parts = {'title', 'opening'} | {s['id'] for s in draft['sections']}
    if not isinstance(target, str) or target not in set(KINDS) | parts:
        raise ValueError('Choose target draft, outline, research, title, opening or a section ID.')
    scope = record.get('conversation_scope', 'draft')
    if scope != 'draft' and target not in parts and target != scope:
        raise ValueError('This target exceeds the requested conversation scope.')
    if scope in ('research', 'outline') and target in parts:
        raise ValueError('This target exceeds the requested conversation scope.')
    extra, guidance = desk_jobs._context(root, draft)
    research, research_guidance = desk_jobs._research_extra(root, ident)
    inputs = {
        'draft': draft,
        'record': record,
        **extra,
        **research,
        'guidance': guidance + research_guidance,
        'start': desk.read_start(root, ident),
        'editorial_notes': _notes(root, ident),
    }
    # Include the team's current driver and byte-level domain files too. Source/voice/style
    # revisions are read through pinned context; changing any current dependency invalidates it.
    from team_workspace import record as team_record

    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Blog Studio conversation inputs cannot traverse links.')
        if path.is_file():
            files[str(path.relative_to(directory))] = studio.digest(path.read_bytes())
    value = {
        'target': target,
        'scope': scope,
        'inputs': inputs,
        'files': files,
        'team': team_record(root, ident),
        'jobs': desk_jobs.jobs(root, ident),
    }
    expected = studio.digest(json.dumps(value, sort_keys=True).encode())
    kind = KINDS.get(target, 'part')
    requirements = {
        'text': {
            'content': 'Markdown draft, up to 200,000 characters; no image data',
            'notes': 'Optional editorial notes kept outside the writing',
            'gaps': 'Optional list of things the person must supply',
        },
        'outline': {
            'title': 'One line',
            'opening_brief': 'Outline introduction',
            'sections': '1 to '
            + str(desk.SECTIONS)
            + ' rows with heading and brief; new outline start only, without prose or part History',
        },
        'part': {'text': 'Checked text for this existing part only'},
        'research': {
            'case': 'Absolute local Harness Research case directory containing a complete reviewed research bundle; raw prose is refused'
        },
    }[kind]
    return {
        'target': target,
        'expected_basis': expected,
        'scope': scope,
        'inputs': inputs,
        'requirements': {
            'kind': kind,
            'payload': requirements,
            'envelope': ['kind', 'target', 'expected_basis', 'payload'],
        },
    }


def context(root, ident, target):
    _workspace(root)
    with studio.locked(root):
        return _context(root, ident, target)


def _payload(request):
    if not isinstance(request, dict) or set(request) != {
        'kind',
        'target',
        'expected_basis',
        'payload',
    }:
        raise ValueError('Submit kind, target, expected_basis and payload together.')
    if not isinstance(request['payload'], dict):
        raise ValueError('The submission payload must be a JSON object.')
    if not isinstance(request['expected_basis'], str) or len(request['expected_basis']) != 64:
        raise ValueError('Use the expected_basis returned by desk context.')
    return request['payload']


def submit(root, ident, request):
    from team_workspace import before, saved

    _workspace(root)
    payload = _payload(request)
    before(root, ident)
    with studio.locked(root):
        _guard(root, ident)
        current = _context(root, ident, request['target'])
        if request['kind'] != current['requirements']['kind']:
            raise ValueError('The submission kind does not match this target.')
        if request['expected_basis'] != current['expected_basis']:
            raise ValueError(CHANGED)
        draft = current['inputs']['draft']
        kind = request['kind']
        if kind == 'part':
            if set(payload) != {'text'}:
                raise ValueError('A part payload takes only text.')
            desk.save(
                root, ident, draft['revision'], request['target'], payload['text'], source='chat'
            )
        elif kind == 'outline':
            if set(payload) - {'title', 'opening_brief', 'sections'}:
                raise ValueError('An outline takes title, opening_brief and sections.')
            start = desk.read_start(root, ident)
            initial_outline = bool(start and start.get('step') == 'outline')
            if start and current['scope'] == 'outline' and start.get('step') == 'research':
                steps = start.get('steps') or []
                initial_outline = (
                    'research' in steps and 'outline' in steps[steps.index('research') + 1 :]
                )
            prose_parts = ['opening'] + [section['id'] for section in draft['sections']]
            if (
                not initial_outline
                or draft['opening'].strip()
                or any(section['text'].strip() for section in draft['sections'])
                or any(desk.versions(root, ident, part) for part in prose_parts)
                or desk.removed(root, ident)
            ):
                raise ValueError(
                    'An initial outline is only for a new unwritten start without part History. '
                    'Use desk outline-save --article ID --input FILE to preserve sections and History.'
                )
            job = {'metadata': {'desk': {'basis': desk_jobs._outline_basis(draft)}}}
            desk_jobs._apply_outline(root, ident, draft, job, {'content': json.dumps(payload)})
        elif kind == 'text':
            if set(payload) - {'content', 'notes', 'gaps'}:
                raise ValueError('A draft takes content, notes and gaps.')
            text = payload.get('content')
            if (
                not isinstance(text, str)
                or not text.strip()
                or len(text) > desk.LIMIT
                or desk_images_hold(text)
            ):
                raise ValueError(
                    'Supply Markdown text up to 200,000 characters without embedded image data.'
                )
            notes = payload.get('notes', _notes(root, ident)['notes'])
            gaps = payload.get('gaps', draft.get('gaps', []))
            if (
                not isinstance(notes, str)
                or len(notes) > 20_000
                or not isinstance(gaps, list)
                or len(gaps) > 100
                or any(not isinstance(g, str) or len(g) > 2000 for g in gaps)
            ):
                raise ValueError('Supply bounded editorial notes and a list of publishing gaps.')
            desk.reimport(root, ident, text, 'chat')
            updated = desk.read(root, ident)
            updated['gaps'] = gaps
            desk._write(root, ident, updated)
            directory, _ = studio.item(root, 'articles', ident)
            studio.write_json(
                studio.inside(directory, 'desk', 'conversation-notes.json'),
                {'notes': notes, 'gaps': gaps},
            )
        else:
            _research(root, ident, payload, current)
        start = desk.read_start(root, ident)
        if start and request['target'] in ('draft', 'outline', 'research'):
            completed = {
                'draft': ['outline', 'draft'],
                'outline': ['outline'],
                'research': ['research'],
            }[request['target']]
            remaining = [s for s in start['steps'] if s not in completed]
            start.update(
                steps=remaining or start['steps'],
                step=remaining[0] if remaining else None,
                ended_at=None if remaining else studio.now(),
                job=None,
            )
            desk.write_start(root, ident, start)
        directory, _ = studio.item(root, 'articles', ident)
        receipts = studio.inside(directory, 'desk', 'conversation-submissions.json')
        prior = studio.read_json(receipts) if receipts.is_file() else []
        receipt = {
            'kind': kind,
            'target': request['target'],
            'expected_basis': request['expected_basis'],
            'input_revision': draft['revision'],
            'payload_digest': studio.digest(json.dumps(payload, sort_keys=True).encode()),
            'at': studio.now(),
            'source': 'conversation',
        }
        studio.write_json(receipts, (prior + [receipt])[-100:])
        result = _read(root, ident)
    saved(root, ident, 'Keep checked Blog Studio conversation work')
    return result


def desk_images_hold(text):
    import desk_images

    return desk_images.holds(text)


def _research(root, ident, payload, current):
    from studio_core import research_contract

    if (
        set(payload) != {'case'}
        or not isinstance(payload['case'], str)
        or not Path(payload['case']).is_absolute()
    ):
        raise ValueError('Research requires an absolute reviewed Harness Research case directory.')
    case = Path(payload['case'])
    if case.is_symlink():
        raise ValueError('Research cases cannot traverse links.')
    # Use the same consumer checker and publisher as worker settlement, without invoking
    # a companion or accepting an assistant-written report in place of independent review.
    bundle = case / 'research'
    manifest_file = research_contract.inside(bundle, 'output.json')
    if manifest_file.stat().st_size > 1_000_000:
        raise ValueError('Use a focused research bundle with a bounded manifest.')
    manifest = json.loads(manifest_file.read_text())
    entries = manifest.get('artifacts') if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or len(entries) > 1000:
        raise ValueError('Use a research bundle with at most 1,000 files.')
    total = 0
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('file'), str):
            raise ValueError('The research manifest has an unreadable file entry.')
        path = research_contract.inside(bundle, entry['file'])
        if not path.is_file():
            raise ValueError('Research bundles contain ordinary files only.')
        total += path.stat().st_size
        if total > 20_000_000:
            raise ValueError('Use a focused research bundle up to 20 MB.')
    facts, manifest = research_contract.read_bundle(bundle)
    if any(not isinstance(facts.get(key), list) for key in ('findings', 'facts', 'sources')):
        raise ValueError('The reviewed research must include findings, facts and sources lists.')
    import blog_library
    import synthesis_research
    from studio_core import research_sites

    directory, record = studio.item(root, 'articles', ident)
    # The checked context is the exact pinned selection exposed to the conversation.
    # Keep the saved choice from the article record: context inputs omit that policy.
    chosen = (
        research_sites.effective({})
        if 'research_from' in record and record['research_from'] is None
        else synthesis_research.research_from(record)
    )
    selected = {
        'sources/' + item['id'] + '.txt': item
        for item in current['inputs']['sources']
        if synthesis_research.offered(item)
    }
    for source in facts['sources']:
        if not isinstance(source, dict):
            raise ValueError('The research includes an unreadable source.')
        permission = source.get('permission')
        if permission == 'selected':
            name = source.get('file')
            item = selected.get(name) if isinstance(name, str) else None
            snapshot = source.get('snapshot')
            original = source.get('original_snapshot')
            if (
                not chosen['documents']
                or not item
                or source.get('origin') != item['origin']
                or not isinstance(snapshot, str)
                or research_contract.inside(
                    bundle, research_contract.snapshot_name(snapshot, manifest)
                ).read_bytes()
                != item['text'].encode()
                or (
                    original is not None
                    and (
                        not isinstance(original, str)
                        or research_contract.inside(
                            bundle, research_contract.snapshot_name(original, manifest)
                        ).read_bytes()
                        != item['text'].encode()
                    )
                )
            ):
                raise ValueError('The research includes a capture outside the pinned documents.')
        elif permission == 'public':
            if not isinstance(source.get('origin'), str):
                raise ValueError('The research includes an unreadable public origin.')
            blog_library.canonical(source['origin'])
            if not chosen['web'] and not research_sites.under(
                source.get('origin'), chosen['sites']
            ):
                raise ValueError('The research exceeds the pinned source scope.')
        else:
            raise ValueError('The research includes an unknown source permission.')
    previous = studio.inside(directory, 'research', 'output.json')
    if previous.is_file():
        # Keep a previous reviewed output byte-for-byte before replacing it, just as
        # a checked text save keeps History. Only consumer-validated manifest files
        # enter this archive; unrelated case files and arbitrary paths never do.
        _, old = research_contract.read_bundle(previous.parent)
        old_manifest = previous.read_bytes()
        archive = studio.inside(directory, 'history', 'research', studio.digest(old_manifest))
        for entry in old['artifacts']:
            content = research_contract.inside(previous.parent, entry['file']).read_bytes()
            research_contract.write(archive, entry['file'], content)
        research_contract.write(archive, 'output.json', old_manifest)
        research_contract.read_bundle(archive)
    research_contract.publish(case, directory / 'research')


def set_scope(root, ident, expected_basis, scope):
    """Record a person's explicit change of requested work without scheduling it."""
    from team_workspace import before, saved

    _workspace(root)
    if scope not in SCOPES:
        raise ValueError('Choose scope draft, outline, research or part.')
    before(root, ident)
    with studio.locked(root):
        _guard(root, ident)
        directory, record = studio.item(root, 'articles', ident)
        if record.get('execution') != 'conversation':
            raise ValueError('Only conversation-owned work changes scope here.')
        previous = record.get('conversation_scope', 'draft')
        target = previous if previous in KINDS else 'opening'
        current = _context(root, ident, target)
        if expected_basis != current['expected_basis']:
            raise ValueError(CHANGED + ' Use context --target ' + target + ' for scope changes.')
        if scope != previous:
            record['conversation_scope'] = scope
            changes = record.get('conversation_scope_changes', [])
            record['conversation_scope_changes'] = (
                changes
                + [
                    {
                        'before': previous,
                        'scope': scope,
                        'expected_basis': expected_basis,
                        'source': 'conversation',
                        'at': studio.now(),
                    }
                ]
            )[-100:]
            studio.persist(directory, 'articles', record)
        result = _read(root, ident)
    saved(root, ident, 'Change requested Blog Studio conversation scope')
    return result


def handoff(root, ident, expected_basis, scope):
    """Explicitly transfer only the requested remaining steps to the runner."""
    from team_workspace import before, saved

    _workspace(root)
    if (
        not isinstance(scope, list)
        or not scope
        or len(scope) > 3
        or any(not isinstance(s, str) or s not in ('research', 'outline', 'draft') for s in scope)
        or len(set(scope)) != len(scope)
    ):
        raise ValueError('Handoff scope must list research, outline and/or draft steps.')
    before(root, ident)
    with studio.locked(root):
        _guard(root, ident)
        start = desk.read_start(root, ident)
        if _owner(root, ident) != 'conversation':
            raise ValueError('Only conversation-owned work can hand off remaining steps.')
        if not start or start.get('ended_at'):
            raise ValueError(
                'This saved start has no remaining runner plan for the requested scope. Continue with checked desk submissions; no runner work started.'
            )
        _, record = studio.item(root, 'articles', ident)
        requested = record.get('conversation_scope', 'draft')
        allowed = {
            'draft': ('research', 'outline', 'draft'),
            'outline': ('outline',),
            'research': ('research',),
            'part': (),
        }[requested]
        if any(step not in allowed for step in scope):
            raise ValueError('Handoff scope exceeds the currently requested conversation scope.')
        # A scope change can exclude the old pending step without changing the
        # saved plan. Bind the explicit handoff to a context the current scope permits.
        target = start['step'] if start['step'] in allowed else requested
        current = _context(root, ident, target)
        if expected_basis != current['expected_basis']:
            raise ValueError(CHANGED)
        remaining = start['steps'][start['steps'].index(start['step']) :]
        if any(s not in remaining for s in scope) or scope != [s for s in remaining if s in scope]:
            raise ValueError('Choose remaining steps in their current order for handoff scope.')
        directory, record = studio.item(root, 'articles', ident)
        start.update(steps=scope, step=scope[0], execution='runner', job=None)
        desk.write_start(root, ident, start)
        record.update(execution='runner', handoff_scope=scope)
        studio.persist(directory, 'articles', record)
        desk_jobs.begin(root, ident)
        result = _read(root, ident)
    saved(root, ident, 'Hand off requested Blog Studio work')
    return result


def add_parser(groups):
    commands = groups.add_parser(
        'desk', help='create and edit Blog Studio work in conversation'
    ).add_subparsers(dest='action', required=True)
    for action in (
        'create',
        'show',
        'save',
        'context',
        'submit',
        'handoff',
        'scope',
        'outline-save',
        'migration-preview',
        'migrate',
    ):
        command = commands.add_parser(action)
        if action != 'create':
            command.add_argument('--article', required=True)
        if action in ('create', 'save', 'submit', 'handoff', 'scope', 'outline-save'):
            command.add_argument('--input', required=True, help='JSON file, or - for stdin')
        if action == 'context':
            command.add_argument('--target', required=True)
        if action == 'migrate':
            command.add_argument('--expected', required=True)


def command(root, args):
    if args.action == 'migration-preview':
        return migration_preview(root, args.article)
    if args.action == 'migrate':
        return migrate(root, args.article, args.expected)
    if args.action == 'show':
        return read(root, args.article)
    if args.action == 'context':
        return context(root, args.article, args.target)
    if args.input == '-':
        raw = sys.stdin.read(1_000_001)
    else:
        with Path(args.input).open(encoding='utf-8') as stream:
            raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Use a JSON request up to 1,000,000 characters.')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Supply a JSON object.')
    if args.action == 'create':
        return create(root, data)
    if args.action == 'submit':
        return submit(root, args.article, data)
    if args.action == 'outline-save':
        return outline_save(root, args.article, data)
    if args.action == 'scope':
        if set(data) != {'expected_basis', 'scope'}:
            raise ValueError('A scope change takes expected_basis and scope.')
        return set_scope(root, args.article, data['expected_basis'], data['scope'])
    if args.action == 'handoff':
        if set(data) != {'expected_basis', 'scope'}:
            raise ValueError('Handoff takes expected_basis and scope.')
        return handoff(root, args.article, data['expected_basis'], data['scope'])
    if set(data) != {'seen', 'part', 'text'}:
        raise ValueError('A checked save takes seen, part and text.')
    return save(root, args.article, data['seen'], data['part'], data['text'])
