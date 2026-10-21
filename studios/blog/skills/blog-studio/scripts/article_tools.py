"""Voice, interview and repurposing tasks using existing article/profile records."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import manuscript_editor
import studio
import tool_jobs

REFERENCES = Path(__file__).resolve().parents[1] / 'references/modules'
FORMATS = {
    'linkedin': 'LinkedIn feed copy',
    'newsletter': 'Newsletter introduction',
    'email': 'Announcement email',
    'summary': 'Short summary',
    'thread': 'Short thread',
}


def text(value, label, maximum=2000, required=True):
    if not isinstance(value, str) or len(value) > maximum or required and not value.strip():
        raise ValueError(f'Give {label} up to {maximum} characters.')
    return value.strip()


def fingerprint(value):
    return studio.digest(json.dumps(value, sort_keys=True).encode())


def samples(root, selected, purpose='voice-sample'):
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= 10
        or len(set(selected)) != len(selected)
    ):
        raise ValueError(
            'Choose one to ten different authored voice samples.'
            if purpose == 'voice-sample'
            else 'Choose one to ten different examples of this kind of writing.'
        )
    if purpose == 'voice-sample':
        studio.validate_samples(root, selected)
    else:
        import styles

        styles.validate_samples(root, selected)
    from manuscript_preview import text_only

    found = []
    for ident in selected:
        folder, record = studio.item(root, 'sources', ident)
        body = text_only((folder / 'content.md').read_text())
        if len(body) > 80_000:
            raise ValueError(
                'Use shorter authored voice samples for learning.'
                if purpose == 'voice-sample'
                else 'Use shorter examples for learning.'
            )
        found.append({'id': ident, 'revision': record['revision'], 'record': record, 'text': body})
    return found


def background(root, ident):
    """Author background from a readable source classified as author-background."""
    folder, record = studio.item(root, 'sources', ident)
    if 'author-background' not in record['purposes'] or record['status'] != 'ready':
        raise ValueError(
            'Author background must be a readable source classified as author-background.'
        )
    body = (folder / 'content.md').read_text(encoding='utf-8')
    if len(body) > 20_000:
        raise ValueError('Use a shorter author background.')
    return body


def profile(root, ident):
    folder, record = studio.item(root, 'profiles', ident)
    guide = (folder / 'VOICE.md').read_text()
    rules = studio.read_json(folder / 'rules.json')
    return {
        **record,
        'guide': guide,
        'rules': rules,
        'expected': fingerprint([record, guide, rules]),
    }


def voices(root):
    profiles, sources = [], []
    for file in sorted(studio.inside(root, 'profiles').glob('*/record.json')):
        try:
            record = studio.read_json(file)
            profiles.append({key: record.get(key) for key in ('id', 'name', 'revision', 'status')})
        except (ValueError, OSError):
            continue
    for file in sorted(studio.inside(root, 'sources').glob('*/record.json')):
        record = studio.read_json(file)
        if 'voice-sample' in record.get('purposes', []) and record.get('status') == 'ready':
            sources.append({key: record.get(key) for key in ('id', 'name', 'author', 'revision')})
    return {'profiles': profiles, 'samples': sources, **studio.sample_choices(root, 'voice-sample')}


def article_basis(root, ident):
    folder, record = studio.item(root, 'articles', ident)
    return fingerprint(studio.fingerprints(root, folder, record))


def voice_basis(root, data):
    selected = samples(root, data['samples'])
    current = profile(root, data['profile'])['expected'] if data.get('profile') else None
    parts = [selected, current]
    if data.get('background'):
        parts.append(background(root, data['background']))  # unchanged basis without one
    return fingerprint(parts), selected


def style_basis(root, data):
    import styles

    selected = samples(root, data['samples'], 'style-sample')
    current = styles.detail(root, data['style'])['expected'] if data.get('style') else None
    return fingerprint([selected, current]), selected


def refuse_retired_style(root, metadata):
    """Learning into a retired style would quietly bring it back."""
    import styles

    if metadata.get('style') and styles.detail(root, metadata['style'])['status'] == 'retired':
        raise ValueError('This style is retired. Restore it in chat, or learn a new style.')


def interview(root, ident):
    folder, record = studio.item(root, 'articles', ident)
    state_file = folder / 'derived/interview.json'
    state = (
        studio.read_json(state_file)
        if state_file.is_file()
        else {
            'schema': 1,
            'answers': [],
            'question': 'What is the main point you want this reader to understand?',
            'question_id': 'main-point',
        }
    )
    notes = (folder / 'INTERVIEW.md').read_text() if (folder / 'INTERVIEW.md').is_file() else ''
    expected = fingerprint([record, state.get('answers', []), state.get('question'), notes])
    return {
        **state,
        'id': ident,
        'title': record['title'],
        'notes': notes,
        'expected': expected,
        'outline': (folder / 'OUTLINE.md').is_file(),
        'outline_content': (folder / 'OUTLINE.md').read_text()
        if (folder / 'OUTLINE.md').is_file()
        else '',
    }


def save_interview(root, ident, state):
    folder, _ = studio.item(root, 'articles', ident)
    studio.write_json(
        folder / 'derived/interview.json',
        {
            key: value
            for key, value in state.items()
            if key not in ('id', 'title', 'notes', 'expected', 'outline', 'outline_content')
        },
    )


def request(root, data):
    kind = data.get('kind')
    operation = data.get('operation')
    metadata = {}
    if kind == 'voice-learn':
        if data.get('confirmed') is not True:
            raise ValueError('Confirm these are permitted authored voice samples before analysis.')
        name = text(data.get('name'), 'an author/profile name', 200)
        metadata = {'name': name, 'samples': data.get('samples'), 'profile': data.get('profile')}
        if data.get('background'):
            metadata['background'] = data['background']
        basis, selected = voice_basis(root, metadata)
        payload = {'author': name, 'authored_samples': selected}
        guidance = (
            (REFERENCES / 'blog-voice-profile.md').read_text()
            + '\nInfer a provisional voice guide from these authored samples only. Describe observable style and uncertainty. Separate voice from factual expertise, supplied branding and generic house style. Do not invent biography or anecdotes. Return the editable guide as Markdown, with a short synthetic audition paragraph clearly labeled invented sample text, not author experience. Do not confirm or apply the profile.'
        )
        if metadata.get('background'):
            # Without a background the job is exactly what it was before backgrounds existed.
            payload['author_background'] = background(root, metadata['background'])
            guidance += (
                '\nauthor_background is biography and expertise supplied by the author for '
                'identity; it is not prose to imitate, and career facts are never inferred from '
                'the samples.'
            )
    elif kind == 'style-learn':
        if data.get('confirmed') is not True:
            raise ValueError('Confirm you may analyze these examples before starting.')
        name = text(data.get('name'), 'a style name', 200)
        metadata = {'name': name, 'samples': data.get('samples'), 'style': data.get('style')}
        refuse_retired_style(root, metadata)
        basis, selected = style_basis(root, metadata)
        payload = {'style_name': name, 'examples': selected}
        guidance = (
            'Describe the kind of writing these examples share, as an editable Markdown style '
            'guide named ' + name + '. Cover the structure and order of parts, opening and closing '
            'moves, typical length, heading habits, what every example includes, what varies, the '
            'register a reader of this kind expects, and what does not belong. Ignore who wrote '
            'them: no voice, biography, first person or author preferences. Where the examples '
            'disagree, say so. With a single example, say the guide is thin and provisional. End '
            'with two short lists, "A reader expects" and "Does not belong". Add one short '
            'synthetic audition paragraph clearly labeled invented sample text. Do not confirm '
            'or apply the style.'
        )
    elif kind == 'voice-audition':
        selected = profile(root, data.get('profile'))
        sample = text(data.get('content'), 'a short audition passage', 10_000)
        metadata = {'profile': selected['id'], 'profile_revision': selected['revision']}
        basis = selected['expected']
        payload = {'voice_guide': selected['guide'], 'passage': sample}
        guidance = 'Show a short sample applying only the supplied voice to this passage. Preserve its facts and uncertainty, invent no experience. This is an audition, not a profile update or article save.'
    elif kind == 'repurpose':
        ident = data.get('id')
        current = manuscript_editor.read(root, ident)
        if not current['content']:
            raise ValueError('Save the source manuscript first.')
        chosen = data.get('format')
        if chosen not in FORMATS:
            raise ValueError('Choose a listed copy format.')
        length = data.get('words', 150)
        if type(length) is not int or not 30 <= length <= 1500:
            raise ValueError('Choose a target from 30 to 1500 words.')
        folder, record = studio.item(root, 'articles', ident)
        metadata = {
            'article': ident,
            'format': chosen,
            'words': length,
            'source_sha256': studio.digest(current['content'].encode()),
            'voice': record['voice'],
        }
        basis = article_basis(root, ident)
        voice = record['voice']
        if voice.get('mode') == 'profile':
            location, _ = studio.item(root, 'profiles', voice['profile_id'])
            voice = {
                **voice,
                'guide': (location / 'revisions' / str(voice['revision']) / 'VOICE.md').read_text(),
            }
        payload = {
            'source': current['content'],
            'voice': voice,
            'format': FORMATS[chosen],
            'target_words': length,
            'audience': text(data.get('audience', ''), 'the reader', 2000, False),
            'article_url': text(data.get('url', ''), 'the actual article URL', 2000, False),
        }
        if payload['article_url']:
            from urllib.parse import urlsplit

            parsed = urlsplit(payload['article_url'])
            if (
                parsed.scheme not in ('https', 'http')
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError(
                    'Give an actual public article URL without credentials, or leave it blank.'
                )
        guidance = (
            (REFERENCES / 'blog-repurpose.md').read_text()
            + '\nPrepare only the selected format at approximately the requested editorial length. Keep essential qualifiers and the article’s supported facts and voice. Do not invent URLs, offers, quotations or experience. Missing article URLs remain clearly marked [ARTICLE URL]. This prepares copy only; send, post, schedule and recipient selection are unavailable. No current platform hard limit has been verified; report only actual counts.'
        )
    elif kind in ('interview-question', 'interview-outline'):
        ident = data.get('id')
        current = interview(root, ident)
        if kind == 'interview-outline' and not any(
            item.get('answer') for item in current['answers']
        ):
            raise ValueError('Record at least one substantive answer before outlining.')
        metadata = {'article': ident}
        basis = current['expected']
        folder, record = studio.item(root, 'articles', ident)
        payload = {
            'article_title': record['title'],
            'preferences': record.get('writing_preferences', {}),
            'answers': current['answers'],
            'notes': current['notes'],
        }
        guidance = (REFERENCES / 'blog-author-interview.md').read_text() + (
            '\nReturn exactly one short adaptive question as the content, up to 1000 characters. Reuse known facts and ask only for a meaningful remaining gap; do not force a fixed question count.'
            if kind == 'interview-question'
            else '\nReturn an outline grounded only in recorded answers and author-reported experience, labeling missing evidence. Do not write a draft or claim the outline was approved.'
        )
    else:
        raise ValueError('Choose a supported contextual task.')
    result = tool_jobs.create(root, operation, kind, payload, guidance, basis, metadata)
    import blog_runner

    blog_runner.engine(root).wake.set()
    return result


def apply(root, data):
    job = tool_jobs.read(root, data.get('job'))
    if job.get('applied'):
        return job['applied']
    if job['status'] != 'ready':
        raise ValueError('Wait for a complete result before saving it.')
    metadata, kind = job['metadata'], job['kind']
    if metadata.get('article'):
        from team_workspace import guard

        guard(root, metadata['article'])
        current = manuscript_editor.read(root, metadata['article'])
        if current['working']:
            raise ValueError('Pause the writing job before saving this tool result.')
    if kind == 'voice-learn':
        basis, _ = voice_basis(root, metadata)
    elif kind == 'style-learn':
        refuse_retired_style(root, metadata)
        basis, _ = style_basis(root, metadata)
    elif kind == 'voice-audition':
        basis = profile(root, metadata['profile'])['expected']
    elif kind.startswith('interview-'):
        basis = interview(root, metadata['article'])['expected']
    else:
        basis = article_basis(root, metadata['article'])
    if basis != job['basis']:
        raise ValueError(
            'The examples or style changed. Keep this result for comparison and regenerate from the current version.'
            if kind == 'style-learn'
            else 'The source, voice or answers changed. Keep this result for comparison and regenerate from the current version.'
        )
    content = text(
        data.get('content', (job.get('result') or {}).get('content')),
        'the reviewed result',
        200_000,
    )
    if kind == 'voice-learn':
        content = text(content, 'the voice guide', 40_000)
        status = data.get('status', 'provisional')
        if (
            status not in ('provisional', 'confirmed')
            or status == 'confirmed'
            and data.get('confirmed') is not True
        ):
            raise ValueError('Explicitly confirm the reviewed profile, or save it as provisional.')
        with tempfile.TemporaryDirectory(prefix='blog-voice-guide-') as scratch:
            guide = Path(scratch) / 'VOICE.md'
            guide.write_text(content)
            about = None
            if metadata.get('background'):
                about = Path(scratch) / 'BACKGROUND.md'
                about.write_text(background(root, metadata['background']), encoding='utf-8')
            result = studio.profile_command(
                root,
                SimpleNamespace(
                    action='save' if metadata.get('profile') else 'create',
                    id=metadata.get('profile'),
                    name=metadata['name'],
                    guide_file=str(guide),
                    background_file=str(about) if about else None,
                    rules_file=None,
                    status=status,
                    sample=metadata['samples'],
                ),
            )
        receipt = {
            'profile': result['id'],
            'revision': result['revision'],
            'status': result['status'],
        }
    elif kind == 'style-learn':
        import styles

        content = text(content, 'the style guide', 40_000)
        status = data.get('status', 'provisional')
        if (
            status not in ('provisional', 'confirmed')
            or status == 'confirmed'
            and data.get('confirmed') is not True
        ):
            raise ValueError('Explicitly confirm the reviewed style, or save it as provisional.')
        with tempfile.TemporaryDirectory(prefix='blog-style-guide-') as scratch:
            guide = Path(scratch) / 'STYLE.md'
            guide.write_text(content, encoding='utf-8')
            result = styles.command(
                root,
                SimpleNamespace(
                    action='save' if metadata.get('style') else 'create',
                    id=metadata.get('style'),
                    name=metadata['name'],
                    guide_file=str(guide),
                    status=status,
                    sample=metadata['samples'],
                ),
            )
        receipt = {
            'style': result['id'],
            'revision': result['revision'],
            'status': result['status'],
        }
    elif kind == 'repurpose':
        name = studio.identifier(data.get('name'))
        folder, _ = studio.item(root, 'articles', metadata['article'])
        if (folder / 'derived' / (name + '.md')).exists():
            raise ValueError(
                'A copy with this name exists. Choose another name or open the saved copy to edit it.'
            )
        with tempfile.TemporaryDirectory(prefix='blog-derived-copy-') as scratch:
            file = Path(scratch) / 'copy.md'
            file.write_text(content)
            studio.article_command(
                root,
                SimpleNamespace(action='derive', id=metadata['article'], name=name, file=str(file)),
            )
        folder, _ = studio.item(root, 'articles', metadata['article'])
        studio.write_json(
            folder / 'derived' / (name + '.meta.json'),
            {**metadata, 'operation': job['id'], 'created_at': studio.now()},
        )
        receipt = {
            'id': metadata['article'],
            'name': name,
            'status': 'prepared-copy-saved',
            'posted': False,
        }
    elif kind == 'interview-question':
        if len(content) > 1000 or content.count('?') > 1:
            raise ValueError('The result needs one short question. Retry with a focused request.')
        state = interview(root, metadata['article'])
        state.update(question=content, question_id=studio.digest(content.encode())[:16])
        save_interview(root, metadata['article'], state)
        receipt = {'id': metadata['article'], 'status': 'question-saved'}
    elif kind == 'interview-outline':
        folder, record = studio.item(root, 'articles', metadata['article'])
        studio.save_artifact(folder, 'outline', content, record, 'Interview outline for review')
        studio.persist(folder, 'articles', record)
        receipt = {
            'id': metadata['article'],
            'status': 'outline-saved-for-review',
            'approved': False,
            'draft_started': False,
        }
    else:
        raise ValueError('An audition is read-only; it cannot change a profile.')
    job['applied'] = receipt
    job['saved_content'] = content
    tool_jobs.write(root, job)
    return receipt


def answer(root, data):
    from team_workspace import guard

    guard(root, data.get('id'))
    state = interview(root, data.get('id'))
    if data.get('expected') != state['expected']:
        raise ValueError('The interview changed. Reload it before saving this answer.')
    answer = text(data.get('answer', ''), 'an answer', 12_000, False)
    if not answer and data.get('skip') is not True:
        raise ValueError('Answer the question or explicitly skip it.')
    selected = data.get('question_id')
    if selected:
        previous = next((item for item in state['answers'] if item['id'] == selected), None)
        if previous is None:
            raise ValueError('Choose a saved interview answer.')
        previous.update(answer=answer, skipped=not answer, at=studio.now())
        folder, _ = studio.item(root, 'articles', state['id'])
        studio.atomic(
            folder / 'INTERVIEW.md',
            (
                state['notes']
                + '\n\n## Correction: '
                + previous['question']
                + '\n\n'
                + (answer or '(Skipped)')
            ).encode(),
        )
        save_interview(root, state['id'], state)
        return interview(root, state['id'])
    question = state['question']
    state['answers'].append(
        {
            'id': state['question_id'],
            'question': question,
            'answer': answer,
            'skipped': not answer,
            'at': studio.now(),
        }
    )
    folder, record = studio.item(root, 'articles', state['id'])
    notes = state['notes'] + '\n\n## ' + question + '\n\n' + (answer or '(Skipped)')
    studio.atomic(folder / 'INTERVIEW.md', notes.encode())
    state.update(
        question='What important example, caveat or takeaway would you like to add?',
        question_id=studio.digest(notes.encode())[:16],
    )
    save_interview(root, state['id'], state)
    return interview(root, state['id'])


def save_profile(root, data):
    selected = data.get('profile')
    current = profile(root, selected) if selected else None
    if current and data.get('expected') != current['expected']:
        raise ValueError('This voice profile changed. Reload before saving a revision.')
    status = data.get('status', 'provisional')
    if (
        status not in ('provisional', 'confirmed')
        or status == 'confirmed'
        and data.get('confirmed') is not True
    ):
        raise ValueError('Confirm the reviewed voice guide, or save it as provisional.')
    guide = text(data.get('guide'), 'a reviewed voice guide', 40_000)
    name = text(data.get('name', (current or {}).get('name')), 'a profile name', 200)
    chosen = data.get('samples', (current or {}).get('sample_ids', []))
    if not isinstance(chosen, list) or len(chosen) > 10:
        raise ValueError('Choose up to ten authored samples.')
    studio.validate_samples(root, chosen)
    with tempfile.TemporaryDirectory(prefix='blog-voice-profile-') as scratch:
        file = Path(scratch) / 'VOICE.md'
        file.write_text(guide)
        rules_file = None
        if 'rules' in data:
            rules = data['rules']
            studio.validate_rules(rules)
            if len(json.dumps(rules)) > 40_000:
                raise ValueError('Use a rules object up to 40,000 characters.')
            rules_file = Path(scratch) / 'rules.json'
            studio.write_json(rules_file, rules)
        result = studio.profile_command(
            root,
            SimpleNamespace(
                action='save' if current else 'create',
                id=selected,
                name=name,
                guide_file=str(file),
                background_file=None,
                rules_file=str(rules_file) if rules_file else None,
                status=status,
                sample=chosen,
            ),
        )
    return {'profile': result['id'], 'revision': result['revision'], 'status': result['status']}


def retire_profile(root, data):
    current = profile(root, data.get('profile'))
    if current['expected'] != data.get('expected') or data.get('confirmed') is not True:
        raise ValueError('Confirm the current profile before retiring it.')
    record = studio.profile_command(
        root,
        SimpleNamespace(
            action='retire', id=current['id'], expected_revision=current['revision'], confirmed=True
        ),
    )
    return {'profile': record['id'], 'status': 'retired', 'revision': record['revision']}


def job_view(root, ident):
    value = tool_jobs.read(root, ident)
    kind, metadata = value['kind'], value['metadata']
    try:
        if kind == 'voice-learn':
            basis, _ = voice_basis(root, metadata)
        elif kind == 'style-learn':
            basis, _ = style_basis(root, metadata)
        elif kind == 'voice-audition':
            basis = profile(root, metadata['profile'])['expected']
        elif kind.startswith('interview-'):
            basis = interview(root, metadata['article'])['expected']
        else:
            basis = article_basis(root, metadata['article'])
        changed = basis != value['basis']
    except (OSError, ValueError, KeyError):
        changed = True
    return {**tool_jobs.public(value), 'source_changed': changed}


def start_interview(root, data):
    title = text(data.get('title'), 'an interview title', 200)
    audience = text(data.get('audience'), 'the reader', 2000)
    goal = text(data.get('goal'), 'the main goal', 4000)
    args = SimpleNamespace(
        id=None,
        title=title,
        mode='interview',
        author=None,
        profile=None,
        voice='preserve',
        tone='',
        stop='outline',
        research='supplied-only',
        audience=audience,
        blog_type=None,
        review_folder=None,
    )
    operation = data.get('operation')
    ledger = tool_jobs.path(root, operation).with_suffix('.interview')
    signature = fingerprint([title, audience, goal])
    if ledger.exists():
        saved = studio.read_json(ledger)
        if saved['fingerprint'] != signature:
            raise ValueError('This operation belongs to another interview. Start a new interview.')
        return interview(root, saved['article'])
    record = studio.article_command(root, SimpleNamespace(action='create', **vars(args)))
    folder, saved = studio.item(root, 'articles', record['id'])
    saved['writing_preferences'] = {
        **saved.get('writing_preferences', {}),
        'audience': audience,
        'goal': goal,
    }
    studio.persist(folder, 'articles', saved)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.parent.chmod(0o700)
    studio.write_json(ledger, {'fingerprint': signature, 'article': record['id']})
    ledger.chmod(0o600)
    return interview(root, record['id'])


def variants(root, ident):
    folder, _ = studio.item(root, 'articles', ident)
    return {
        'id': ident,
        'variants': [
            {'name': file.stem, 'provenance': studio.read_json(file.with_suffix('.meta.json'))}
            for file in sorted((folder / 'derived').glob('*.md'))
            if file.with_suffix('.meta.json').is_file()
        ][:50],
    }


def variant(root, ident, name):
    folder, _ = studio.item(root, 'articles', ident)
    name = studio.identifier(name)
    file = studio.inside(folder, 'derived', name + '.md')
    meta = studio.inside(folder, 'derived', name + '.meta.json')
    if not file.is_file() or file.stat().st_size > 800_000 or not meta.is_file():
        raise ValueError('Choose a saved channel copy up to 200,000 characters.')
    content, provenance = file.read_text(), studio.read_json(meta)
    draft = folder / 'DRAFT.md'
    changed = not draft.is_file() or studio.digest(draft.read_bytes()) != provenance.get(
        'source_sha256'
    )
    return {
        'id': ident,
        'name': name,
        'content': content,
        'provenance': provenance,
        'expected': fingerprint([content, provenance]),
        'source_changed': changed,
    }


def save_variant(root, data):
    current = variant(root, data.get('id'), data.get('name'))
    if current['expected'] != data.get('expected'):
        raise ValueError(
            'This saved copy changed. Your text is kept; reload and compare before resubmitting.'
        )
    article = manuscript_editor.read(root, current['id'])
    manuscript_editor.guard(root, {'id': current['id'], 'expected': article['expected']})
    content = text(data.get('content'), 'the prepared copy', 200_000)
    with tempfile.TemporaryDirectory(prefix='blog-copy-edit-') as scratch:
        file = Path(scratch) / 'copy.md'
        file.write_text(content)
        studio.article_command(
            root,
            SimpleNamespace(
                action='derive', id=current['id'], name=current['name'], file=str(file)
            ),
        )
    return {
        'id': current['id'],
        'name': current['name'],
        'status': 'prepared-copy-saved',
        'posted': False,
    }
