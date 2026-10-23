"""The writing desk: a blog's draft as title, opening and sections, kept with versions.

DRAFT.md is rewritten on every save so Copy, Download, Google Docs, the team library and the
pre-publish check read the same text as before.
"""

import json
import re
import secrets
import textwrap
from types import SimpleNamespace

import studio

DESK = 'desk'
KEEP = 20  # versions kept per part
PARTS = ('title', 'opening')  # plus each section id
LIMIT = 200_000  # characters in one part
ON_DESK = 'This blog is on the desk. Edit it there.'
LENGTHS = ('style', 'short', 'deep')  # as blog_runner.LENGTHS: usual, short, in depth
CREATE = frozenset(
    {
        'title',
        'manuscript',
        'source',
        'article',
        'style',
        'tone',
        'length',
        'sources',
        'library',
        # A start (Phase 2): the way of working, and what the person brings for it.
        'way',
        'point',
        'audience',
        'outline',
        'outline_source',
        'research_from',
    }
)
# What the person brings: a draft (edit), a topic (author), an outline written from or an
# outline shaped with them first (co-author).
WAYS = ('draft', 'topic', 'outline', 'shape')
FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
TITLE = re.compile(r'# (?!#)(.*\S)\s*')
HEADING = re.compile(r'## (?!#)(.*\S)\s*')
ANY_HEADING = re.compile(r'(#{1,6})\s+(.*?\S)\s*#*\s*')
ITEM = re.compile(r'(?:[-*+]|\d{1,3}[.)])\s+(\S.*)')
SECTIONS = 60  # sections in one outline
BRIEF = 4000  # characters in one section's brief


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


def has_heading(text):
    """Whether a part's text holds a `## ` heading outside code, which would start a new
    section the next time DRAFT.md is read."""
    fence = None
    for line in text.replace('\r\n', '\n').split('\n'):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
            continue
        if fence is None and HEADING.fullmatch(line):
            return True
    return False


def outline_from(text):
    """The outline a person pasted, as a title, an opening brief and sections with briefs,
    or None when it is notes without structure.

    Headings outside code (at the shallowest level used) start sections; without headings,
    top-level list items do, and the lines indented under each are its brief. Text before
    the first section is the opening brief. Fewer than two sections is not an outline."""
    lines = (text or '').replace('\r\n', '\n').strip('\n').split('\n')
    title = ''
    found = TITLE.fullmatch(lines[0]) if lines and lines[0] else None
    if found:
        title, lines = found.group(1), lines[1:]
    headings, items, fence = [], [], None
    for at, line in enumerate(lines):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
            continue
        if fence is not None:
            continue
        heading = ANY_HEADING.fullmatch(line)
        if heading:
            headings.append((at, len(heading.group(1)), heading.group(2)))
        elif ITEM.fullmatch(line) and not line[:1].isspace():
            items.append((at, ITEM.fullmatch(line).group(1)))
    if headings:
        level = min(depth for _, depth, _ in headings)
        cuts = [(at, words) for at, depth, words in headings if depth == level]
    else:
        cuts = items
    if not 2 <= len(cuts) <= SECTIONS:
        return None
    sections, taken = [], set()
    for number, (at, words) in enumerate(cuts):
        end = cuts[number + 1][0] if number + 1 < len(cuts) else len(lines)
        body = '\n'.join(lines[at + 1 : end])
        words = words.strip()
        if not headings:
            body = textwrap.dedent(body)
            lead, colon, rest = words.partition(': ')
            if colon and len(lead) <= 100:
                words, body = lead, rest + ('\n' + body if body.strip() else '')
        heading = ' '.join(words.rstrip(':').split())[:200] or 'Section ' + str(number + 1)
        sections.append(
            {
                'id': _id(taken),
                'heading': heading,
                'brief': _tidy(body.split('\n'))[:BRIEF],
                'text': '',
            }
        )
    return {
        'title': title.strip()[:500],
        'opening_brief': _tidy(lines[: cuts[0][0]])[:BRIEF],
        'sections': sections,
    }


def _title_line(text):
    """The `# ` title on the first line of a pasted outline or notes, or ''."""
    first = (text or '').replace('\r\n', '\n').strip('\n').split('\n')[0]
    found = TITLE.fullmatch(first)
    return found.group(1).strip()[:500] if found else ''


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
# page's dispatch and views do (management.py) and the job worker does when it settles a
# result (tool_jobs.once); none of them takes it again, and every writer checks it is held.


