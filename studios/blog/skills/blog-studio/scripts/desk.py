"""The writing desk: a blog's draft as title, opening and sections, kept with versions.

DRAFT.md is rewritten on every save so Copy, Download, Google Docs, the team library and the
pre-publish check read the same text as before.
"""

import json
import re
import secrets
from types import SimpleNamespace

import studio

DESK = 'desk'
KEEP = 20  # versions kept per part
PARTS = ('title', 'opening')  # plus each section id
LIMIT = 200_000  # characters in one part
LENGTHS = ('style', 'short', 'deep')  # as blog_runner.LENGTHS: usual, short, in depth
CREATE = frozenset(
    {'title', 'manuscript', 'source', 'article', 'style', 'tone', 'length', 'sources', 'library'}
)
FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
TITLE = re.compile(r'# (?!#)(.*\S)\s*')
HEADING = re.compile(r'## (?!#)(.*\S)\s*')


def _id(taken):
    while True:
        value = secrets.token_hex(4)
        if value not in taken:
            taken.add(value)
            return value


def _tidy(lines):
    """Lines as one text without blank lines around it; a first line keeps its indent."""
    return re.sub(r'^(?:[ \t]*\n)+', '', '\n'.join(lines)).rstrip()


def split(markdown, title=''):
    """Title, opening and sections of a Markdown draft.

    The first line is the title when it is a `# ` heading. Each `## ` heading starts a
    section; text before the first one is the opening. A heading inside a fenced code block
    is text, and deeper headings stay inside their section.
    """
    lines = markdown.replace('\r\n', '\n').strip('\n').split('\n')
    found = TITLE.fullmatch(lines[0]) if lines else None
    if found:
        title, lines = found.group(1), lines[1:]
    opening, sections, current, fence, taken = [], [], None, None, set()
    for line in lines:
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
        heading = None if fence is not None or marker else HEADING.fullmatch(line)
        if heading:
            current = {'id': _id(taken), 'heading': heading.group(1), 'brief': '', 'lines': []}
            sections.append(current)
        else:
            (current['lines'] if current else opening).append(line)
    return {
        'title': title.strip(),
        'opening': _tidy(opening),
        'sections': [
            {
                'id': section['id'],
                'heading': section['heading'].strip(),
                'brief': '',
                'text': _tidy(section['lines']),
            }
            for section in sections
        ],
    }


def join(draft):
    """The Markdown the parts make, as DRAFT.md keeps it."""
    parts = []
    if draft.get('title'):
        parts.append('# ' + draft['title'])
    if draft.get('opening'):
        parts.append(draft['opening'])
    for section in draft['sections']:
        parts.append(
            '## ' + section['heading'] + ('\n\n' + section['text'] if section['text'] else '')
        )
    return '\n\n'.join(parts) + '\n'


# The desk record. Every function below expects the caller to hold the studio lock, as the
# page's dispatch and views do (management.py); none of them takes it again.


def _paths(root, ident):
    if not isinstance(ident, str):
        raise ValueError('Choose a blog on the desk.')
    directory, _ = studio.item(root, 'articles', ident)
    return directory, studio.inside(directory, DESK, 'draft.json')


def _source_text(root, ident):
    folder, source = studio.item(root, 'sources', ident)
    path = studio.inside(folder, 'content.md')
    if source['status'] != 'ready' or not path.is_file() or not path.read_text().strip():
        raise ValueError('Choose a draft with readable text.')
    return path.read_text()


def _attach(root, data, record):
    """The sources and library items chosen for this blog, pinned as a run pins them."""
    import blog_runner

    sources = data.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 50 or len(set(sources)) != len(sources):
        raise ValueError('Select at most 50 different sources.')
    for source in sources:
        if not isinstance(source, str):
            raise ValueError('Select at most 50 different sources.')
        studio.item(root, 'sources', source)
    picked = blog_runner.library_picks(root, data.get('library', []), sources)
    for source in sources + list(picked):
        _, found = studio.item(root, 'sources', source)
        record['sources'] = [s for s in record['sources'] if s['source_id'] != source] + [
            {
                'source_id': source,
                'revision': found['revision'],
                'purposes': picked.get(source, found['purposes']),
            }
        ]
    record['material'] = [
        entry['source_id'] for entry in record['sources'] if 'material' in entry['purposes']
    ]


