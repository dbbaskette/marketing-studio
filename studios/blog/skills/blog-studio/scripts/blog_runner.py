"""One blog pipeline shared by conversation guidance and the local browser runner."""

import json
import difflib
from pathlib import Path
import re
import threading
from types import SimpleNamespace
import uuid

import studio
import blog_worker

STATE = 'derived/blog-run.json'
STAGES = {
    'research-plan': (
        'Research questions',
        'derived/blog-research-plan.md',
        'Plan focused research questions for the brief. Say what evidence is needed.',
    ),
    'research': (
        'Research findings',
        'derived/blog-research.md',
        'Research the approved questions. Cite evidence, contradictions and unanswered questions. '
        'With supplied sources only, use only those sources. Explicitly label missing evidence.',
    ),
    'outline': (
        'Outline',
        'OUTLINE.md',
        'Make an argument outline: reader problem, thesis, section purpose, evidence, caveats and ending.',
    ),
    'draft': (
        'Draft',
        'DRAFT.md',
        'Write the blog from the approved outline, evidence and voice. Avoid invented author experience.',
    ),
    'review': (
        'Review',
        'derived/blog-review.md',
        'Review the saved draft for factual support, argument, voice and wording. '
        'List actionable findings with passages and proposed changes. Do not rewrite the draft. '
        'Distinguish your judgment from completed mechanical checks; unresolved facts stay unresolved.',
    ),
    'package': (
        'Export package',
        'derived/blog-package.md',
        'Prepare a publication handoff: selected title, alternative titles, excerpt, suggested '
        'description, links to check and unresolved review findings. Do not publish anything.',
    ),
}
GUIDES = {
    'research-plan': 'modules/blog-deep-research.md',
    'research': 'modules/blog-deep-research.md',
    'outline': 'modules/blog-argument-outline.md',
    'draft': 'modules/blog-write.md',
    'review': 'modules/copy-editing.md',
    'package': 'modules/blog-repurpose.md',
}
ENGINES = {}
DEFAULTS = {
    'engine': 'codex',
    'seconds': 600,
    'research': 'supplied-only',
    'stop': 'package',
    'tone': 'Clear, conversational and specific',
    'author': '',
}
MODES = ('write', 'outline', 'revise', 'review')


def settings(root, data=None):
    """Shared settings come only from studios config; writing limits stay local."""
    import studios_config

    path = studio.inside(root, '.blog-run-settings.json')
    migration_notice, migration_problem = studios_config.migrate(root)
    shared, shared_problem = studios_config.read()
    shared_problem = shared_problem or migration_problem
    saved = studio.read_json(path) if path.is_file() else {}
    private = {
        key: value
        for key, value in saved.get('defaults', {}).items()
        if key in DEFAULTS and key not in ('engine', 'author')
    }
    base = {**DEFAULTS, **private}
    agent = shared.get('assistant', {}).get('agent')
    name = shared.get('person', {}).get('name')
    if agent in ('codex', 'claude'):
        base['engine'] = agent
    if isinstance(name, str) and len(name) <= 200:
        base['author'] = name
    if data is not None:
        data = dict(data)
        before = data.pop(
            'shared_before',
            {
                'engine': shared.get('assistant', {}).get('agent'),
                'author': shared.get('person', {}).get('name'),
            },
        )
        if not isinstance(before, dict) or set(before) != {'engine', 'author'}:
            raise ValueError('Reload the displayed shared settings before saving.')
        if set(data) != set(DEFAULTS):
            raise ValueError('Save the displayed writing settings only.')
        if data['engine'] not in ('codex', 'claude') or data['research'] not in (
            'none',
            'supplied-only',
            'web-allowed',
        ):
            raise ValueError('Choose a listed assistant and research scope.')
        if data['stop'] not in ('outline', 'draft', 'review', 'package'):
            raise ValueError('Choose a listed stop point.')
        if type(data['seconds']) is not int or not 30 <= data['seconds'] <= 3600:
            raise ValueError('Choose a step limit between 30 and 3600 seconds.')
        for key, maximum in (('tone', 2000), ('author', 200)):
            text(data[key], key, maximum)
        changes = {}
        if data['engine'] != (before['engine'] or DEFAULTS['engine']):
            changes['assistant'] = {'agent': data['engine']}
        if data['author'] != (before['author'] or DEFAULTS['author']):
            changes['person'] = {'name': data['author']}
        expected = {}
        if 'assistant' in changes:
            expected['assistant'] = {'agent': before['engine']}
        if 'person' in changes:
            expected['person'] = {'name': before['author']}
        shared = studios_config.update(changes, expected=expected)
        private = {key: value for key, value in data.items() if key not in ('engine', 'author')}
        studio.write_json(path, {'schema': 1, 'defaults': private})
        base = {
            **data,
            'engine': shared.get('assistant', {}).get('agent') or DEFAULTS['engine'],
            'author': shared.get('person', {}).get('name') or DEFAULTS['author'],
        }
        saved = {'defaults': private}
    return {
        'configured': bool(saved),
        'defaults': base,
        'shared_before': {
            'engine': shared.get('assistant', {}).get('agent'),
            'author': shared.get('person', {}).get('name'),
        },
        'shared_problem': shared_problem,
        'migration_notice': migration_notice,
        'workspace': str(root),
    }