def on_desk(directory):
    """Whether a blog's folder holds a desk draft: then only the desk writes its DRAFT.md."""
    return (directory / DESK / 'draft.json').is_file()


def refuse_on_desk(directory):
    if on_desk(directory):
        raise ValueError(ON_DESK)


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('Desk writes run under the studio lock.')


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
    _require_lock()
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
    way = data.get('way', 'draft')
    if way not in WAYS:
        raise ValueError('Choose a topic, an outline or notes, or a draft.')
    if way != 'draft':
        if given:
            raise ValueError('A start from a topic or an outline brings no draft. Choose A draft.')
        return _start(root, data, way, title.strip(), tone, length, style)
    if data.get('research_from'):
        raise ValueError('Research runs before new writing. A draft you bring is edited as it is.')
    if data.get('outline') or data.get('outline_source') or data.get('point'):
        raise ValueError(
            'A draft you bring takes no outline or point. Choose a topic or an outline.'
        )
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
    if len(manuscript) > LIMIT:
        # As runs take, and as much as one part may hold or one job may return.
        raise ValueError('Use a draft up to 200,000 characters.')
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


START = 'start.json'
# About how long each step of a start takes, for "in about N minutes"; a draft by length.
MINUTES = {'research': 10, 'outline': 1, 'draft': {'short': 2, 'style': 3, 'deep': 5}}


def estimate(steps, length):
    return sum(
        MINUTES['draft'].get(length, 3) if step == 'draft' else MINUTES[step] for step in steps
    )


def _research_choice(root, chosen, record):
    """Where research before the writing may look: your sites and the public web, both off
    by default, with your documents counted when readable ones are given. None: no research."""
    import blog_runner
    import synthesis_research
    from studio_core import research_contract, research_sites

    if chosen is None:
        return None
    if (
        not isinstance(chosen, dict)
        or set(chosen) - {'sites', 'web'}
        or type(chosen.get('web', False)) is not bool
        or not isinstance(chosen.get('sites', []), list)
    ):
        raise ValueError('Choose whether to search your sites and the web.')
    sites = research_sites.sites(chosen.get('sites') or [])
    if not sites and not chosen.get('web'):
        return None
    if not chosen.get('web') and research_contract.snapshot() is None:
        raise ValueError(blog_runner.NEEDS_HARNESS_RESEARCH)
    given = False
    for entry in record['sources']:
        _, source = studio.item(root, 'sources', entry['source_id'])
        given = given or synthesis_research.offered({**source, 'purposes': entry['purposes']})
    return research_sites.effective(
        {'documents': True, 'sites': sites, 'web': chosen.get('web', False)}, given
    )