def create(root, data):
    """A new desk blog from a pasted draft (`manuscript`), an uploaded draft (`source`), or a
    blog just started from a Google Doc (`article`), with its kind of post, tone and length.

    The blog writes with its tone only: no default or pinned voice is applied."""
    if not isinstance(data, dict) or set(data) - CREATE:
        raise ValueError('This request has fields the desk does not take.')
    given = [key for key in ('manuscript', 'source', 'article') if data.get(key)]
    if len(given) > 1:
        raise ValueError('Bring one draft: pasted, uploaded or from a Google Doc.')
    title = data.get('title') or ''
    tone = data.get('tone') or ''
    if not isinstance(title, str) or len(title.strip()) > 500 or '\n' in title.strip():
        raise ValueError('Use a blog title of one line, up to 500 characters.')
    if not isinstance(tone, str) or len(tone) > 2000:
        raise ValueError('Describe the tone in up to 2000 characters.')
    tone = tone.strip()
    length = data.get('length', 'style')
    if length not in LENGTHS:
        raise ValueError('Choose a length: the usual length, short or in depth.')
    style = data.get('style') or None
    if style is not None and not isinstance(style, str):
        raise ValueError('Choose a listed kind of post.')
    if style:
        studio.style_check(root, style)  # Refused when retired or unknown; writes nothing.
    existing = None
    if given == ['article']:
        directory, existing = studio.item(root, 'articles', data['article'])
        import blog_runner

        if studio.inside(directory, DESK, 'draft.json').exists():
            raise ValueError('This blog is already on the desk. Open it there.')
        if studio.inside(directory, blog_runner.STATE).exists():
            raise ValueError('This blog has a step-by-step run. Open it there.')
        if not (directory / 'DRAFT.md').is_file():
            raise ValueError('This blog has no draft to bring to the desk.')
        manuscript = (directory / 'DRAFT.md').read_text()
        title = title or existing['title']
    elif given == ['source']:
        manuscript = _source_text(root, data['source'])
    else:
        manuscript = data.get('manuscript') or ''
        if not isinstance(manuscript, str):
            raise ValueError('Paste or upload a draft to start on the desk.')
    if not manuscript.strip():
        raise ValueError('Paste or upload a draft to start on the desk.')
    if len(manuscript) > 1_000_000:
        raise ValueError('Use a draft under one million characters.')
    draft = split(manuscript, title=title.strip())
    if not draft['title']:
        raise ValueError('Give the blog a title.')
    draft['title'] = draft['title'][:500]
    if existing is None:
        args = SimpleNamespace(
            action='create',
            id=None,
            title=draft['title'],
            mode='existing',
            profile=None,
            author=None,
            voice='tone',
            tone=tone,
            audience=None,
            blog_type=None,
            review_folder=None,
            stop='review',
            research='supplied-only',
        )
        ident = studio.new_id(draft['title'])
        record = studio.article_record(root, args, ident)
        directory = studio.inside(root, 'articles', ident)
    else:
        record, ident = existing, existing['id']
    record['voice'] = {'mode': 'tone', 'tone': tone}  # Tone only, whatever the defaults say.
    record['flow'] = 'desk'
    record['title'] = draft['title']
    _attach(root, data, record)
    if style:
        record['style'] = studio.style_pin(root, style)
    now = studio.now()
    draft = {
        'schema': 1,
        'id': ident,
        'revision': 1,
        **draft,
        'style': record.get('style') if style else None,
        'tone': tone,
        'length': length,
        'sources': _citable(record['sources']),
        'gaps': [],
        'created_at': now,
        'updated_at': now,
    }
    if existing is None:
        directory.mkdir()
        studio.save_artifact(directory, 'original', manuscript, record, 'supplied manuscript')
    studio.save_artifact(directory, 'draft', join(draft), record, 'brought to the desk')
    studio.write_json(studio.inside(directory, DESK, 'draft.json'), draft)
    studio.persist(directory, 'articles', record)
    studio.write_json(studio.inside(root, '.active-article.json'), {'id': ident})
    return draft