def text(value, label, maximum=2000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'Use {label} text up to {maximum} characters.')
    return value.strip()


def load(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    path = studio.inside(directory, STATE)
    if not path.is_file():
        raise ValueError('This blog has no guided run. Choose Run this blog on the page.')
    run = studio.read_json(path)
    if run.get('schema') != 1 or run.get('approval') not in ('page', 'conversation'):
        raise ValueError('This run needs a newer Blog Studio runtime.')
    return directory, record, run


def inputs(root, record, run):
    """Exact selected context. Never silently replace a pinned voice with its latest revision."""
    sources = []
    from hub_workspace import portable_origin

    for selected in record['sources']:
        folder, source = studio.item(root, 'sources', selected['source_id'])
        path = studio.inside(folder, 'content.md')
        if selected['revision'] != source['revision']:
            raise ValueError(
                'A selected source changed. Reattach its current revision in chat first.'
            )
        content = path.read_text() if path.is_file() else ''
        sources.append(
            {
                'id': 'source-' + studio.digest((source['name'] + content).encode())[:12],
                'name': source['name'],
                'origin': portable_origin(source['origin']),
                'purposes': selected['purposes'],
                'status': source['status'],
                'text': content,
            }
        )
    voice = dict(record['voice'])
    if voice.get('mode') == 'profile':
        folder, _ = studio.item(root, 'profiles', voice['profile_id'])
        folder = studio.inside(folder, 'revisions', str(voice['revision']))
        voice['guide'] = (folder / 'VOICE.md').read_text()
        voice['rules'] = (folder / 'rules.json').read_text()
        voice.pop('profile_id')
        voice.pop('revision')
    # Shared context is an explicit selection, not the entire Hub or other authors' work.
    shared = []
    if record.get('hub_context'):
        from hub_workspace import active

        adapter = active(root)
        if adapter is None and not (root / 'hub.json').is_file():
            raise ValueError('The selected team context needs its Team Hub. Reconnect it in chat.')
        for ref in record['hub_context']['selected']:
            if adapter is None:
                migrated = studio.read_json(
                    studio.inside(root, '.shared', 'memory', ref['revision'] + '.json')
                )
                shared.append({'kind': migrated['kind'], 'body': migrated['body']})
                continue
            revision = adapter.hub.graph()['revisions'][ref['revision']]
            materialized = adapter.hub.read(ref['item'], ref['revision'])
            shared.append(
                {
                    'kind': revision['kind'],
                    'body': Path(materialized['paths']['BODY.md']).read_text(),
                }
            )
    payload = {
        'title': record['title'],
        'author': record.get('author', ''),
        'brief': run['brief'],
        'voice': voice,
        'sources': sources,
        'preferences': record.get('writing_preferences', {}),
        'memory': record.get('memory', {}),
        'team_context': shared,
        'research_policy': record['research_policy'],
        'guidance': (record.get('guidance') or {}).get('revision'),
    }
    if run.get('brand'):
        payload['brand'] = run['brand']
    if len(json.dumps(payload)) > 300_000:
        raise ValueError(
            'Selected context is too large for one writing job. Use focused excerpts in chat.'
        )
    return payload


def basis(root, directory, record, run, stage):
    context = inputs(root, record, run)
    previous = {}
    for name in run['pipeline']:
        if name == stage:
            break
        previous[name] = studio.artifact_fingerprint(directory, STAGES[name][1])
    original = studio.artifact_fingerprint(directory, 'ORIGINAL.md')
    if run['existing'] and stage != 'draft':
        previous['manuscript'] = studio.artifact_fingerprint(directory, 'DRAFT.md') or original
    return studio.digest(json.dumps([context, previous, original], sort_keys=True).encode())


def survey(root, ident):
    directory, record, run = load(root, ident)
    rows, next_stage, upstream = [], None, False
    for name in run['pipeline']:
        saved = run['stages'].get(name, {})
        current = studio.artifact_fingerprint(directory, STAGES[name][1])
        changed = bool(saved) and (
            saved.get('hash') != current
            or saved.get('basis') != basis(root, directory, record, run, name)
        )
        status = (
            'pending'
            if saved.get('status') == 'pending'
            else 'stale'
            if saved and (changed or upstream)
            else saved.get('status', 'pending')
        )
        if status != 'approved':
            upstream = True
            if next_stage is None:
                next_stage = name
        rows.append(
            {
                'stage': name,
                'label': STAGES[name][0],
                'status': status,
                'path': STAGES[name][1],
                'notes': saved.get('notes', ''),
                'request': saved.get('request', ''),
            }
        )
    content = ''
    if next_stage:
        path = studio.inside(directory, STAGES[next_stage][1])
        content = path.read_text() if path.is_file() else ''
    revision = studio.digest(
        (
            studio.inside(directory, STATE).read_bytes()
            + ((directory / 'run.json').read_bytes() if (directory / 'run.json').is_file() else b'')
            + json.dumps(
                [
                    [
                        row,
                        studio.artifact_fingerprint(directory, row['path']),
                        basis(root, directory, record, run, row['stage']),
                    ]
                    for row in rows
                ],
                sort_keys=True,
            ).encode()
        )
    )
    return {
        'id': ident,
        'title': record['title'],
        'approval': run['approval'],
        'engine': run['engine'],
        'seconds': run['seconds'],
        'stages': rows,
        'next': next_stage,
        'complete': next_stage is None,
        'content': content,
        'expected': revision,
        'directory': str(directory),
        'brief': run['brief'],
        'existing': run['existing'],
        'mode': run.get('mode', 'review' if run['existing'] else 'write'),
        'brand': {key: run['brand'][key] for key in ('skill', 'version', 'brand', 'variant')}
        if run.get('brand')
        else None,
        'decisions': run.get('decisions', [])[-30:],
    }


def save(root, directory, record, run, event):
    path = studio.inside(directory, STATE)
    if path.exists():
        studio.atomic(
            studio.inside(directory, 'history', 'editorial-run-' + uuid.uuid4().hex + '.json'),
            path.read_bytes(),
        )
    run.setdefault('decisions', []).append({'event': event, 'at': studio.now()})
    studio.write_json(path, run)
    record['next_step'] = (
        'Continue the guided blog on the page.'
        if run['approval'] == 'page'
        else 'Continue the guided blog in chat.'
    )
    studio.persist(directory, 'articles', record)
    from management import share, receipt

    from team_workspace import saved

    saved(root, record['id'], event)
    result = share(root, 'article', record)
    receipt(root, 'Guided blog', result, 'article')


def create(root, data, approval='conversation'):
    data = dict(data)
    defaults = settings(root)['defaults']
    data.setdefault('engine', defaults['engine'])
    data.setdefault('author', defaults['author'])
    if 'brand' not in data:
        import brand_skill

        for key, value in brand_skill.defaults().items():
            data.setdefault(key, value)
    allowed = {
        'id',
        'title',
        'author',
        'audience',
        'goal',
        'tone',
        'profile',
        'sources',
        'research',
        'stop',
        'engine',
        'seconds',
        'mode',
        'manuscript',
        'brand',
        'variant',
    }
    if set(data) - allowed:
        raise ValueError('Unknown new-blog field.')
    mode = data.get('mode', 'write')
    if mode not in MODES:
        raise ValueError('Choose write, outline, revise or review.')
    manuscript = None
    if data.get('manuscript'):
        if mode not in ('revise', 'review'):
            raise ValueError('Choose revise or review to start from a manuscript.')
        if data.get('id'):
            raise ValueError('Choose a saved blog or a supplied manuscript, not both.')
        folder, source = studio.item(root, 'sources', data['manuscript'])
        path = studio.inside(folder, 'content.md')
        if source['status'] != 'ready' or not path.is_file() or not path.read_text().strip():
            raise ValueError('Choose a draft with readable text.')
        manuscript = path.read_text()
        if len(manuscript) > 200_000:
            raise ValueError('Use a manuscript up to 200,000 characters.')
    if mode in ('revise', 'review') and not (data.get('id') or manuscript):
        raise ValueError('Choose an existing blog or upload a draft first.')
    engine = data.get('engine', 'codex')
    if engine not in ('codex', 'claude'):
        raise ValueError('Choose Codex or Claude.')
    seconds = data.get('seconds', 600)
    if type(seconds) is not int or not 30 <= seconds <= 3600:
        raise ValueError('Choose a step time limit between 30 and 3600 seconds.')
    research = data.get('research', 'supplied-only')
    if research not in ('supplied-only', 'web-allowed', 'none'):
        raise ValueError('Choose supplied sources, public research, or no research.')
    stop = data.get('stop', 'package')
    if mode == 'outline':
        stop = 'outline'
    elif mode == 'review':
        stop = 'review'
    elif mode == 'revise' and stop == 'outline':
        raise ValueError('A revision starts at draft. Choose draft, review or export package.')
    if stop not in ('outline', 'draft', 'review', 'package'):
        raise ValueError('Choose outline, draft, review or export package.')
    brief = {
        'goal': text(data.get('goal', ''), 'goal', required=True),
        'audience': text(data.get('audience', ''), 'audience', 500, required=True),
    }
    import brand_skill

    selected_brand = brand_skill.snapshot(data.get('brand', ''), data.get('variant', ''))
    title = text(data.get('title', ''), 'title', 500, required=not data.get('id'))
    profile = data.get('profile') or None
    if profile:
        studio.voice_pin(root, profile)
    sources = data.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 50 or len(set(sources)) != len(sources):
        raise ValueError('Select at most 50 different sources.')
    for source in sources:
        studio.item(root, 'sources', source)
    existing = bool(data.get('id') or manuscript)
    if data.get('id'):
        directory, record = studio.item(root, 'articles', data['id'])
        if studio.inside(directory, STATE).exists():
            raise ValueError('This blog already has a guided run. Open that run instead.')
        existing = (directory / 'DRAFT.md').is_file() or (directory / 'ORIGINAL.md').is_file()
        if mode in ('revise', 'review') and not existing:
            raise ValueError('This blog has no saved manuscript to revise or review.')
        if existing and stop in ('outline', 'draft') and mode != 'revise':
            raise ValueError('An existing draft starts at review. Choose review or export package.')
    else:
        args = SimpleNamespace(
            action='create',
            id=None,
            title=title,
            mode='existing'
            if manuscript
            else 'outline-only'
            if stop == 'outline'
            else 'first-draft',
            profile=profile,
            author=text(data.get('author', ''), 'author', 200) or None,
            voice='tone',
            tone=text(data.get('tone', ''), 'tone'),
            audience=brief['audience'],
            blog_type=None,
            review_folder=None,
            stop='outline' if stop == 'outline' else 'review',
            research='supplied-only' if research == 'none' else research,
        )
        ident = studio.new_id(title)
        record = studio.article_record(root, args, ident)
        directory = studio.inside(root, 'articles', ident)
    for source in sources:
        _, source_record = studio.item(root, 'sources', source)
        record['sources'] = [s for s in record['sources'] if s['source_id'] != source] + [
            {
                'source_id': source,
                'revision': source_record['revision'],
                'purposes': source_record['purposes'],
            }
        ]
    if profile:
        record['voice'] = {'mode': 'profile', **studio.voice_pin(root, profile)}
    record['research_policy'] = 'supplied-only' if research == 'none' else research
    pipeline = [] if research == 'none' else ['research-plan', 'research']
    pipeline += (
        (['draft', 'review', 'package'] if mode == 'revise' else ['review', 'package'])
        if existing
        else ['outline', 'draft', 'review', 'package']
    )
    pipeline = pipeline[: pipeline.index(stop) + 1]
    run = {
        'schema': 1,
        'approval': approval,
        'engine': engine,
        'seconds': seconds,
        'brief': brief,
        'existing': existing,
        'mode': mode,
        'pipeline': pipeline,
        'stages': {},
    }
    if selected_brand:
        run['brand'] = selected_brand
    inputs(root, record, run)  # Refuse unusable context before creating a partial blog.
    if not data.get('id'):
        directory.mkdir()
        studio.write_json(studio.inside(root, '.active-article.json'), {'id': record['id']})
    if manuscript:
        studio.save_artifact(directory, 'original', manuscript, record, 'supplied manuscript')
        studio.save_artifact(directory, 'draft', manuscript, record, 'supplied manuscript')
    save(root, directory, record, run, 'Created from ' + approval)
    return survey(root, record['id'])


def guard(root, ident, expected, page=False):
    found = survey(root, ident)
    if found['approval'] == 'page' and not page:
        raise ValueError(
            'This blog is decided on the page. Open its run to approve or return it to chat.'
        )
    if page and found['approval'] != 'page':
        raise ValueError('This blog is decided in chat. Choose Run this from here first.')
    if not expected or expected != found['expected']:
        raise ValueError('This blog changed. Reload its run and compare before deciding.')
    return found


def submit(root, ident, stage, result, expected, page=False):
    found = guard(root, ident, expected, page)
    if found['next'] != stage:
        raise ValueError('Finish the current stage before submitting another.')
    result = blog_worker.validate(result)
    directory, record, run = load(root, ident)
    pin = basis(root, directory, record, run, stage)
    filename = STAGES[stage][1]
    if stage in ('outline', 'draft'):
        studio.save_artifact(directory, stage, result['content'], record, 'guided run')
    else:
        path = studio.inside(directory, filename)
        if path.exists():
            studio.atomic(
                studio.inside(
                    directory, 'history', 'derived-blog-' + stage + '-' + uuid.uuid4().hex + '.md'
                ),
                path.read_bytes(),
            )
        studio.atomic(path, result['content'].encode())
    previous = run['stages'].get(stage, {})
    run['stages'][stage] = {
        'status': 'draft',
        'hash': studio.digest(result['content'].encode()),
        'basis': pin,
        'notes': result['notes'],
        'request': previous.get('request', ''),
    }
    save(root, directory, record, run, 'Submitted ' + stage)
    return survey(root, ident)


def decide(root, ident, expected, action, request='', page=False, target=None):
    found = guard(root, ident, expected, page)
    directory, record, run = load(root, ident)
    stage = target if action == 'changes' and target else found['next']
    if (
        action == 'changes'
        and target == 'draft'
        and run['existing']
        and 'draft' not in run['pipeline']
    ):
        run['pipeline'].insert(run['pipeline'].index('review'), 'draft')
    if stage is not None and stage not in run['pipeline']:
        raise ValueError('Choose a stage in this blog’s run.')
    if action == 'changes' and target and found['next']:
        if run['pipeline'].index(target) > run['pipeline'].index(found['next']):
            raise ValueError('Finish the current stage before changing a later stage.')
    if action == 'handoff':
        run['approval'] = 'conversation' if page else 'page'
    elif action == 'approve':
        if (
            not stage
            or next(row['status'] for row in found['stages'] if row['stage'] == stage) != 'draft'
        ):
            raise ValueError('Only a current submitted draft can be approved.')
        run['stages'][stage]['status'] = 'approved'
        approved_hash = run['stages'][stage]['hash']
        studio.atomic(
            studio.inside(
                directory, 'history', 'derived-blog-approved-' + stage + '-' + approved_hash + '.md'
            ),
            studio.inside(directory, STAGES[stage][1]).read_bytes(),
        )
        run.setdefault('approved', {})[stage] = approved_hash
    elif action == 'changes':
        if not stage:
            raise ValueError('This run is complete. Start a new revision in chat.')
        request = text(request, 'change request', 8000, required=True)
        run['stages'].setdefault(stage, {})['status'] = 'pending'
        run['stages'][stage]['request'] = request
        # Downstream decisions are kept in history, never silently renewed.
        for name in run['pipeline'][run['pipeline'].index(stage) + 1 :]:
            run['stages'].pop(name, None)
    else:
        raise ValueError('Unknown guided-blog decision.')
    save(root, directory, record, run, action + (' ' + stage if stage else ''))
    return survey(root, ident)


def job(root, ident):
    found = survey(root, ident)
    stage = found['next']
    if not stage:
        raise ValueError('This run is complete.')
    directory, record, run = load(root, ident)
    payload = inputs(root, record, run)
    payload['documents'] = {}
    for name in run['pipeline']:
        path = studio.inside(directory, STAGES[name][1])
        if path.is_file():
            payload['documents'][name] = path.read_text()
        if name == stage:
            break
    if run['existing']:
        path = directory / ('DRAFT.md' if (directory / 'DRAFT.md').is_file() else 'ORIGINAL.md')
        payload['documents']['manuscript'] = path.read_text()
    payload['changes'] = run['stages'].get(stage, {}).get('request', '')
    if len(json.dumps(payload)) > 600_000:
        raise ValueError('This job needs smaller source excerpts. Continue it in chat.')
    references = Path(__file__).resolve().parents[1] / 'references'
    guidance = STAGES[stage][2] + '\n\n' + (references / GUIDES[stage]).read_text()
    if stage == 'draft' and run['existing']:
        guidance += '\nRevise the supplied manuscript in the scope of its brief. Preserve its stance, meaningful qualifiers and author voice; retain unsupported claims as questions rather than inventing support.'
    guidance += '\n\n' + (references / 'style/house.md').read_text()
    return found, payload, guidance


class Engine:
    """One worker at a time per workspace. Locks cover saves, never model latency."""

    def __init__(self, root, worker=blog_worker.generate):
        self.root, self.worker = root, worker
        self.closed = threading.Event()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.current = None
        self.thread = None
        self.sync_thread = None

    def local(self, ident):
        path = studio.inside(self.root, '.blog-runs', studio.identifier(ident) + '.json')
        return studio.read_json(path) if path.is_file() else {'enabled': False, 'status': 'paused'}

    def keep_local(self, ident, value):
        studio.write_json(studio.inside(self.root, '.blog-runs', ident + '.json'), value)

    def control(self, ident, action):
        found = survey(self.root, ident)
        if found['approval'] != 'page':
            raise ValueError('Choose Run this from here to move this blog from chat to the page.')
        state = self.local(ident)
        if action in ('resume', 'retry'):
            if found['complete']:
                raise ValueError('This run is already complete.')
            state.update(enabled=True, status='queued', error='')
        elif action in ('pause', 'stop'):
            state.update(enabled=False, status='paused' if action == 'pause' else 'stopped')
            if action == 'stop' and self.current == ident:
                self.stop.set()
        else:
            raise ValueError('Unknown run control.')
        self.keep_local(ident, state)
        self.wake.set()
        return self.describe(ident)

    def describe(self, ident):
        found = survey(self.root, ident)
        local = self.local(ident)
        status = local.get('status', 'paused')
        if found['complete']:
            status = 'complete'
        elif found['approval'] == 'conversation':
            status = 'in-chat'
        elif any(
            row['stage'] == found['next'] and row['status'] == 'draft' for row in found['stages']
        ):
            status = 'waiting-for-approval'
        elif status == 'working' and self.current != ident:
            status = 'queued' if local.get('enabled') else 'paused'
        elif status in ('waiting-for-approval', 'complete'):
            # The prior gate was just decided; the next job has not started yet.
            status = 'queued' if local.get('enabled') else 'paused'
        from team_workspace import driver, space

        owner = driver(self.root, ident) if space(self.root) else None
        return {
            **found,
            'team': bool(space(self.root)),
            'driver': owner,
            'status': status,
            'error': local.get('error', ''),
            'enabled': local.get('enabled', False),
            'observation': 'Saved locally. Workers use your selected CLI sign-in. Public research links need review; no publishing is automatic.',
        }

    def once(self, ident):
        import brand_skill

        with brand_skill.using(quiet=True) as available:
            if available:
                return self._once(ident)

    def _once(self, ident):
        if not self.local(ident).get('enabled'):
            return
        from team_workspace import before

        preview = survey(self.root, ident)
        if (
            not preview['complete']
            and preview['approval'] == 'page'
            and not any(
                row['stage'] == preview['next'] and row['status'] == 'draft'
                for row in preview['stages']
            )
        ):
            before(self.root, ident)
        with studio.locked(self.root):
            local = self.local(ident)
            if not local.get('enabled'):
                return
            found = survey(self.root, ident)
            if found['complete']:
                local.update(enabled=False, status='complete')
                self.keep_local(ident, local)
                return
            if found['approval'] != 'page' or any(
                row['stage'] == found['next'] and row['status'] == 'draft'
                for row in found['stages']
            ):
                return
            if any(
                row['stage'] == found['next'] and row['status'] == 'stale'
                for row in found['stages']
            ):
                local.update(
                    enabled=False,
                    status='needs-attention',
                    error='Saved writing or its inputs changed. Review the saved version or ask for changes before running it again.',
                )
                self.keep_local(ident, local)
                return
            from team_workspace import guard

            guard(self.root, ident)
            found, payload, guidance = job(self.root, ident)
            local.update(status='working', error='')
            self.keep_local(ident, local)
            self.current = ident
            self.stop.clear()
            # Includes session metadata as well as run/documents: a parallel edit wins.
            directory, _, _ = load(self.root, ident)
            session = (directory / 'session.json').read_bytes()
        try:
            result = self.worker(
                found['engine'],
                payload,
                guidance,
                seconds=found['seconds'],
                web=found['next'] == 'research' and payload['research_policy'] == 'web-allowed',
                stop=self.stop,
            )
            with studio.locked(self.root):
                if self.stop.is_set() or self.closed.is_set():
                    return
                if (directory / 'session.json').read_bytes() != session:
                    raise ValueError(
                        'The blog changed while the worker ran. Your edit was kept. Retry from the latest version.'
                    )
                from team_workspace import before

                before(self.root, ident)
                submit(self.root, ident, found['next'], result, found['expected'], page=True)
                state = self.local(ident)
                state.update(status='waiting-for-approval', error='')
                self.keep_local(ident, state)
        except Exception as exc:
            with studio.locked(self.root):
                state = self.local(ident)
                if not self.stop.is_set() and not self.closed.is_set():
                    message = (
                        str(exc)
                        if isinstance(exc, (ValueError, OSError))
                        else 'The worker failed. Retry this step; saved work is kept.'
                    )
                    state.update(enabled=False, status='failed', error=message[:500])
                    self.keep_local(ident, state)
        finally:
            self.current = None

    def sync_team(self):
        from team_workspace import refresh

        while not self.closed.is_set():
            try:
                refresh(self.root)
            except (ValueError, OSError) as exc:
                # A failed background check remains visible until a successful one.
                from team_workspace import space, internal
                from studio_sync import support

                found = space(self.root)
                if found:
                    with support.locked(found.repo / '.git/blog-studio.lock'), internal():
                        prior = support.read_json(self.root / '.team-sync.json', {})
                        prior = prior if isinstance(prior, dict) else {}
                        studio.write_json(
                            self.root / '.team-sync.json',
                            {**prior, 'report': {'shared': False, 'notice': str(exc)[:500]}},
                        )
            if self.closed.wait(60):
                return

    def serve(self):
        while not self.closed.is_set():
            folder = studio.inside(self.root, '.blog-runs')
            for path in sorted(folder.glob('*.json')) if folder.exists() else []:
                if self.closed.is_set():
                    break
                try:
                    self.once(path.stem)
                except Exception as exc:
                    with studio.locked(self.root):
                        state = self.local(path.stem)
                        state.update(enabled=False, status='failed', error=str(exc)[:500])
                        self.keep_local(path.stem, state)
            self.wake.wait(1)
            self.wake.clear()

    def start(self):
        from team_workspace import space

        if space(self.root):
            self.sync_thread = threading.Thread(target=self.sync_team, daemon=True)
            self.sync_thread.start()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def close(self):
        self.closed.set()
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=5)
        if self.sync_thread:
            self.sync_thread.join(timeout=5)