def _start(root, data, way, title, tone, length, style):
    """A new desk blog whose draft is written for the person: from a topic and its point,
    from their outline, or from an outline shaped with them first. The draft record holds
    what is known so far; desk/start.json the steps that write the rest, with no stops."""
    from studio_core import research_contract

    point, audience = data.get('point') or '', data.get('audience') or ''
    if not isinstance(point, str) or len(point) > 2000:
        raise ValueError('Say the point to make in up to 2,000 characters.')
    if not isinstance(audience, str) or len(audience) > 500:
        raise ValueError('Say who it is for in up to 500 characters.')
    point, audience = point.strip(), audience.strip()
    if way == 'topic' and not point:
        raise ValueError('Say the point to make, or pick an angle.')
    notes = ''
    if way in ('outline', 'shape'):
        if data.get('outline') and data.get('outline_source'):
            raise ValueError('Paste or upload your outline, not both.')
        if data.get('outline_source'):
            notes = _source_text(root, data['outline_source'])
        else:
            notes = data.get('outline') or ''
        if not isinstance(notes, str) or not notes.strip():
            raise ValueError('Paste or upload your outline or notes.')
        if len(notes) > LIMIT:
            raise ValueError('Use an outline up to 200,000 characters.')
    parsed = outline_from(notes) if way == 'outline' else None
    title = (title or _title_line(notes))[:500]
    if not title:
        raise ValueError('Give the blog a title.')
    args = SimpleNamespace(
        action='create',
        id=None,
        title=title,
        mode='first-draft',
        profile=None,
        author=None,
        voice='tone',
        tone=tone,
        audience=audience or None,
        blog_type=None,
        review_folder=None,
        stop='review',
        research='supplied-only',
    )
    ident = studio.new_id(title)
    record = studio.article_record(root, args, ident)
    record['voice'] = {'mode': 'tone', 'tone': tone}  # Tone only, whatever the defaults say.
    record['flow'] = 'desk'
    _attach(root, data, record)
    found = _research_choice(root, data.get('research_from'), record)
    record['research_policy'] = 'web-allowed' if found else 'supplied-only'
    record['research_from'] = found
    if style:
        record['style'] = studio.style_pin(root, style)
    steps = (['research'] if found else []) + {
        'topic': ['outline', 'draft'],
        'outline': ['draft'] if parsed else ['outline', 'draft'],
        'shape': ['outline'],
    }[way]
    now = studio.now()
    draft = {
        'schema': 1,
        'id': ident,
        'revision': 1,
        'title': title,
        'opening': '',
        'sections': parsed['sections'] if parsed else [],
        'brief': {'point': point, 'audience': audience},
        'opening_brief': parsed['opening_brief'] if parsed else '',
        'style': record.get('style') if style else None,
        'tone': tone,
        'length': length,
        'sources': _citable(record['sources']),
        'gaps': [],
        'created_at': now,
        'updated_at': now,
    }
    start = {
        'schema': 1,
        'way': way,
        'steps': steps,
        'step': steps[0],
        'job': None,
        'started_at': now,
        'ended_at': None,
        'open': 'outline' if way == 'shape' else 'draft',
        'minutes': estimate(steps, length),
        'notes': notes,
        'research_from': found,
        # Research keeps the Harness Research version it starts with, as a run does.
        'contract': research_contract.snapshot() if found else None,
    }
    directory = studio.inside(root, 'articles', ident)
    directory.mkdir()
    studio.write_json(studio.inside(directory, DESK, 'draft.json'), draft)
    studio.write_json(studio.inside(directory, DESK, START), start)
    studio.persist(directory, 'articles', record)
    studio.write_json(studio.inside(root, '.active-article.json'), {'id': ident})
    return draft


def _start_path(root, ident):
    directory, _ = _paths(root, ident)
    return studio.inside(directory, DESK, START)


def read_start(root, ident):
    """The start that writes this blog's draft, or None for a blog brought as a draft."""
    target = _start_path(root, ident)
    if not target.is_file() or target.is_symlink():
        return None
    return studio.read_json(target)


def write_start(root, ident, start):
    _require_lock()
    studio.write_json(_start_path(root, ident), start)


def _citable(sources):
    """The sources a desk job reads: the blog's own manuscript is the draft, not a source."""
    return [dict(entry) for entry in sources if 'manuscript' not in entry['purposes']]


def open_run(root, ident):
    """A finished step-by-step blog on the desk: its DRAFT.md split into a desk draft with
    the run's kind of post, tone (never its voice) and length. The run's own state and files
    stay as they are, so it remains readable; opening again returns the same desk."""
    import blog_runner

    _require_lock()
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
    _require_lock()
    directory, target = _paths(root, ident)
    record = studio.read_json(studio.metadata_path(directory, 'articles'))
    draft['revision'] += 1
    draft['updated_at'] = studio.now()
    changed = draft.setdefault('changed', {})
    for part in parts:
        changed[part] = draft['revision']
    body = join(draft)
    current = studio.inside(directory, 'DRAFT.md')
    if current.is_file() and studio.digest(current.read_bytes()) != record['artifact_hashes'].get(
        'draft'
    ):
        # Something other than the desk changed DRAFT.md: keep that text before replacing it.
        stamp = studio.now().replace(':', '').replace('-', '').replace('+', '')[:20]
        kept = 'draft-' + stamp + '-' + secrets.token_hex(4) + '.md'
        studio.atomic(studio.inside(directory, 'history', kept), current.read_bytes())
        record.setdefault('artifact_events', []).append(
            {
                'kind': 'draft',
                'before': kept,
                'after_sha256': studio.digest(body.encode()),
                'label': 'Changed outside the desk; kept before a desk save',
                'at': studio.now(),
            }
        )
        record['artifact_events'] = record['artifact_events'][-100:]
    studio.write_json(target, draft)
    studio.atomic(current, body.encode())
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
    if part != 'title' and has_heading(text):
        raise ValueError(
            'A ## heading would start a new section. Use ### for a heading inside this part.'
        )
    return text


