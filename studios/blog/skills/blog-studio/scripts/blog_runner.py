"""One blog pipeline shared by conversation guidance and the local browser runner."""

import json
import difflib
from pathlib import Path
import re
import threading
import tempfile
import time
from types import SimpleNamespace
import uuid

import studio
import blog_worker
import editorial
from studio_core import model_profiles, review_policy, research_contract
from studio_core.preferences import ready as shared_ready

STATE = 'derived/blog-run.json'
# A from-files run embeds the uploaded files; past this many JSON characters of source
# text, each file is excerpted to its share and the run says which ones were.
SOURCE_BUDGET = 240_000
STAGES = {
    'angles': (
        'Angles',
        'derived/blog-angles.md',
        'Read the uploaded files and the author’s note about them. Propose three distinct blog '
        'angles the files can support. Return each as a `## Title` heading followed by one '
        'line in this shape: the audience · the point it makes · Leans on <file names>. '
        'Say which files were excerpted or have no text. Do not outline or draft the blog.',
    ),
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
    'angles': 'modules/blog-argument-outline.md',
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
MODES = ('write', 'outline', 'from-outline', 'ideas', 'revise', 'review', 'from-files')
MATERIAL_ELSEWHERE = (
    'This blog’s uploaded files stay on the computer that added them. Continue it there, '
    'or start it again here from your files.'
)


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
        displayed_engine = (
            before['engine'] if before['engine'] in ('codex', 'claude') else DEFAULTS['engine']
        )
        if data['engine'] != displayed_engine:
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
            'engine': shared.get('assistant', {}).get('agent')
            if shared.get('assistant', {}).get('agent') in ('codex', 'claude')
            else DEFAULTS['engine'],
            'author': shared.get('person', {}).get('name') or DEFAULTS['author'],
        }
        saved = {'defaults': private}
    try:
        review_level = review_policy.snapshot(shared)['level']
    except ValueError:
        review_level = 'step_by_step'
    return {
        'configured': bool(saved) or shared_ready(shared),
        'defaults': base,
        'review_level': review_level,
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
    if run.get('schema') not in (1, 2, 3) or run.get('approval') not in ('page', 'conversation'):
        raise ValueError('This run needs a newer Blog Studio runtime.')
    if run.get('schema') == 2 and not run.get('review_policy'):
        raise ValueError('This run is missing its saved review level. Restore its run record.')
    if run.get('schema') == 3 and (run.get('research_contract') or {}).get('schema') != 2:
        raise ValueError('This run is missing its saved research contract. Restore its run record.')
    return directory, record, run


def inputs(root, record, run):
    """Exact selected context. Never silently replace a pinned voice with its latest revision."""
    sources = []
    from hub_workspace import portable_origin

    pinned = {selected['source_id'] for selected in record['sources']}
    for selected in record['sources']:
        if 'material' in selected['purposes'] or selected['source_id'] in record.get(
            'material', []
        ):
            try:
                studio.item(root, 'sources', selected['source_id'])
            except ValueError:
                raise ValueError(MATERIAL_ELSEWHERE) from None
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
    if set(record.get('material', [])) - pinned:
        raise ValueError(MATERIAL_ELSEWHERE)  # A Team Hub copy carries no uploaded files.
    if run.get('mode') == 'from-files':
        sources = excerpted(sources, SOURCE_BUDGET, run_terms(record, run))
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


def encoded_size(value):
    return len(json.dumps(value))


STOPWORDS = frozenset(
    'about after again also because been before being blog could does each file files from '
    'have into just more most much need only other over post same should some such than '
    'that their them then there these they this those through very want what when where '
    'which while will with would your uploaded write writing'.split()
)


def terms(*texts):
    """Words worth matching in a file: four letters or more, without common words."""
    words = []
    for value in texts:
        for word in re.findall(r'[^\W\d_]{4,}', str(value or '').casefold()):
            if word not in words and word not in STOPWORDS:
                words.append(word)
    return words[:12]


def run_terms(record, run):
    """What the person typed about the files and, once chosen, the angle: never defaults."""
    chosen = run.get('chosen_angle') or {}
    return terms(run.get('files_note', ''), chosen.get('title', ''), chosen.get('says', ''))


def fit(text, limit, wanted=()):
    """The head of a text, then the paragraphs that mention the wanted words, then the rest,
    within a limit of JSON characters. Cuts are marked so the worker sees them."""
    if encoded_size(text) <= limit:
        return text
    spans = [(m.start(), m.end()) for m in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text)]
    chosen, used = {}, 0
    mark = encoded_size('\n\n[…]\n\n')

    def take(index, allowance, cut):
        nonlocal used
        start, end = spans[index]
        piece = text[start:end]
        size = encoded_size(piece)
        if size > allowance:
            if not cut:
                return False  # Whole paragraphs first; a later pass may cut one to fit.
            piece = piece[: max(0, len(piece) - (size - allowance))]
            while piece and encoded_size(piece) > allowance:
                piece = piece[: len(piece) * 9 // 10]
            if not piece:
                return False
            while piece and encoded_size(piece + ' […]') > allowance:
                piece = piece[: len(piece) * 9 // 10]
            if not piece:
                return False
            piece += ' […]'
        chosen[index] = piece
        used += encoded_size(piece) + mark
        return True

    order = list(range(len(spans)))
    matched = [
        index
        for index in order
        if any(word in text[spans[index][0] : spans[index][1]].casefold() for word in wanted)
    ]
    passes = ((order, limit // 2, False), (matched, limit, False), (order, limit, True))
    for sequence, allowance, cut in passes:
        for index in sequence:
            if index in chosen:
                continue
            if used + mark >= allowance or not take(index, allowance - used - mark, cut):
                break
    parts, previous = [], None
    for index in sorted(chosen):
        if previous is not None and index != previous + 1 and not parts[-1].endswith('[…]'):
            parts.append('[…]')
        parts.append(chosen[index])
        previous = index
    if previous is not None and previous != len(spans) - 1 and not parts[-1].endswith('[…]'):
        parts.append('[…]')
    return '\n\n'.join(parts)


def excerpted(sources, budget, wanted=()):
    """Sources within a shared budget: small files whole, large ones excerpted to a fair share."""
    sizes = {source['id']: encoded_size(source['text']) for source in sources}
    if sum(sizes.values()) <= budget:
        return sources
    shares, remaining = {}, budget
    pending = sorted(sources, key=lambda source: sizes[source['id']])
    for position, source in enumerate(pending):
        share = min(sizes[source['id']], remaining // (len(pending) - position))
        shares[source['id']] = share
        remaining -= share
    result = []
    for source in sources:
        if sizes[source['id']] <= shares[source['id']]:
            result.append(source)
            continue
        text = fit(source['text'], shares[source['id']], wanted)
        result.append(
            {
                **source,
                'text': text,
                'excerpted': True,
                'total_chars': len(source['text']),
                'kept_chars': len(text),
            }
        )
    return result


def basis(root, directory, record, run, stage, context=None, research=None):
    """A stage's input pin. Pass the serialised inputs() and research manifest to reuse them."""
    if context is None:
        context = json.dumps(inputs(root, record, run), sort_keys=True)
    previous = {}
    if run.get('mode') == 'from-outline':
        previous['supplied_outline'] = studio.artifact_fingerprint(directory, 'OUTLINE.md')
    for name in run['pipeline']:
        if name == stage:
            break
        previous[name] = studio.artifact_fingerprint(directory, STAGES[name][1])
    if run.get('research_contract') and 'research' in previous and run['stages'].get('research'):
        if research is None:
            _, research = research_contract.read_bundle(directory / 'research')
        previous['research_digest'] = research['digest']
    original = studio.artifact_fingerprint(directory, 'ORIGINAL.md')
    if run['existing'] and stage != 'draft':
        previous['manuscript'] = studio.artifact_fingerprint(directory, 'DRAFT.md') or original
    # Byte-for-byte json.dumps([inputs, previous, original], sort_keys=True), so saved pins hold.
    pinned = '[' + context + ', ' + json.dumps(previous, sort_keys=True) + ', '
    return studio.digest((pinned + json.dumps(original) + ']').encode())


def survey(root, ident, listing=False):
    """Stage states. A listing skips the version token and next document a decision needs."""
    directory, record, run = load(root, ident)
    research = None
    if run.get('research_contract') and run['stages'].get('research'):
        _, research = research_contract.read_bundle(directory / 'research')
    # Selected context is read and serialised once; every stage pin reuses it.
    payload = inputs(root, record, run)
    context = json.dumps(payload, sort_keys=True)
    bases = {}

    def pin(name):
        if name not in bases:
            bases[name] = basis(root, directory, record, run, name, context, research)
        return bases[name]

    rows, next_stage, upstream = [], None, False
    for name in run['pipeline']:
        saved = run['stages'].get(name, {})
        current = studio.artifact_fingerprint(directory, STAGES[name][1])
        changed = bool(saved) and (saved.get('hash') != current or saved.get('basis') != pin(name))
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
                'accepted_by': saved.get('accepted_by'),
                # Accepted by the saved review level, not the person; it needs no approval.
                'auto_accepted': status == 'approved'
                and saved.get('accepted_by') == 'review-policy',
                'request': saved.get('request', ''),
            }
        )
    # What moves the run on: the person's decision on a submitted document, or a submission.
    awaits = None
    if next_stage:
        submitted = next(row for row in rows if row['stage'] == next_stage)['status'] == 'draft'
        awaits = 'decision' if submitted else 'submission'
    content, revision = '', None
    if next_stage and not listing:
        path = studio.inside(directory, STAGES[next_stage][1])
        content = path.read_text() if path.is_file() else ''
    if not listing:
        revision = studio.digest(
            (
                studio.inside(directory, STATE).read_bytes()
                + (
                    (directory / 'run.json').read_bytes()
                    if (directory / 'run.json').is_file()
                    else b''
                )
                + json.dumps(
                    [
                        [
                            row,
                            studio.artifact_fingerprint(directory, row['path']),
                            pin(row['stage']),
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
        'google': editorial.doc_link(record),
        'approval': run['approval'],
        'engine': run['engine'],
        'model_mode': (run.get('model_profiles') or {}).get('mode', 'single'),
        'review_level': review_policy.level(run),
        'seconds': run['seconds'],
        'stages': rows,
        'next': next_stage,
        'awaits': awaits,
        'complete': next_stage is None,
        'content': content,
        'expected': revision,
        'directory': str(directory),
        'brief': run['brief'],
        'existing': run['existing'],
        'editor_check': run.get('editor_check'),
        'mode': run.get('mode', 'review' if run['existing'] else 'write'),
        'brand': {key: run['brand'][key] for key in ('skill', 'version', 'brand', 'variant')}
        if run.get('brand')
        else None,
        'decisions': run.get('decisions', [])[-30:],
        'publication': (record.get('editorial') or {}).get('publication_url') or None,
        # Files cut to the run's budget, by name, so the page and chat can say so.
        'excerpted': [source['name'] for source in payload['sources'] if source.get('excerpted')],
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


def research_scope(research, sources):
    """Supplied-only research has nothing to read without supplied sources."""
    return 'none' if research == 'supplied-only' and not sources else research


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
        'outline_text',
        'brand',
        'variant',
    }
    if set(data) - allowed:
        raise ValueError('Unknown new-blog field.')
    mode = data.get('mode', 'write')
    if mode not in MODES:
        raise ValueError(
            'Choose write, outline, from-outline, ideas, revise, review or from-files.'
        )
    outline_text = text(
        data.get('outline_text', ''), 'outline', 200_000, required=mode == 'from-outline'
    )
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
    research = data.get(
        'research', 'none' if mode in ('revise', 'review', 'ideas') else 'supplied-only'
    )
    if research not in ('supplied-only', 'web-allowed', 'none'):
        raise ValueError('Choose supplied sources, public research, or no research.')
    if mode == 'from-files' and research == 'none':
        research = 'supplied-only'  # The files are the sources; the web is the only option.
    stop = data.get('stop', 'package')
    if mode in ('outline', 'ideas'):
        stop = 'outline'
    elif mode == 'review':
        stop = 'review'
    elif mode == 'revise' and stop == 'outline':
        raise ValueError('A revision starts at draft. Choose draft, review or export package.')
    if stop not in ('outline', 'draft', 'review', 'package'):
        raise ValueError('Choose outline, draft, review or export package.')
    from_files = mode == 'from-files'
    brief = {
        'goal': text(data.get('goal', ''), 'goal', required=not from_files)
        or 'Write a blog from the uploaded files.',
        'audience': text(data.get('audience', ''), 'audience', 500, required=not from_files)
        or 'To be chosen with the angle.',
    }
    import brand_skill

    selected_brand = brand_skill.snapshot(data.get('brand', ''), data.get('variant', ''))
    title = text(
        data.get('title', ''), 'title', 500, required=not data.get('id') and not from_files
    )
    if from_files:
        title = title or 'From my files'
        if data.get('id') or manuscript or outline_text:
            raise ValueError('Write from my files starts a new blog from uploaded files.')
    profile = data.get('profile') or None
    if profile:
        studio.voice_pin(root, profile)
    sources = data.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 50 or len(set(sources)) != len(sources):
        raise ValueError('Select at most 50 different sources.')
    for source in sources:
        studio.item(root, 'sources', source)
    if from_files:
        readable = [
            source
            for source in sources
            if studio.item(root, 'sources', source)[1]['status'] == 'ready'
        ]
        if not readable:
            raise ValueError('Upload at least one file with text first.')
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
    if data.get('id') and mode == 'from-outline' and not existing:
        record['mode'] = 'from-outline'
        record['stop_point'] = stop
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
    research = research_scope(research, record['sources'])
    if from_files and research == 'supplied-only':
        research = 'none'  # The files are read at every step; only the web adds research stages.
    pipeline = [] if research == 'none' else ['research-plan', 'research']
    pipeline += (
        (['draft', 'review', 'package'] if mode == 'revise' else ['review', 'package'])
        if existing
        else ['draft', 'review', 'package']
        if mode == 'from-outline'
        else ['outline', 'draft', 'review', 'package']
    )
    pipeline = pipeline[: pipeline.index(stop) + 1]
    if from_files:
        # Three angles first; the chosen one starts the pipeline above (see choose_angle).
        pipeline = ['angles']
        record['stop_point'] = stop
        record['mode'] = 'from-files'
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
    if from_files:
        run['after_angles'] = {'research': research, 'stop': stop}
        run['files_note'] = text(data.get('goal', ''), 'goal')
        # The uploaded files this blog pinned; a deletion keeps them with it.
        record['material'] = [
            entry['source_id'] for entry in record['sources'] if 'material' in entry['purposes']
        ]
    import studios_config

    shared, problem = studios_config.read()
    if problem:
        raise ValueError(problem)
    assistant = shared.get('assistant') or {}
    same_agent = assistant.get('agent') == engine
    contract = research_contract.snapshot() if research != 'none' else None
    if contract:
        run['research_contract'] = contract
    run['review_policy'] = review_policy.snapshot(shared)
    if review_policy.level(run) != 'step_by_step':
        run['schema'] = 2
    if contract:
        run['schema'] = 3
    run['model_profiles'] = model_profiles.snapshot(
        shared,
        engine,
        assistant.get('model') if same_agent else None,
        assistant.get('effort') if same_agent else None,
    )
    if selected_brand:
        run['brand'] = selected_brand
    inputs(root, record, run)  # Refuse unusable context before creating a partial blog.
    if not data.get('id'):
        directory.mkdir()
        studio.write_json(studio.inside(root, '.active-article.json'), {'id': record['id']})
    if outline_text:
        studio.save_artifact(directory, 'outline', outline_text, record, 'author supplied outline')
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
    if stage == 'angles' and len(angles(result['content'])) != 3:
        raise ValueError('Return exactly three angles, each under its own ## heading.')
    directory, record, run = load(root, ident)
    if stage == 'research' and run.get('research_contract'):
        research_contract.read_bundle(directory / 'research')
        if result['content'] != (directory / 'research/report.md').read_text():
            raise ValueError('Submit the saved, independently reviewed research report.')
    if stage == 'review' and run.get('editor_check'):
        from manuscript_editor import record_review

        result = record_review(root, directory, record, run, result)
    pin = basis(root, directory, record, run, stage)
    filename = STAGES[stage][1]
    if stage == 'draft' and (directory / 'DRAFT.md').is_file():
        from text_checks import preserve

        check = preserve((directory / 'DRAFT.md').read_text(), result['content'])
        result['notes'] += '\nPreservation check: ' + json.dumps(check)
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
        'model_purpose': previous.get('model_purpose', stage),
    }
    if stage != 'angles' and review_policy.automatic(run, 'blog', stage, run['pipeline'][-1]):
        _accept(directory, run, stage, 'review-policy')
        review_policy.receipt(run, stage, run['stages'][stage], studio.now())
    save(root, directory, record, run, 'Submitted ' + stage)
    return survey(root, ident)


def _accept(directory, run, stage, by):
    run['stages'][stage].update(status='approved', accepted_by=by)
    approved_hash = run['stages'][stage]['hash']
    studio.atomic(
        studio.inside(
            directory, 'history', 'derived-blog-approved-' + stage + '-' + approved_hash + '.md'
        ),
        studio.inside(directory, STAGES[stage][1]).read_bytes(),
    )
    run.setdefault('approved', {})[stage] = approved_hash


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
    elif action == 'approve' and stage == 'angles':
        raise ValueError(
            'Choose one of the angles with run choose, or ask for three different ones.'
        )
    elif action == 'approve':
        if (
            not stage
            or next(row['status'] for row in found['stages'] if row['stage'] == stage) != 'draft'
        ):
            raise ValueError(
                'Only a current submitted draft can be approved. Read awaits in run status: '
                'steps the review level accepted automatically need no approval.'
            )
        _accept(directory, run, stage, 'page' if page else 'conversation')
    elif action == 'changes':
        if not stage:
            raise ValueError('This run is complete. Start a new revision in chat.')
        request = text(request, 'change request', 8000, required=True)
        run['stages'].setdefault(stage, {})['status'] = 'pending'
        run['stages'][stage]['request'] = request
        run['stages'][stage]['model_purpose'] = (
            'repair' if stage == 'draft' and found['next'] == 'review' else stage
        )
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
    # The package works from the saved writing, and only evidence checks review against
    # sources. inputs() above still refuses a changed source pin for every step.
    check = run.get('editor_check')
    if stage == 'package' or (stage == 'review' and check and check not in studio.SOURCE_CHECKS):
        payload['sources'] = []
    if (
        run.get('research_contract')
        and stage not in ('research-plan', 'research')
        and run['stages'].get('research')
    ):
        directory, _ = studio.item(root, 'articles', record['id'])
        facts, manifest = research_contract.read_bundle(directory / 'research')
        payload['research_bundle'] = {
            'digest': manifest['digest'],
            'brief': (directory / 'research/brief.md').read_text(),
            'findings': facts['findings'],
            'facts': facts['facts'],
            'sources': facts['sources'],
        }
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
        if stage == 'review' and run.get('editor_check'):
            from manuscript_preview import text_only

            payload['documents']['manuscript'] = text_only(payload['documents']['manuscript'])
    if run.get('mode') == 'from-outline':
        payload['documents']['outline'] = (directory / 'OUTLINE.md').read_text()
    saved = run['stages'].get(stage, {})
    request = saved.get('request', '') or run.get('editor_request', '')
    # A note for this step is kept beside the run, outside its versioned state, so leaving
    # one never changes the version a worker is checked against.
    note = (engine(root).local(ident).get('notes') or {}).get(stage, '')
    payload['changes'] = '\n'.join(part for part in (request, note) if part)
    if len(json.dumps(payload)) > 600_000:
        raise ValueError('This job needs smaller source excerpts. Continue it in chat.')
    # A request against a version the author has already seen, or their own manuscript,
    # edits it. Otherwise (a developed idea, a first attempt) it directs a new document.
    edit = stage != 'angles' and bool(
        request
        and payload['documents'].get(stage, '').strip()
        and not (stage == 'review' and run.get('editor_check'))
        and (saved.get('hash') or (stage == 'draft' and run['existing']))
    )
    references = Path(__file__).resolve().parents[1] / 'references'
    if edit:
        guidance = (
            f'Edit the saved {STAGES[stage][0].lower()} in documents.{stage}. This is a minimal '
            'edit, not a rewrite: apply the author’s request at the end of this guidance and '
            'keep everything else verbatim.\n\n' + (references / 'minimal-edits.md').read_text()
        )
    elif stage == 'draft' and run['existing']:
        guidance = (
            'Revise the supplied manuscript in the scope of its brief. Preserve its stance, '
            'meaningful qualifiers and author voice; retain unsupported claims as questions '
            'rather than inventing support.\n\n' + (references / GUIDES[stage]).read_text()
        )
    else:
        guidance = STAGES[stage][2] + '\n\n' + (references / GUIDES[stage]).read_text()
    guidance += '\n\n' + (references / 'style/house.md').read_text()
    if stage in ('draft', 'review'):
        requested = run.get('editor_check')
        guides = ['modules/blog-voice-check.md', 'style/software.md']
        if requested in ('polish', 'humanization', None):
            guides.append('modules/blog-humanize.md')
        if requested in ('factual-support', None):
            guides += ['modules/blog-fact-check.md', 'review/evidence.md']
        if requested == 'geo':
            guides += ['modules/blog-geo-review.md', 'review/evidence.md']
        if requested == 'shape':
            guides.append('modules/copywriting.md')
        for guide in guides:
            guidance += '\n\n' + (references / guide).read_text()
        guidance += '\nApply only the requested checks and editing scope. Preserve the original author voice, stance and qualifiers. Report exact passages, evidence and unresolved gaps. Linked helper instructions are guidance; do not claim tools ran.'
    if stage in ('draft', 'review'):
        from text_checks import lint

        rules = payload['voice'].get('rules', '{}')
        rules = json.loads(rules) if isinstance(rules, str) else rules
        payload['mechanical_checks'] = lint(
            payload['documents'].get('manuscript', payload['documents'].get('draft', '')),
            rules or {},
        )
    if run.get('editor_check') in ('polish', 'humanization'):
        guidance += (
            '\n\n' + (references / 'blogforge/voice/assets/ai-tells/patterns.md').read_text()
        )
    if stage == 'angles':
        if payload['sources']:
            guidance += '\nThe uploaded files are in sources, with their names; name them in each angle’s Leans on line.'
        if request and payload['documents'].get('angles', '').strip():
            guidance += (
                '\nThe author set aside the saved angles in documents.angles. Propose three '
                'different angles that honor the author’s request; do not repeat the earlier ones.'
            )
    if run.get('mode') == 'ideas' and stage == 'outline':
        guidance += '\nReturn three distinct blog angles with audience, thesis, evidence needed and tradeoffs. Stop for the author to choose; do not draft the blog.'
    if run.get('mode') == 'from-outline':
        guidance += '\nUse the supplied outline as authoritative structure. Preserve headings and order unless explicitly asked to restructure.'
    if stage == 'review' and run.get('editor_check'):
        payload['response_kind'] = 'editing-review'
        guidance += (
            '\nReturn the structured editing review required by the response schema: summary, findings and notes. '
            'Use at most 100 findings with distinct IDs containing only letters, digits, underscores or hyphens. '
            'Each before must be a verbatim contiguous quote from documents.manuscript, including its exact punctuation and whitespace. '
            'Choose a shorter quote within one plain-text run when a sentence crosses Markdown formatting or link boundaries. '
            'Do not quote a rendered or paraphrased version of the Markdown. '
            'Use kind edit/comment, after as the proposed replacement (empty for comments or deletion), '
            'context as exact surrounding manuscript text only when needed to disambiguate (otherwise empty), '
            'a concise reason, evidence as a source passage or an explanation of editorial judgment, '
            'and verdict supported/unsupported/contradicted/editorial. '
            'Do not invent a clean verdict. Return an empty findings list only with explicit coverage and limitations.'
        )
    if request:
        # The request is the author's instruction for this step, not untrusted document data.
        guidance += (
            '\n\nAUTHOR’S REQUEST FOR THIS STEP, from the author through Blog Studio. '
            + (
                'Apply it as a minimal edit of documents.' + stage + ' and change nothing '
                'it does not require.'
                if edit
                else 'Follow it within this step.'
            )
            + '\n"""\n'
            + request
            + '\n"""'
        )
    if run.get('model_profiles'):
        found['model_selection'] = model_profiles.route(
            run,
            'Blog Studio',
            stage,
            purpose=run['stages'].get(stage, {}).get('model_purpose', stage),
        )
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

    def note_stage(self, ident, found, local=None):
        """The stage a note left now would go with: the next job that starts. While a
        submitted stage waits for a decision, or a worker is on the next stage, that is the
        stage after it; None when there is no later stage."""
        if found['complete'] or not found['next']:
            return None
        local = self.local(ident) if local is None else local
        names = [row['stage'] for row in found['stages']]
        at = names.index(found['next'])
        busy = found['awaits'] == 'decision' or (
            local.get('status') == 'working' and self.current == ident
        )
        if not busy:
            return found['next']
        return names[at + 1] if at + 1 < len(names) else None

    def describe(self, ident, listing=False):
        found = survey(self.root, ident, listing)
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
        decisions = found.get('decisions') or []
        return {
            **found,
            'team': bool(space(self.root) and space(self.root).address),
            'driver': owner,
            'status': status,
            'notes': local.get('notes') or {},
            'note_stage': self.note_stage(ident, found, local),
            # The job's start is timed only while it is the one working here.
            'started_at': local.get('started_at') if status == 'working' else None,
            'touched': decisions[-1]['at'] if decisions else None,
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
            from team_workspace import guard as team_guard

            team_guard(self.root, ident)
            found, payload, guidance = job(self.root, ident)
            choice = found.get('model_selection')
            if choice:
                directory, record, run = load(self.root, ident)
                attempt = sum(job['step'] == found['next'] for job in run.get('model_jobs', [])) + 1
                model_profiles.audit(
                    run, choice, attempt, 'research' if found['next'] == 'research' else 'write'
                )
                save(self.root, directory, record, run, 'Selected model for ' + found['next'])
                # Audit metadata changes the optimistic token, so use the freshly saved version.
                found['expected'] = survey(self.root, ident)['expected']
            local.update(status='working', error='', started_at=studio.now())
            self.keep_local(ident, local)
            self.current = ident
            self.stop.clear()
            # Includes session metadata as well as run/documents: a parallel edit wins.
            directory, _, run = load(self.root, ident)
            session = (directory / 'session.json').read_bytes()
            review_source = (
                (directory / 'DRAFT.md').read_text()
                if found['next'] == 'review' and run.get('editor_check')
                else None
            )
        pending = None
        review_attempts = []
        try:
            if found['next'] == 'research' and run.get('research_contract'):
                import synthesis_research

                pending = tempfile.TemporaryDirectory(prefix='blog-research-draft-')
                target = Path(pending.name)
                if (directory / research_contract.CASE).is_dir():
                    research_contract.copy_case(
                        directory / research_contract.CASE, target / research_contract.CASE
                    )
                result = synthesis_research.generate(
                    target, run, payload, self.worker, seconds=found['seconds'], stop=self.stop
                )
            else:
                started = time.monotonic()
                result = self.worker(
                    found['engine'],
                    payload,
                    guidance,
                    seconds=found['seconds'],
                    web=found['next'] == 'research' and payload['research_policy'] == 'web-allowed',
                    stop=self.stop,
                    model_selection=found.get('model_selection'),
                )
            if found['next'] == 'review' and run.get('editor_check'):
                from manuscript_editor import validate_review

                try:
                    validate_review(result, review_source)
                except ValueError as error:
                    review_attempts.append({'response': result, 'error': str(error)})
                    remaining = found['seconds'] - (time.monotonic() - started)
                    if self.stop.is_set() or self.closed.is_set() or remaining <= 0:
                        raise error
                    result = self.worker(
                        found['engine'],
                        {
                            **payload,
                            'previous_output': result.get('content', ''),
                            'validation_error': str(error),
                        },
                        guidance
                        + '\nCorrect the previous output once using the structured editing review schema. '
                        'Each before must be copied verbatim from the supplied manuscript, preserving punctuation and whitespace. '
                        'Use kind edit/comment, verdict editorial for writing advice, and a short evidence explanation. '
                        'Use IDs containing only letters, digits, underscores or hyphens. '
                        'Do not remove legitimate findings to evade validation.',
                        seconds=max(1, int(remaining)),
                        web=False,
                        stop=self.stop,
                        model_selection=found.get('model_selection'),
                    )
                    try:
                        validate_review(result, review_source)
                    except ValueError as error:
                        review_attempts.append({'response': result, 'error': str(error)})
                        raise
            with studio.locked(self.root):
                if self.stop.is_set() or self.closed.is_set():
                    return
                if (directory / 'session.json').read_bytes() != session:
                    raise ValueError(
                        'The blog changed while the worker ran. Your edit was kept. Retry from the latest version.'
                    )
                from team_workspace import before

                before(self.root, ident)
                if pending:
                    guard(self.root, ident, found['expected'], page=True)
                    research_contract.copy_case(
                        target / research_contract.CASE, directory / research_contract.CASE
                    )
                    research_contract.publish(
                        target / research_contract.CASE, directory / 'research'
                    )
                submit(self.root, ident, found['next'], result, found['expected'], page=True)
                state = self.local(ident)
                state.update(status='waiting-for-approval', error='')
                if run.get('editor_check'):
                    state['enabled'] = False
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
                    if review_attempts:
                        try:
                            folder = studio.inside(self.root, '.blog-runs', 'diagnostics')
                            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                            folder.chmod(0o700)
                            diagnostic = folder / (ident + '.json')
                            studio.write_json(
                                diagnostic,
                                {
                                    'check': run.get('editor_check'),
                                    'at': studio.now(),
                                    'manuscript_sha256': studio.digest(review_source.encode()),
                                    'attempts': review_attempts,
                                },
                            )
                            diagnostic.chmod(0o600)
                        except OSError:
                            message += ' The private failure diagnostic could not be saved.'
                    state.update(enabled=False, status='failed', error=message[:500])
                    self.keep_local(ident, state)
        finally:
            if pending:
                pending.cleanup()
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
        import tool_jobs

        with studio.locked(self.root):
            tool_jobs.recover(self.root)
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
            if not self.closed.is_set():
                try:
                    tool_jobs.once(self)
                except Exception:
                    # A tool job that failed to be recorded never takes the loop down with it.
                    self.current = None
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
                found = engine(root).describe(ident, listing=True)
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
                            'editor_check',
                            'team',
                            'driver',
                            'touched',
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
    rows.sort(key=lambda row: row.get('touched') or '', reverse=True)
    import blog_delete

    return {'items': rows, 'total': len(rows), 'deleted': blog_delete.deleted(root)}


def options(root):
    def records(kind):
        result = []
        for path in sorted(studio.inside(root, kind).glob('*/record.json')):
            record = studio.read_json(path)
            if kind == 'sources' and 'material' in record.get('purposes', []):
                continue  # Uploaded for one run; chosen on its own screen, not from the library.
            if kind != 'profiles' or record.get('status') != 'retired':
                result.append(
                    {'id': record['id'], 'name': record['name'], 'status': record['status']}
                )
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
    from manuscript_preview import fields

    def preview_file(path):
        body = path.read_text()
        return {'content': body, **fields(body)}

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
        **fields(content),
        'previous': previous,
        'diff': differences[:4000],
        'diff_truncated': len(differences) > 4000,
        'stage': stage,
        'review_level': found['review_level'],
        # Grouped reviews read the approved stages together; the final stop always brings
        # the approved draft back beside the handoff notes, whatever the review level.
        'bundle': [
            {
                'stage': item['stage'],
                'label': item['label'],
                **preview_file(studio.inside(directory, item['path'])),
            }
            for item in found['stages']
            if stage == found['next']
            and item['stage'] != stage
            and item['status'] == 'approved'
            and (
                found['review_level'] != 'step_by_step'
                or item['stage'] == 'draft'
                and stage == run['pipeline'][-1]
            )
        ],
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
    if (
        set(data)
        - {'id', 'expected', 'request', 'stage'}
        - ({'seconds'} if action == 'retry' else set())
    ):
        raise ValueError('Unknown run field.')
    # Every page control is bound to the version the person was shown.
    found = survey(root, ident)
    if not data.get('expected') or data['expected'] != found['expected']:
        raise ValueError('This blog changed. Reload before deciding.')
    if action == 'develop':
        guard(root, ident, data['expected'], page=True)
        directory, record, run = load(root, ident)
        if run.get('mode') == 'from-files':
            choose_angle(root, directory, record, run, found, data.get('request', ''))
            return runner.control(ident, 'resume')
        if run.get('mode') not in ('ideas', 'outline') or not (directory / 'OUTLINE.md').is_file():
            raise ValueError('Choose a saved idea or outline before developing it.')
        request = text(data.get('request', ''), 'selected angle', 8000, required=True)
        run['mode'] = 'write'
        run['pipeline'] = ['outline', 'draft']
        run['stages'] = {
            'outline': {
                'status': 'pending',
                'request': 'Develop this selected angle or structure: ' + request,
            }
        }
        record['stop_point'] = 'draft'
        save(root, directory, record, run, 'Selected angle for drafting')
        return runner.control(ident, 'resume')
    if action == 'start':
        if found['approval'] == 'conversation':
            decide(root, ident, data['expected'], 'handoff')
        return runner.control(ident, 'resume')
    if action == 'retry' and 'seconds' in data:
        # Try again with more time: the limit that just ran out is raised for every step.
        seconds = data['seconds']
        if type(seconds) is not int or not 30 <= seconds <= 3600:
            raise ValueError('Choose a step time limit between 30 and 3600 seconds.')
        if found['approval'] != 'page':
            raise ValueError('Choose Run this from here to move this blog from chat to the page.')
        directory, record, run = load(root, ident)
        run['seconds'] = seconds
        save(root, directory, record, run, f'Step time limit set to {seconds} seconds')
    if action in ('resume', 'retry', 'pause', 'stop'):
        return runner.control(ident, action)
    if action == 'note':
        # A note for the next job that starts. It is kept beside the run, in its local
        # state, never in the versioned record: leaving one stops nothing and changes no
        # version a running worker is checked against. job() folds it into that stage's
        # request when the stage starts.
        request = text(data.get('request', ''), 'note', 8000, required=True)
        stage = runner.note_stage(ident, found)
        if stage is None:
            raise ValueError(
                'There is no later step for a note to go with. Ask for changes to '
                + (STAGES[found['next']][0].lower() if found['next'] else 'a stage')
                + ' instead.'
            )
        state = runner.local(ident)
        notes = state.setdefault('notes', {})
        notes[stage] = (notes.get(stage, '') + '\n' + request).strip()
        runner.keep_local(ident, state)
        return {**runner.describe(ident), 'noted': stage}
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


def angles(content):
    """The saved angles: each `## Title` heading with the line beneath it."""
    found = []
    lines = str(content or '').splitlines()
    for index, line in enumerate(lines):
        match = re.fullmatch(r'##\s+(.+?)\s*#*\s*', line)
        if not match:
            continue
        says = ''
        for later in lines[index + 1 :]:
            if later.startswith('#'):
                break
            if later.strip():
                says = re.sub(r'^[-*]\s+', '', later.strip())
                break
        title = re.sub(r'^\d+[.)]\s*', '', match.group(1)).replace('**', '').strip()
        found.append({'title': title, 'says': says})
    return found


def choose_angle(root, directory, record, run, found, request):
    """The chosen angle becomes the blog's title, point and reader; the normal run follows."""
    saved = run['stages'].get('angles', {})
    if found['next'] != 'angles' or saved.get('status') != 'draft':
        raise ValueError('Wait for the three angles before choosing one.')
    request = text(request, 'selected angle', 8000, required=True)
    title, _, note = request.partition('\n')
    doc = (directory / STAGES['angles'][1]).read_text()
    angle = next(
        (item for item in angles(doc) if item['title'].casefold() == title.strip().casefold()),
        None,
    )
    if angle is None:
        raise ValueError('Choose one of the saved angles by its heading.')
    headings = [item['title'].casefold() for item in angles(doc)]
    if len(set(headings)) != len(headings):
        raise ValueError('Two angles share a heading. Ask for three different ones instead.')
    parts = [part.strip() for part in re.split(r'\s[·•|]\s', angle['says'])]
    audience = parts[0] if len(parts) >= 2 else ''
    point = parts[1] if len(parts) >= 2 else angle['says']
    record['title'] = angle['title']
    record.setdefault('writing_preferences', {})
    if audience:
        record['writing_preferences']['audience'] = audience
    run['brief'] = {
        'goal': point or run['brief']['goal'],
        'audience': audience or run['brief']['audience'],
    }
    after = run.get('after_angles') or {'research': 'none', 'stop': 'package'}
    pipeline = ['research-plan', 'research'] if after['research'] == 'web-allowed' else []
    pipeline += ['outline', 'draft', 'review', 'package']
    # The angles stay at the head of the run, decided by the pick.
    run['pipeline'] = ['angles'] + pipeline[: pipeline.index(after['stop']) + 1]
    run['chosen_angle'] = {'title': angle['title'], 'says': angle['says']}
    _accept(directory, run, 'angles', 'page' if run['approval'] == 'page' else 'conversation')
    run['stages'] = {
        'angles': run['stages']['angles'],
        'outline': {
            'status': 'pending',
            'request': (
                'Develop this selected angle: '
                + angle['title']
                + ('\n' + angle['says'] if angle['says'] else '')
                + ('\n' + note.strip() if note.strip() else '')
            ),
        },
    }
    record['stop_point'] = after['stop']
    # The brief and title just changed with the pick; the decided angles are pinned to them.
    run['stages']['angles']['basis'] = basis(root, directory, record, run, 'angles')
    save(root, directory, record, run, 'Chose the angle: ' + angle['title'])


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
        '--research', choices=('none', 'supplied-only', 'web-allowed'), default=None
    )
    create_cmd.add_argument(
        '--stop', choices=('outline', 'draft', 'review', 'package'), default='package'
    )
    create_cmd.add_argument('--engine', choices=('codex', 'claude'))
    create_cmd.add_argument('--seconds', type=int, default=600)
    create_cmd.add_argument('--source', action='append', default=[])
    create_cmd.add_argument('--mode', choices=MODES, default='write')
    create_cmd.add_argument('--manuscript')
    create_cmd.add_argument('--outline-text')
    commands.add_parser('list')
    for name in ('status', 'submit', 'approve', 'changes', 'handoff', 'choose'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--id', required=True)
        if name != 'status':
            cmd.add_argument('--expected', required=True)
        if name == 'choose':
            cmd.add_argument('--angle', required=True)
            cmd.add_argument('--note', default='')
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
                if k not in ('root', 'group', 'action', 'source', 'compact') and v is not None
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
        if args.action == 'choose':
            found = guard(root, args.id, args.expected)
            directory, record, run = load(root, args.id)
            if run.get('mode') != 'from-files':
                raise ValueError('Only a blog written from files chooses an angle.')
            choose_angle(root, directory, record, run, found, args.angle + '\n' + (args.note or ''))
            return survey(root, args.id)
        return decide(
            root,
            args.id,
            args.expected,
            args.action,
            getattr(args, 'request', ''),
            target=getattr(args, 'stage', None),
        )