def engine(root):
    return ENGINES.setdefault(str(root), Engine(root))


def catalog(root):
    rows = []
    for path in sorted(studio.inside(root, 'articles').glob('*/session.json')):
        ident = path.parent.name
        try:
            if studio.inside(path.parent, STATE).is_file():
                found = engine(root).describe(ident)
                rows.append(
                    {
                        k: found[k]
                        for k in (
                            'id',
                            'title',
                            'status',
                            'next',
                            'approval',
                            'error',
                            'stages',
                            'complete',
                            'engine',
                            'mode',
                            'team',
                            'driver',
                        )
                    }
                )
        except (ValueError, OSError, KeyError):
            rows.append(
                {
                    'id': ident,
                    'title': ident,
                    'status': 'needs-attention',
                    'error': 'Open this blog in chat to inspect its saved context.',
                }
            )
    return {'items': rows, 'total': len(rows)}


def options(root):
    def records(kind):
        result = []
        for path in sorted(studio.inside(root, kind).glob('*/record.json')):
            record = studio.read_json(path)
            result.append({'id': record['id'], 'name': record['name'], 'status': record['status']})
        return result

    agents = {}
    for name in ('codex', 'claude'):
        try:
            blog_worker.source_curator.executable(name)
            agents[name] = True
        except ValueError:
            agents[name] = False

    import brand_skill

    brand = brand_skill.status()
    brand['default'] = brand_skill.defaults(brand)
    return {
        'profiles': records('profiles'),
        'sources': records('sources'),
        'agents': agents,
        'settings': settings(root),
        'brand': brand,
    }