def save(root, ident, seen, part, text, source='save', session=None):
    """Save one part the form last saw at revision `seen`; an outdated form is refused."""
    checked_text(part, text)
    draft = read(root, ident)
    before = text_of(draft, part)
    if before == text.strip():
        return draft  # The same text again, as from a retried save: nothing to refuse.
    checked(draft, seen, [part])
    keep(root, ident, part, before, source, session)
    _set(draft, part, text)
    return _write(root, ident, draft, [part])


# Kinds that write every section or plan the outline: the outline waits while they work.
WHOLE_DRAFT = ('desk-outline', 'desk-draft', 'desk-research', 'desk-first-pass', 'desk-revise-all')


def outline_save(root, ident, seen, rows):
    """Rename, reorder, add and remove sections and edit their briefs, from the Outline tab.
    Ids are kept; a section without one is new. A form older than a section it changes, or
    than the outline's order, is refused."""
    import desk_jobs

    draft = read(root, ident)
    if not isinstance(rows, list) or len(rows) > SECTIONS:
        raise ValueError('Keep the outline to 60 sections.')
    current = {section['id']: section for section in draft['sections']}
    taken, named, out, touched, added = set(current), set(), [], [], False
    for row in rows:
        if not isinstance(row, dict) or set(row) - {'id', 'heading', 'brief'}:
            raise ValueError('Each section needs its heading and brief.')
        heading, brief = row.get('heading'), row.get('brief', '')
        if not isinstance(heading, str) or not heading.strip() or '\n' in heading.strip():
            raise ValueError('Give each section a heading of one line, up to 200 characters.')
        heading = heading.strip()
        if len(heading) > 200:
            raise ValueError('Give each section a heading of one line, up to 200 characters.')
        if heading.startswith('#'):
            raise ValueError('Leave out the # marks; the desk adds them.')
        if not isinstance(brief, str) or len(brief) > BRIEF:
            raise ValueError('Keep each brief to 4,000 characters.')
        brief = brief.strip()
        part = row.get('id')
        if part is None:
            part, added = _id(taken), True
            out.append({'id': part, 'heading': heading, 'brief': brief, 'text': ''})
            continue
        if part not in current or part in named:
            raise ValueError(
                'This outline names a section this draft does not have. Reload to see the latest.'
            )
        named.add(part)
        section = current[part]
        if section['heading'] != heading or section.get('brief', '') != brief:
            touched.append(part)
        out.append({**section, 'heading': heading, 'brief': brief})
    removed = [part for part in current if part not in named]
    reordered = [s['id'] for s in out if s['id'] in current] != [
        s['id'] for s in draft['sections'] if s['id'] in named
    ]
    structure = ['outline'] if added or removed or reordered else []
    if not touched and not structure:
        return draft
    checked(draft, seen, touched + removed + structure)
    if any(
        job['kind'] in WHOLE_DRAFT and desk_jobs.busy(job) for job in desk_jobs.jobs(root, ident)
    ):
        raise ValueError(
            'The draft is being written from this outline. Wait for it, or stop it, then change '
            'the outline.'
        )
    draft['sections'] = out
    now = studio.now()
    order = list(current)
    _keep_removed(
        root, ident, [{**current[part], 'index': order.index(part), 'at': now} for part in removed]
    )
    return _write(
        root, ident, draft, touched + [s['id'] for s in out if s['id'] not in current] + structure
    )


REMOVED = 20  # removed sections kept to bring back


def _removed_path(root, ident):
    directory, _ = _paths(root, ident)
    return studio.inside(directory, DESK, 'removed.json')