def _citable(sources):
    """The sources a desk job reads: the blog's own manuscript is the draft, not a source."""
    return [dict(entry) for entry in sources if 'manuscript' not in entry['purposes']]


def open_run(root, ident):
    """A finished step-by-step blog on the desk: its DRAFT.md split into a desk draft with
    the run's kind of post, tone (never its voice) and length. The run's own state and files
    stay as they are, so it remains readable; opening again returns the same desk."""
    import blog_runner

    directory, record, run = blog_runner.load(root, ident)
    target = studio.inside(directory, DESK, 'draft.json')
    if target.is_file() and not target.is_symlink():
        return read(root, ident)
    if (
        not blog_runner.survey(root, ident, listing=True)['complete']
        or not (directory / 'DRAFT.md').is_file()
    ):
        raise ValueError('Finish this blog, then open it on the desk.')
    draft = split((directory / 'DRAFT.md').read_text(), title=record['title'])
    now = studio.now()
    draft = {
        'schema': 1,
        'id': ident,
        'revision': 1,
        **draft,
        'style': record.get('style'),
        'tone': ((record.get('voice') or {}).get('tone') or '').strip(),
        'length': run.get('length', 'style') if run.get('length') in LENGTHS else 'style',
        'sources': _citable(record.get('sources', [])),
        'gaps': [],
        'from_run': True,
        'created_at': now,
        'updated_at': now,
    }
    studio.write_json(target, draft)
    return draft


def read(root, ident):
    _, target = _paths(root, ident)
    if not target.is_file() or target.is_symlink():
        raise ValueError('This blog is not on the desk.')
    return studio.read_json(target)


def _part(draft, part):
    """The section a part names, or None for the title and the opening."""
    if part in PARTS:
        return None
    for section in draft['sections']:
        if section['id'] == part:
            return section
    raise ValueError('Choose a part of this draft.')


def text_of(draft, part):
    section = _part(draft, part)
    return draft[part] if section is None else section['text']


def _set(draft, part, text):
    section = _part(draft, part)
    if section is None:
        draft[part] = text.strip()
    else:
        section['text'] = text.strip()


def _write(root, ident, draft, parts=()):
    """Keep the draft, DRAFT.md and the blog's record in step, one revision on. Each part
    in `parts` records the revision it last changed at, for the stale check."""
    directory, target = _paths(root, ident)
    record = studio.read_json(studio.metadata_path(directory, 'articles'))
    draft['revision'] += 1
    draft['updated_at'] = studio.now()
    changed = draft.setdefault('changed', {})
    for part in parts:
        changed[part] = draft['revision']
    body = join(draft)
    studio.write_json(target, draft)
    studio.atomic(studio.inside(directory, 'DRAFT.md'), body.encode())
    record['artifact_hashes']['draft'] = studio.digest(body.encode())
    record['stage'] = 'draft'
    record['title'] = draft['title']
    studio.persist(directory, 'articles', record)
    return draft


def checked(draft, seen, parts=None):
    """Refuse a form older than the parts it changes.

    With no parts named, the whole draft must be as the form saw it. With parts, a form
    that saw revision `seen` may still change a part nothing else changed after it, so a
    rewrite landing in one section never refuses typing in another."""
    if type(seen) is not int or not 1 <= seen <= draft['revision']:
        raise ValueError('This draft changed since you opened it. Reload to see the latest.')
    if parts is None:
        stale = seen != draft['revision']
    else:
        changed = draft.get('changed') or {}
        stale = any(changed.get(part, 1) > seen for part in parts)
    if stale:
        raise ValueError('This draft changed since you opened it. Reload to see the latest.')