def document(root, ident, stage):
    directory, _, run = load(root, ident)
    if stage not in run['pipeline']:
        raise ValueError('Choose a stage in this blog’s run.')
    path = studio.inside(directory, STAGES[stage][1])
    content = path.read_text()
    previous = None
    approved = run.get('approved', {}).get(stage, '')
    if re.fullmatch('[a-f0-9]{64}', approved):
        before = studio.inside(
            directory, 'history', 'derived-blog-approved-' + stage + '-' + approved + '.md'
        )
        if before.is_file() and studio.digest(before.read_bytes()) == approved:
            previous = before.read_text()
    found = survey(root, ident)
    row = next(row for row in found['stages'] if row['stage'] == stage)
    differences = (
        list(
            difflib.unified_diff(
                (previous or '').splitlines(),
                content.splitlines(),
                fromfile='Last approved',
                tofile='This version',
                n=3,
            )
        )
        if previous is not None
        else []
    )
    return {
        'name': path.name,
        'content': content,
        'previous': previous,
        'diff': differences[:4000],
        'diff_truncated': len(differences) > 4000,
        'stage': stage,
        'label': row['label'],
        'status': row['status'],
        'notes': row['notes'],
        'expected': found['expected'],
        'checks': [
            {'label': 'Saved document contains readable text', 'passed': bool(content.strip())},
            {
                'label': 'Document matches its submitted version and selected inputs',
                'passed': row['status'] in ('draft', 'approved'),
            },
        ],
        'id': ident,
        'title': found['title'],
    }