def removed(root, ident):
    """Sections taken out on the Outline tab, newest first, each with its text and brief."""
    target = _removed_path(root, ident)
    if not target.is_file() or target.is_symlink():
        return []
    try:
        found = studio.read_json(target)
    except (ValueError, OSError):
        return []
    return [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []


def _keep_removed(root, ident, sections):
    if sections:
        studio.write_json(_removed_path(root, ident), (sections + removed(root, ident))[:REMOVED])


def unremove(root, ident, seen, index):
    """Bring a removed section back where it was, with its id, so its History comes too."""
    found = removed(root, ident)
    if type(index) is not int or not 0 <= index < len(found):
        raise ValueError('Choose a removed section.')
    draft = read(root, ident)
    checked(draft, seen, ['outline'])
    if len(draft['sections']) >= SECTIONS:
        raise ValueError('Keep the outline to 60 sections.')
    item = found[index]
    taken = {section['id'] for section in draft['sections']}
    kept = str(item.get('id') or '')
    part = kept if PART.fullmatch(kept) and kept not in taken else _id(taken)
    section = {
        'id': part,
        'heading': ' '.join(str(item.get('heading') or 'Section').split())[:200],
        'brief': str(item.get('brief') or '')[:BRIEF],
        'text': str(item.get('text') or ''),
    }
    at = item.get('index') if type(item.get('index')) is int else len(draft['sections'])
    draft['sections'].insert(max(0, min(at, len(draft['sections']))), section)
    studio.write_json(_removed_path(root, ident), found[:index] + found[index + 1 :])
    return _write(root, ident, draft, [part, 'outline'])


def _kept_ids(keep, sources):
    if not isinstance(keep, list) or any(not isinstance(item, str) for item in keep):
        raise ValueError('Keep only sources you are adding, by their IDs.')
    if set(keep) - set(sources if isinstance(sources, list) else []):
        raise ValueError('Keep only sources you are adding, by their IDs.')
    return sorted(set(keep))


def keep_in_library(root, ident, kept):
    """Move the sources the person ticked into the team library, now that the blog that
    reads them is made, and move this blog's own pins with them. Returns a readable problem,
    or None; the blog stands either way."""
    if not kept:
        return None
    import management

    try:
        directory, record = studio.item(root, 'articles', ident)
        for source in kept:
            management.source_keep(root, {'id': source, 'keep': True}, blog=ident)
            for entry in record['sources']:
                if entry['source_id'] == source:
                    entry['purposes'] = [
                        'reference' if purpose == 'material' else purpose
                        for purpose in entry['purposes']
                    ]
        record['material'] = [
            entry['source_id'] for entry in record['sources'] if 'material' in entry['purposes']
        ]
        studio.persist(directory, 'articles', record)
        _, target = _paths(root, ident)
        draft = read(root, ident)
        draft['sources'] = _citable(record['sources'])
        studio.write_json(target, draft)
    except (ValueError, OSError) as error:
        return 'Not kept in the team library: ' + str(error)[:500]
    return None


def add_sources(root, ident, data):
    """Pin more sources (uploaded files, Google Docs, library items with a role) on a desk
    blog at any time; later rewrites and checks read them."""
    chosen, library = data.get('sources') or [], data.get('library') or []
    if not chosen and not library:
        raise ValueError('Choose a source to add.')
    kept = _kept_ids(data.get('keep', []), chosen)
    directory, record = studio.item(root, 'articles', ident)
    draft = read(root, ident)
    _attach(root, {'sources': chosen, 'library': library}, record)
    if len(record['sources']) > 50:
        raise ValueError('A blog reads at most 50 sources.')
    studio.persist(directory, 'articles', record)
    draft['sources'] = _citable(record['sources'])
    written = _write(root, ident, draft, ['sources'])
    problem = keep_in_library(root, ident, kept)
    if problem:
        raise ValueError(problem + ' The source was added to this blog only.')
    return written


PART = re.compile(r'[a-f0-9]{8}')
SOURCES = (
    'save',
    'rewrite',
    'revise-all',
    'selection',
    'first-pass',
    'finishing',
    'restore',
    'draft',
)


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
    _require_lock()
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
    'create': CREATE | {'operation', 'first_pass', 'angles', 'keep'},
    'save': {'id', 'seen', 'part', 'text', 'session'},
    'restore': {'id', 'seen', 'part', 'index'},
    'note': {'id', 'seen', 'part', 'note'},
    'revise': {'id', 'seen', 'note'},
    'selection': {'id', 'seen', 'part', 'text', 'action', 'instruction', 'start'},
    'first-pass': {'id', 'seen', 'choice'},
    'stop': {'id', 'job'},
    'open': {'id'},
    'angles': {
        'operation',
        'title',
        'point',
        'audience',
        'style',
        'tone',
        'sources',
        'library',
        'replaces',
    },
    'unremove': {'id', 'seen', 'index'},
    'retry': {'id'},
    'outline-save': {'id', 'seen', 'sections'},
    'draft': {'id', 'seen'},
    'sources': {'id', 'sources', 'library', 'keep'},
    # Finishing (desk_finish.py): a tool proposes, then the person applies or skips.
    'finish': {'id', 'seen', 'tool', 'level'},
    'apply': {'id', 'seen', 'job', 'items'},
    'skip': {'id', 'job', 'items'},
}
SESSION = re.compile(r'[a-f0-9]{16,64}')