def checked_text(part, text):
    if not isinstance(text, str) or len(text) > LIMIT:
        raise ValueError('Keep one part under 200,000 characters.')
    if part == 'title' and (not text.strip() or '\n' in text.strip() or len(text.strip()) > 500):
        raise ValueError('Keep the title to one line, up to 500 characters.')
    return text


def save(root, ident, seen, part, text, source='save', session=None):
    """Save one part the form last saw at revision `seen`; an outdated form is refused."""
    checked_text(part, text)
    draft = read(root, ident)
    before = text_of(draft, part)
    checked(draft, seen, [part])
    if before == text.strip():
        return draft
    keep(root, ident, part, before, source, session)
    _set(draft, part, text)
    return _write(root, ident, draft, [part])


PART = re.compile(r'[a-f0-9]{8}')
SOURCES = ('save', 'rewrite', 'revise-all', 'selection', 'first-pass', 'finishing', 'restore')


def _versions_path(root, ident, part):
    if not isinstance(part, str) or (part not in PARTS and not PART.fullmatch(part)):
        raise ValueError('Choose a part of this draft.')
    directory, _ = _paths(root, ident)
    target = studio.inside(directory, DESK, 'versions', part + '.jsonl')
    for path in (target.parent.parent, target.parent, target):
        if path.is_symlink() or (path.exists() and not (path.is_dir() or path.is_file())):
            raise ValueError('A desk versions file is not a plain file. Nothing was changed.')
    return target


def _entries(target):
    if not target.is_file():
        return []
    entries = []
    for line in target.read_text(encoding='utf-8').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # A torn line never hides the others.
        if isinstance(entry, dict) and isinstance(entry.get('text'), str):
            entries.append(entry)
    return entries


def keep(root, ident, part, text, source, session=None):
    """Keep a part's text before it changes, newest last, at most KEEP per part.

    Saves from one editing session (the page's session token) keep only the text before
    the first of them; every rewrite, revision, selection edit and restore keeps one."""
    if source not in SOURCES:
        raise ValueError('Choose a listed kind of change.')
    target = _versions_path(root, ident, part)
    entries = _entries(target)
    if (
        source == 'save'
        and session
        and entries
        and entries[-1].get('source') == 'save'
        and entries[-1].get('session') == session
    ):
        return
    entry = {'at': studio.now(), 'source': source, 'text': text, 'words': len(text.split())}
    if source == 'save' and session:
        entry['session'] = session
    lines = [json.dumps(item, ensure_ascii=False) for item in (entries + [entry])[-KEEP:]]
    studio.atomic(target, ('\n'.join(lines) + '\n').encode())


def versions(root, ident, part):
    """The kept versions of one part, newest first."""
    return list(reversed(_entries(_versions_path(root, ident, part))))


def counts(root, ident):
    """How many versions each part keeps, for parts that keep any."""
    directory, _ = _paths(root, ident)
    folder = studio.inside(directory, DESK, 'versions')
    if not folder.is_dir() or folder.is_symlink():
        return {}
    found = {}
    for path in sorted(folder.glob('*.jsonl')):
        part = path.stem
        if (part in PARTS or PART.fullmatch(part)) and path.is_file() and not path.is_symlink():
            found[part] = len(_entries(path))
    return {part: count for part, count in found.items() if count}


def restore(root, ident, seen, part, index):
    """Bring back a kept version; the text it replaces is kept as a version too."""
    found = versions(root, ident, part)
    if type(index) is not int or not 0 <= index < len(found):
        raise ValueError('Choose a saved version.')
    return save(root, ident, seen, part, found[index]['text'], source='restore')