def dispatch(root, action, data):
    """Called only by the authenticated page, under the ordinary desk mutation lock."""
    runner = engine(root)
    if action == 'create':
        data = dict(data)
        operation = data.pop('operation', '')
        if not isinstance(operation, str) or not re.fullmatch('[a-f0-9]{32}', operation):
            raise ValueError('A new blog needs its page operation ID. Reload and retry.')
        path = studio.inside(root, '.blog-runs', 'creations', operation + '.json')
        fingerprint = studio.digest(json.dumps(data, sort_keys=True).encode())
        if path.exists():
            prior = studio.read_json(path)
            if prior['fingerprint'] != fingerprint:
                raise ValueError('This creation request changed. Open a new form.')
            return runner.describe(prior['id'])
        found = create(root, data, approval='page')
        studio.write_json(path, {'id': found['id'], 'fingerprint': fingerprint})
        return runner.control(found['id'], 'resume')
    ident = data.get('id')
    if set(data) - {'id', 'expected', 'request', 'stage'}:
        raise ValueError('Unknown run field.')
    # Every page control is bound to the version the person was shown.
    found = survey(root, ident)
    if not data.get('expected') or data['expected'] != found['expected']:
        raise ValueError('This blog changed. Reload before deciding.')
    if action == 'start':
        if found['approval'] == 'conversation':
            decide(root, ident, data['expected'], 'handoff')
        return runner.control(ident, 'resume')
    if action in ('resume', 'retry', 'pause', 'stop'):
        return runner.control(ident, action)
    if action == 'adopt':
        if not found['next'] or not found['content']:
            raise ValueError('There is no saved stage to review.')
        submit(
            root,
            ident,
            found['next'],
            {
                'content': found['content'],
                'notes': 'The saved version was brought back for your review. Earlier assistant notes remain in history.',
            },
            data['expected'],
            page=True,
        )
        return runner.describe(ident)
    result = decide(
        root,
        ident,
        data['expected'],
        action,
        data.get('request', ''),
        page=True,
        target=data.get('stage'),
    )
    if action == 'handoff':
        state = runner.local(ident)
        state.update(enabled=False, status='in-chat')
        runner.keep_local(ident, state)
        if runner.current == ident:
            runner.stop.set()
    elif action == 'changes' and runner.current == ident:
        runner.stop.set()
    runner.wake.set()
    return {**result, **runner.describe(ident)}