def _create(root, data):
    """Create once per page operation: the same request again returns the same blog."""
    import desk_jobs

    data = dict(data)
    operation = data.pop('operation', '')
    if not isinstance(operation, str) or not re.fullmatch('[a-f0-9]{32}', operation):
        raise ValueError('A new blog needs its page operation ID. Reload and retry.')
    picked = data.pop('angles', None)  # The angles this start came from, let go once made.
    if picked is not None:
        desk_jobs._angles_path(root, picked)  # A bad ID is refused before anything is made.
    kept = _kept_ids(data.pop('keep', []), data.get('sources') or [])
    choice = data.pop('first_pass', 'leave')
    if choice not in desk_jobs.FIRST_PASSES:
        raise ValueError('Choose tighten, reshape or leave it as it is.')
    if data.get('way', 'draft') != 'draft' and choice != 'leave':
        raise ValueError('A first pass is for a draft you bring.')
    if choice == 'reshape' and not data.get('style'):
        raise ValueError('Choose a kind of post to reshape the draft to.')
    path = studio.inside(root, '.blog-runs', 'desk-creations', operation + '.json')
    fingerprint = studio.digest(json.dumps([data, choice, kept], sort_keys=True).encode())
    if path.exists():
        prior = studio.read_json(path)
        if prior['fingerprint'] != fingerprint:
            raise ValueError('This creation request changed. Open a new form.')
        return desk_jobs.view(root, prior['id'])
    made = create(root, data)
    studio.write_json(path, {'id': made['id'], 'fingerprint': fingerprint})
    keep_problem = keep_in_library(root, made['id'], kept)
    try:
        desk_jobs.prune_angles(root)
        if picked:
            desk_jobs.forget_angles(root, picked)
    except Exception:  # noqa: BLE001 - letting angles go never fails a blog just made.
        pass
    problem = None
    if read_start(root, made['id']):
        desk_jobs.begin(root, made['id'])  # A problem is kept on the start, with Retry.
        return {
            **desk_jobs.view(root, made['id']),
            'first_pass_problem': None,
            'keep_problem': keep_problem,
        }
    try:
        desk_jobs.first_pass(root, made['id'], 1, choice)
    except ValueError as error:
        problem = str(error)  # The blog is on the desk either way; the page says why.
    return {
        **desk_jobs.view(root, made['id']),
        'first_pass_problem': problem,
        'keep_problem': keep_problem,
    }


def dispatch(root, action, data):
    import desk_jobs
    from team_workspace import guard

    if action not in ROUTES:
        raise ValueError('Unknown desk action.')
    if not isinstance(data, dict) or set(data) - ROUTES[action]:
        raise ValueError('This request has fields the desk does not take.')
    if action == 'create':
        return _create(root, data)
    if action == 'angles':
        return desk_jobs.angles(root, data)  # Before a blog exists: nothing to guard.
    ident = data.get('id')
    if not isinstance(ident, str):
        raise ValueError('Choose a blog on the desk.')
    guard(root, ident)
    if action == 'open':
        open_run(root, ident)
        return desk_jobs.view(root, ident)
    read(root, ident)
    if action == 'stop':
        desk_jobs.stop(root, ident, data.get('job'))
        return desk_jobs.view(root, ident)
    if action == 'retry':
        desk_jobs.settle(root, ident)
        desk_jobs.retry(root, ident)
        return desk_jobs.view(root, ident)
    # A result an older process finished lands before anything else changes the draft.
    desk_jobs.settle(root, ident)
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
            data.get('start'),
        )
    elif action == 'first-pass':
        desk_jobs.first_pass(root, ident, seen, data.get('choice'))
    elif action == 'outline-save':
        outline_save(root, ident, seen, data.get('sections'))
    elif action == 'unremove':
        unremove(root, ident, seen, data.get('index'))
    elif action == 'draft':
        desk_jobs.draft_job(root, ident, seen)
    elif action == 'sources':
        add_sources(root, ident, data)
    elif action == 'finish':
        desk_jobs.finish(root, ident, seen, data.get('tool'), data.get('level'))
    elif action in ('apply', 'skip'):
        import desk_finish

        if action == 'apply':
            done = desk_finish.apply(root, ident, seen, data.get('job'), data.get('items'))
        else:
            done = desk_finish.skip(root, ident, data.get('job'), data.get('items'))
        return {**desk_jobs.view(root, ident), 'finished': done}
    return desk_jobs.view(root, ident)