# The page's desk routes (POST /api/desk-<action>), under management's studio lock.
ROUTES = {
    'create': CREATE | {'operation', 'first_pass'},
    'save': {'id', 'seen', 'part', 'text', 'session'},
    'restore': {'id', 'seen', 'part', 'index'},
    'note': {'id', 'seen', 'part', 'note'},
    'revise': {'id', 'seen', 'note'},
    'selection': {'id', 'seen', 'part', 'text', 'action', 'instruction'},
    'first-pass': {'id', 'seen', 'choice'},
    'stop': {'id', 'job'},
    'open': {'id'},
}
SESSION = re.compile(r'[a-f0-9]{16,64}')


def _create(root, data):
    """Create once per page operation: the same request again returns the same blog."""
    import desk_jobs

    data = dict(data)
    operation = data.pop('operation', '')
    if not isinstance(operation, str) or not re.fullmatch('[a-f0-9]{32}', operation):
        raise ValueError('A new blog needs its page operation ID. Reload and retry.')
    choice = data.pop('first_pass', 'leave')
    if choice not in desk_jobs.FIRST_PASSES:
        raise ValueError('Choose tighten, reshape or leave it as it is.')
    if choice == 'reshape' and not data.get('style'):
        raise ValueError('Choose a kind of post to reshape the draft to.')
    path = studio.inside(root, '.blog-runs', 'desk-creations', operation + '.json')
    fingerprint = studio.digest(json.dumps([data, choice], sort_keys=True).encode())
    if path.exists():
        prior = studio.read_json(path)
        if prior['fingerprint'] != fingerprint:
            raise ValueError('This creation request changed. Open a new form.')
        return desk_jobs.view(root, prior['id'])
    made = create(root, data)
    studio.write_json(path, {'id': made['id'], 'fingerprint': fingerprint})
    problem = None
    try:
        desk_jobs.first_pass(root, made['id'], 1, choice)
    except ValueError as error:
        problem = str(error)  # The blog is on the desk either way; the page says why.
    return {**desk_jobs.view(root, made['id']), 'first_pass_problem': problem}


def dispatch(root, action, data):
    import desk_jobs
    from team_workspace import guard

    if action not in ROUTES:
        raise ValueError('Unknown desk action.')
    if not isinstance(data, dict) or set(data) - ROUTES[action]:
        raise ValueError('This request has fields the desk does not take.')
    if action == 'create':
        return _create(root, data)
    ident = data.get('id')
    if not isinstance(ident, str):
        raise ValueError('Choose a blog on the desk.')
    guard(root, ident)
    if action == 'open':
        open_run(root, ident)
        return desk_jobs.view(root, ident)
    read(root, ident)
    seen = data.get('seen')
    if action == 'save':
        session = data.get('session')
        if session is not None and (not isinstance(session, str) or not SESSION.fullmatch(session)):
            raise ValueError('Reload the desk to start a new editing session.')
        save(root, ident, seen, data.get('part'), data.get('text'), session=session)
    elif action == 'restore':
        restore(root, ident, seen, data.get('part'), data.get('index'))
    elif action == 'note':
        desk_jobs.section(root, ident, seen, data.get('part'), data.get('note', ''))
    elif action == 'revise':
        desk_jobs.revise_all(root, ident, seen, data.get('note', ''))
    elif action == 'selection':
        desk_jobs.selection(
            root,
            ident,
            seen,
            data.get('part'),
            data.get('text'),
            data.get('action'),
            data.get('instruction', ''),
        )
    elif action == 'first-pass':
        desk_jobs.first_pass(root, ident, seen, data.get('choice'))
    elif action == 'stop':
        import blog_runner
        import tool_jobs

        if not any(job['id'] == data.get('job') for job in desk_jobs.jobs(root, ident)):
            raise ValueError('Choose a job on this blog.')
        tool_jobs.control(root, data['job'], 'cancel', blog_runner.engine(root))
    return desk_jobs.view(root, ident)