def add_parser(groups):
    commands = groups.add_parser('run', help='Guided blogs in chat or on the page').add_subparsers(
        dest='action', required=True
    )
    create_cmd = commands.add_parser('create')
    for name in (
        'title',
        'author',
        'audience',
        'goal',
        'tone',
        'profile',
        'id',
        'brand',
        'variant',
    ):
        create_cmd.add_argument('--' + name, required=name in ('audience', 'goal'))
    create_cmd.add_argument(
        '--research', choices=('none', 'supplied-only', 'web-allowed'), default='supplied-only'
    )
    create_cmd.add_argument(
        '--stop', choices=('outline', 'draft', 'review', 'package'), default='package'
    )
    create_cmd.add_argument('--engine', choices=('codex', 'claude'))
    create_cmd.add_argument('--seconds', type=int, default=600)
    create_cmd.add_argument('--source', action='append', default=[])
    create_cmd.add_argument('--mode', choices=MODES, default='write')
    create_cmd.add_argument('--manuscript')
    commands.add_parser('list')
    for name in ('status', 'submit', 'approve', 'changes', 'handoff'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--id', required=True)
        if name != 'status':
            cmd.add_argument('--expected', required=True)
        if name == 'submit':
            cmd.add_argument('--stage', choices=tuple(STAGES), required=True)
            cmd.add_argument('--file', required=True)
            cmd.add_argument('--notes', default='')
        if name == 'changes':
            cmd.add_argument('--request', required=True)
            cmd.add_argument('--stage', choices=tuple(STAGES))


def command(root, args):
    if args.action == 'list':
        return catalog(root)
    if args.action == 'status':
        return engine(root).describe(args.id)
    with studio.locked(root):
        if args.action == 'create':
            data = {
                k: v
                for k, v in vars(args).items()
                if k not in ('root', 'group', 'action', 'source') and v is not None
            }
            data['sources'] = args.source
            return create(root, data)
        if args.action == 'submit':
            return submit(
                root,
                args.id,
                args.stage,
                {'content': Path(args.file).read_text(), 'notes': args.notes},
                args.expected,
            )
        return decide(
            root,
            args.id,
            args.expected,
            args.action,
            getattr(args, 'request', ''),
            target=getattr(args, 'stage', None),
        )
