"""The writing desk: a blog's draft as title, opening and sections, kept with versions.

DRAFT.md is rewritten on every save so Copy, Download, Google Docs, the team library and the
pre-publish check read the same text as before. Images held as data are kept beside the text
(desk_images): a part holds only their short references, desk/images.json holds their data,
and DRAFT.md ends with them.
"""

from collections import OrderedDict
import json
import re
import secrets
from types import SimpleNamespace

import desk_images
import studio
from studio_core.drafting import parts
from studio_core.drafting import record as desk_record
from studio_core.drafting import versions as desk_versions
from studio_core.drafting.store import Store

DESK = 'desk'
KEEP = desk_versions.KEEP  # versions kept per part
PARTS = parts.MARKDOWN.fixed  # ('title', 'opening'), plus each section id
LIMIT = parts.LIMIT  # characters in one part, not counting image data (desk_images)
ON_DESK = 'This blog is on the desk. Edit it there.'
TITLE_IMAGE = 'Keep images out of the title. Put the image in the opening or a section.'
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
# The draft's parts and their Markdown reading are the shared desk's (studio_core.drafting).
FENCE = parts.FENCE
TITLE = parts.TITLE
SECTION = parts.SECTION
ANY_HEADING = parts.ANY_HEADING
ITEM = parts.ITEM
SECTIONS = parts.SECTIONS  # sections in one outline or draft
TOO_MANY = parts.TOO_MANY
BRIEF = parts.BRIEF  # characters in one section's brief
_id = parts.new_id
_tidy = parts.tidy
_free = parts.free
_divide = parts.divide
level = parts.level
limit = parts.limit
heading_in = parts.heading_in
has_heading = parts.has_heading
heading_problem = parts.heading_problem
outline_from = parts.outline_from
_title_line = parts.title_line


def split(markdown, title=''):
    """Title, opening and sections of a Markdown draft (studio_core.drafting.parts.split).
    Images held as data leave the text first, for `images`; their references stay where
    they sit."""
    return parts.split(markdown, title, take=desk_images.take)


def join(draft, images=True, data=None):
    """The Markdown the parts make, as DRAFT.md keeps it: then the definitions of the images
    the text refers to, at the end, from `data` (desk/images.json) or as just taken from
    text. Without `images`, the text alone, as the page shows it."""
    return parts.join(draft, desk_images.definitions(draft, data) if images else [])


def _vet(part, text):
    if part == 'title' and desk_images.holds(text):
        raise ValueError(TITLE_IMAGE)


def _taken(draft, part, text, previous):
    """A part's new text with image data pasted into it moved out, under labels of its own."""
    had = draft.get('images') or {}
    text, images = desk_images.take(text, had, rename=True, previous=previous)
    return text, (draft if images == had else {**draft, 'images': images})


def _fitted(draft, before):
    """The draft within the image limits, against the images the record had."""
    return desk_images.fitted(draft, before=before.get('images') or {})


def _landed(draft, before, text):
    """A returned text as it lands: each token for image data kept as text (in code, say)
    put back as that data, and refused when one was lost or changed (desk_images.restored);
    any image data in it moved to the draft's images under labels of its own; and the image
    references `before` had kept: one left out goes back where it was, one changed or made
    up is taken out (desk_images.kept)."""
    text = desk_images.restored(before, text)
    own = set()
    text, draft['images'] = desk_images.take(
        text, draft.get('images'), rename=True, previous=before, touched=own
    )
    return desk_images.kept(before, text, draft['images'], own)


def _shown(text):
    """A kept version as the page shows it: a version kept before images moved out of the
    text shows their references, not their data."""
    return desk_images.take(text)[0].strip() if desk_images.holds(text) else text


# Blog Studio's codec: the shared Markdown one, keeping images beside the text. Each hook
# looks Blog's function up when called, so a patch on this module reaches it.
CODEC = parts.MARKDOWN.replace(
    split=lambda markdown, title='': split(markdown, title),
    join=lambda draft, *rest, **named: join(draft, *rest, **named),
    vet=lambda part, text: _vet(part, text),
    taken=lambda draft, part, text, previous: _taken(draft, part, text, previous),
    fitted=lambda draft, before: _fitted(draft, before),
    landed=lambda draft, before, text: _landed(draft, before, text),
    shown=lambda text: _shown(text),
)


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


class BlogStore(Store):
    """Blog Studio's desk store: articles/<id>/desk, under the studio lock, written by
    `_write`. Each member looks Blog's function up when called, so patches reach it."""

    product = 'Blog Studio'
    word = 'blog'

    def __init__(self, root):
        self.root = root

    def held(self):
        return studio.lock_held()

    def folder(self, ident):
        return _paths(self.root, ident)[1].parent

    def path(self, ident, *names):
        directory, _ = _paths(self.root, ident)
        return studio.inside(directory, DESK, *names)

    def local(self, ident, *names):
        return studio.inside(
            self.root, '.blog-runs', 'desk-proposals', studio.identifier(ident), *names
        )

    def read(self, ident):
        return read(self.root, ident)

    def write(self, ident, draft, parts):
        return _write(self.root, ident, draft, parts)

    def read_json(self, path):
        return studio.read_json(path)

    def write_json(self, path, value):
        return studio.write_json(path, value)

    def atomic(self, path, data):
        return studio.atomic(path, data)

    def now(self):
        return studio.now()


def _drafting(root):
    """The shared desk record over this blog workspace."""
    return desk_record.Desk(BlogStore(root), CODEC, SOURCES)


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
        raise ValueError('This request has fields the page does not take.')
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
    draft = split(manuscript, title=title.strip())
    if desk_images.holds(draft['title']):
        raise ValueError(TITLE_IMAGE)
    if len(draft['sections']) > SECTIONS:
        raise ValueError(TOO_MANY)
    if len(join(draft, images=False)) > LIMIT:
        # As runs take, and as much as one part may hold or one job may return. Image data
        # is not counted: it is kept beside the text, within its own limits.
        raise ValueError('Use a draft up to 200,000 characters.')
    draft = desk_images.fitted(draft)
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
    # A saved blog keeps the voice it was pinned to in its record; the desk writes with the
    # tone of its own draft whatever the record says.
    if existing is None or (existing.get('voice') or {}).get('mode') != 'profile':
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
    _keep_images(directory, draft)
    studio.persist(directory, 'articles', record)
    studio.write_json(studio.inside(root, '.active-article.json'), {'id': ident})
    return desk_images.stored(draft)


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
        if len(desk_images.take(notes)[0]) > LIMIT:
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
        'notes': desk_images.without(notes),  # A start's notes keep no image data.
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


UNDER_WAY = ('queued', 'working')  # a run's step that will write when it ends


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
    if blog_runner.engine(root).describe(ident, listing=True)['status'] in UNDER_WAY:
        # Its step would write DRAFT.md when it ends, behind the desk's back.
        raise ValueError(
            'A step of this blog is under way. Let it finish, or stop it, then open it on the desk.'
        )
    found = blog_runner.survey(root, ident, listing=True)
    # A finished blog edited since in the manuscript editor reads as stale at its draft; its
    # DRAFT.md is the person's latest text, so it opens too.
    if not (found['complete'] or found['finished']) or not (directory / 'DRAFT.md').is_file():
        raise ValueError('Finish this blog, then open it on the desk.')
    draft = desk_images.fitted(split((directory / 'DRAFT.md').read_text(), title=record['title']))
    if len(draft['sections']) > SECTIONS:
        raise ValueError(TOO_MANY)
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
    _keep_images(directory, draft)
    return desk_images.stored(draft)


IMAGES = 'images.json'  # {label: data URI} for a desk draft's images (desk_images)
REMEMBERED = 8  # blogs whose image data this process keeps in mind, the most recent


class _Recent(OrderedDict):
    """A small memory of the most recently used blogs, never more than REMEMBERED."""

    def __getitem__(self, name):
        value = super().__getitem__(name)
        self.move_to_end(name)
        return value

    def get(self, name, default=None):
        return self[name] if name in self else default

    def __setitem__(self, name, value):
        super().__setitem__(name, value)
        self.move_to_end(name)
        while len(self) > REMEMBERED:
            self.popitem(last=False)


# desk/images.json as last parsed, by path: (mtime, size, data), so a save or a view that
# needs only its labels never parses it again unchanged.
_PARSED = _Recent()
# A record cleaned as it was read but not written (no lock, or another computer drives the
# blog), by path: (draft.json's digest, the clean draft with its image data), so a poll
# does not clean it again and the page can still be served its images.
_CLEANED = _Recent()


def _data_at(path):
    """desk/images.json by label: each value that is image data that can be written back
    as is. Anything else is left out, and the image shows as missing."""
    if not path.is_file() or path.is_symlink():
        return {}
    stat = path.stat()
    known = _PARSED.get(str(path))
    if known and known[:2] == (stat.st_mtime_ns, stat.st_size):
        return dict(known[2])
    try:
        found = studio.read_json(path)
    except (ValueError, OSError):
        found = {}
    found = found if isinstance(found, dict) else {}
    data = {label: uri for label, uri in found.items() if desk_images.usable(uri)}
    _PARSED[str(path)] = (stat.st_mtime_ns, stat.st_size, data)
    return dict(data)


def _data(root, ident):
    """The data of a desk blog's images, by label. Read only to write DRAFT.md or to serve
    the page its images once, never for a view."""
    directory, _ = _paths(root, ident)
    return _data_at(studio.inside(directory, DESK, IMAGES))


def _held(root, ident):
    """The labels desk/images.json holds data for, to see which images are missing. Parsed
    only when the file changed since it was last read or written here."""
    directory, _ = _paths(root, ident)
    return set(_data_at(studio.inside(directory, DESK, IMAGES)))


def _keep_images(directory, draft, before=None):
    """Keep desk/images.json in step with the draft's images, when that changes, then
    desk/draft.json without any image data. Returns the data, by label. `before` is the
    file as already read, if it was."""
    path = studio.inside(directory, DESK, IMAGES)
    before = _data_at(path) if before is None else before
    data = desk_images.data_of(draft, before)
    if data != before and (data or path.exists()):
        studio.write_json(path, data)
        stat = path.stat()
        _PARSED[str(path)] = (stat.st_mtime_ns, stat.st_size, dict(data))
    studio.write_json(studio.inside(directory, DESK, 'draft.json'), desk_images.stored(draft))
    _CLEANED.pop(str(studio.inside(directory, DESK, 'draft.json')), None)
    return data


def read(root, ident):
    """The desk draft, with its images listed but not their data. A record kept before
    images moved out of the text, or whose text names an image whose data is kept nowhere,
    is cleaned as it is read (`_images_out`); a clean one is only read."""
    _, target = _paths(root, ident)
    if not target.is_file() or target.is_symlink():
        raise ValueError('This blog is not on the desk.')
    raw = target.read_bytes()
    draft = json.loads(raw)
    if draft.get('images'):
        draft['images'] = desk_images.entries(draft['images'])
    sought = set(draft.get('sought') or [])
    held = _held(root, ident) if draft.get('images') else set()
    lost = [
        label for label in desk_images.missing(draft, held) if desk_images.key(label) not in sought
    ]
    if desk_images.inside(draft) or desk_images.unstored(draft) or lost:
        cleaned = _CLEANED.get(str(target))
        if cleaned and cleaned[0] == studio.digest(raw) and not _writable(root, ident):
            return desk_images.stored(cleaned[1])  # Cleaned here before, and not written.
        draft = _images_out(root, ident, draft, lost, studio.digest(raw))
    if not draft['sections'] and has_heading(draft.get('opening') or '', 6):
        draft = _sectioned(root, ident, draft)
    return draft


def _sectioned(root, ident, draft):
    """A record kept before the desk read headings below ##, divided as it is first read:
    a Google Doc's export with ### headings came to the desk as one opening. The opening's
    headings now start sections, as `split` reads them; no word changes.

    Only under the studio lock, on the computer that drives the blog, and while no desk job
    of the blog is under way (its result was asked for against the opening). The record is
    written once, one revision on, with the opening and the outline marked changed: a page
    left open on the opening is refused as outdated rather than writing the whole draft back
    into it, and a form on any other part still saves. The opening keeps its versions, and
    DRAFT.md reads the same. In a team workspace the change is committed on its own and
    shared with the next decision (a view never pushes). Otherwise the record is read as it
    is, and divided where it is driven."""
    import desk_jobs

    if not _writable(root, ident):
        return draft
    if any(desk_jobs.busy(job) for job in desk_jobs.jobs(root, ident)):
        return draft
    opening, sections = _divide(draft['opening'].split('\n'))
    if not sections or len(sections) > SECTIONS:
        return draft
    revision = draft['revision'] + 1
    changed = {**(draft.get('changed') or {}), 'opening': revision, 'outline': revision}
    draft = {
        **draft,
        'opening': opening,
        'sections': sections,
        'revision': revision,
        'changed': changed,
        'updated_at': studio.now(),
    }
    directory, target = _paths(root, ident)
    studio.write_json(target, desk_images.stored(draft))
    _CLEANED.pop(str(target), None)
    record = studio.read_json(studio.metadata_path(directory, 'articles'))
    current, body = studio.inside(directory, 'DRAFT.md'), join(draft, data=_data(root, ident))
    recorded = record.get('artifact_hashes', {}).get('draft')
    if current.is_file() and current.read_bytes() != body.encode():
        if studio.digest(current.read_bytes()) == recorded:  # Never text changed elsewhere.
            studio.atomic(current, body.encode())
            record['artifact_hashes']['draft'] = studio.digest(body.encode())
            studio.persist(directory, 'articles', record)
    from team_workspace import keep_desk, space

    if space(root):
        keep_desk(root, ident, 'Read the sections of ' + ident + ' from its headings')
    return draft


def _writable(root, ident):
    """Whether this read may write the blog: under the lock, on the computer that drives it."""
    if not studio.lock_held():
        return False
    from team_workspace import guard

    try:
        guard(root, ident)
    except ValueError:
        return False
    return True


def _images_out(root, ident, draft, lost=(), raw=None):
    """A record kept before images moved out of the text, cleaned as it is first read: the
    image data in its text moves to desk/images.json, and an image its text names whose data
    is kept nowhere is looked for where it was last written (`_recovered`). No word changes.

    Under the studio lock, on the computer that drives the blog, the clean record is written
    once with no new revision and no part marked changed, so no open form is refused for it
    alone, and DRAFT.md ends with the images again; a label looked for and not found is
    noted in `sought`, so it is looked for once. In a team workspace the change is recorded
    on its own. Otherwise the clean draft is kept in this process only, for the next read and
    for serving the page its images. Image limits let go of images no part refers to, but
    never of data kept before them."""
    draft = desk_images.moved_out(draft)
    if lost:
        draft = _recovered(root, ident, draft, lost)
        sought = {
            desk_images.key(label)
            for label in desk_images.missing(draft, _held(root, ident) if lost else None)
        }
        draft['sought'] = sorted(set(draft.get('sought') or []) | sought)
    draft = desk_images.with_alts(draft)
    draft = desk_images.fitted(draft, before=draft.get('images'))
    _, target = _paths(root, ident)
    if not _writable(root, ident):
        # No lock, or another computer drives the blog and cleans it there.
        _CLEANED[str(target)] = (raw, draft)
        return desk_images.stored(draft)
    from team_workspace import keep_desk, space

    directory, _ = _paths(root, ident)
    data = _keep_images(directory, draft)
    record = studio.read_json(studio.metadata_path(directory, 'articles'))
    current, body = studio.inside(directory, 'DRAFT.md'), join(draft, data=data).encode()
    recorded = record.get('artifact_hashes', {}).get('draft')
    if current.is_file() and current.read_bytes() != body:
        if studio.digest(current.read_bytes()) == recorded:  # Never text changed elsewhere.
            studio.atomic(current, body)
            record['artifact_hashes']['draft'] = studio.digest(body)
            studio.persist(directory, 'articles', record)
    if space(root):
        keep_desk(root, ident, 'Keep the images of ' + ident + ' apart from its desk text')
    return desk_images.stored(draft)


def cleaned_data(root, ident):
    """Image data this process holds for a record it cleaned but could not write."""
    _, target = _paths(root, ident)
    found = _CLEANED.get(str(target))
    if not found or not target.is_file() or found[0] != studio.digest(target.read_bytes()):
        return {}
    return {
        label: entry['uri']
        for label, entry in found[1].get('images', {}).items()
        if entry.get('uri')
    }


def _recovered(root, ident, draft, labels):
    """The draft with the data of each image its text names but keeps nowhere, found where it
    was last written: the newest kept version of any part that defines it, then ORIGINAL.md,
    then the Google Doc the blog started from. Each version is read once."""
    directory, _ = _paths(root, ident)
    images = dict(draft.get('images') or {})
    folder = studio.inside(directory, DESK, 'versions')
    entries = []
    for path in folder.glob('*.jsonl') if folder.is_dir() and not folder.is_symlink() else []:
        if path.stem in PARTS or PART.fullmatch(path.stem):
            try:
                entries += _kept(root, ident, path.stem)
            except ValueError:
                continue
    entries.sort(key=lambda entry: str(entry.get('at') or ''), reverse=True)

    def elsewhere():
        original = studio.inside(directory, 'ORIGINAL.md')
        if original.is_file() and not original.is_symlink():
            yield original.read_text()
        try:
            from google_workflow import snapshot_path

            record = studio.read_json(studio.metadata_path(directory, 'articles'))
            base = (record.get('google') or {}).get('baselines', {}).get('draft') or {}
            if base.get('transfer'):
                snapshot = snapshot_path(directory, base['transfer'], 'document')
                if snapshot.is_file():
                    yield snapshot.read_text()
        except (ValueError, OSError, KeyError, TypeError):
            return

    texts = (text for text in (*(entry['text'] for entry in entries), *elsewhere()))
    found = desk_images.found_in(texts, labels)
    names = {desk_images.key(label): label for label in images}
    for label in labels:
        entry = found.get(desk_images.key(label))
        if entry:
            name = names.get(desk_images.key(label), label)
            images[name] = {**entry, 'alt': (images.get(name) or {}).get('alt', '')}
    return {**draft, 'images': images}


def _part(draft, part):
    """The section a part names, or None for the title and the opening."""
    return CODEC.section(draft, part)


def text_of(draft, part):
    return CODEC.text_of(draft, part)


def _set(draft, part, text):
    CODEC.set_text(draft, part, text)


def _leveled(section, depth):
    """A section as it is kept at a draft's heading level: ## sections record none."""
    kept = {key: value for key, value in section.items() if key not in ('level', 'text')}
    return {**kept, **({'level': depth} if depth != 2 else {}), 'text': section['text']}


def _write(root, ident, draft, parts=()):
    """Keep the draft, DRAFT.md and the blog's record in step, one revision on. Each part
    in `parts` records the revision it last changed at, for the stale check."""
    _require_lock()
    directory, target = _paths(root, ident)
    # Every write keeps the image limits: an image new since the record on disk is refused
    # for its size, or for taking the total over once images no part uses are let go.
    had = (studio.read_json(target).get('images') or {}) if target.is_file() else {}
    # Image data any writer put into a part's text moves out first, so the limits see it.
    images = desk_images.entries(draft.get('images'))
    opening, images = desk_images.take(draft.get('opening') or '', images, rename=True)
    sections = []
    for section in draft['sections']:
        text, images = desk_images.take(section['text'], images, rename=True)
        sections.append({**section, 'text': text.strip()})
    # Every section is written at the draft's level: a section added since keeps it too.
    depth = level({'sections': sections})
    sections = [_leveled(section, depth) for section in sections]
    draft = {**draft, 'opening': opening.strip(), 'sections': sections, 'images': images}
    draft = desk_images.fitted(draft, before=had)
    record = studio.read_json(studio.metadata_path(directory, 'articles'))
    desk_record.advance(draft, parts, studio.now())
    before = _data(root, ident)
    body = join(draft, data=before)
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
    _keep_images(directory, draft, before)
    studio.atomic(current, body.encode())
    record['artifact_hashes']['draft'] = studio.digest(body.encode())
    record['stage'] = 'draft'
    record['title'] = draft['title']
    studio.persist(directory, 'articles', record)
    return desk_images.stored(draft)


def checked(draft, seen, parts=None):
    """Refuse a form older than the parts it changes (studio_core.drafting.record).

    With no parts named, the whole draft must be as the form saw it. With parts, a form
    that saw revision `seen` may still change a part nothing else changed after it, so a
    rewrite landing in one section never refuses typing in another."""
    desk_record.checked(draft, seen, parts, CODEC.thing)


def checked_text(part, text, deepest=2):
    """Refuse text a part cannot hold. `deepest` is the draft's `limit`: a heading at that
    level or above would start a section."""
    return desk_record.checked_text(part, text, CODEC, deepest)


def save(root, ident, seen, part, text, source='save', session=None):
    """Save one part the form last saw at revision `seen`; an outdated form is refused. An
    image pasted as data, or a version kept with image data, leaves the text for `images`."""
    return _drafting(root).save(ident, seen, part, text, source, session)


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


def _same_heading(one, other):
    def plain(text):
        return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower()).split())

    return plain(one) == plain(other)


def reimport(root, ident, markdown, source, record=None):
    """Bring a whole draft written outside the desk onto it: a chat save or a restore from
    history (`chat`), or Google's accepted text (`google`). Each part it changes keeps its
    text first as a version from that source; sections go with the desk section of the same
    heading, then with the one in their place, so ids and History follow the text; a section
    the new text leaves out can be brought back from the Outline tab. DRAFT.md and the
    record are written by `_write`, so a desk page open meanwhile is refused for what changed
    rather than writing over it. `record`, the caller's copy, is brought up to date."""
    _require_lock()
    if source not in ('chat', 'google'):
        raise ValueError('Choose a listed kind of change.')
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError('Cannot save an empty draft.')
    import desk_jobs

    if any(
        job['kind'] in WHOLE_DRAFT and desk_jobs.busy(job) for job in desk_jobs.jobs(root, ident)
    ):
        raise ValueError(
            'The desk is writing this draft now. Wait for it, or stop it on the desk, then '
            'save again.'
        )
    draft = read(root, ident)
    found = split(markdown, title=draft['title'])
    if len(join(found, images=False)) > LIMIT:
        raise ValueError('Use a draft up to 200,000 characters.')
    if len(found['sections']) > SECTIONS:
        raise ValueError(TOO_MANY)
    # The images it defines join the ones kept; text that only names them keeps them.
    images = {**(draft.get('images') or {}), **found['images']}
    changed = ['images'] if images != (draft.get('images') or {}) else []
    title = ' '.join(found['title'].split()) or draft['title']
    if title != draft['title']:
        checked_text('title', title)
        keep(root, ident, 'title', draft['title'], source)
        draft['title'] = title
        changed.append('title')
    if found['opening'] != draft['opening']:
        checked_text('opening', found['opening'], limit(found))
        if draft['opening']:
            keep(root, ident, 'opening', draft['opening'], source)
        draft['opening'] = found['opening']
        changed.append('opening')
    current, taken = draft['sections'], {section['id'] for section in draft['sections']}
    planned, used = [None] * len(found['sections']), set()
    for at, written in enumerate(found['sections']):
        for section in current:
            if section['id'] not in used and _same_heading(section['heading'], written['heading']):
                planned[at] = section
                used.add(section['id'])
                break
    for at in range(len(found['sections'])):
        if planned[at] is None and at < len(current) and current[at]['id'] not in used:
            planned[at] = current[at]
            used.add(current[at]['id'])
    merged = []
    for at, written in enumerate(found['sections']):
        section = planned[at]
        heading = ' '.join(written['heading'].split())[:200]
        checked_text('opening', written['text'], limit(found))
        # Each section takes the level, and any marks kept as written, of the new text.
        depth = {key: written[key] for key in ('level', 'mark') if written.get(key)}
        if section is None:
            part = _id(taken)
            changed.append(part)
            merged.append(
                {'id': part, 'heading': heading, 'brief': '', **depth, 'text': written['text']}
            )
            continue
        section = {key: value for key, value in section.items() if key not in ('level', 'mark')}
        if section['text'] != written['text']:
            if section['text']:
                keep(root, ident, section['id'], section['text'], source)
            changed.append(section['id'])
        elif section['heading'] != heading or any(
            planned[at].get(key) != written.get(key) for key in ('level', 'mark')
        ):
            changed.append(section['id'])
        merged.append({**section, 'heading': heading, **depth, 'text': written['text']})
    gone = [section for section in current if section['id'] not in used]
    if gone or [s['id'] for s in merged if s['id'] in taken] != [
        s['id'] for s in current if s['id'] in used
    ]:
        changed.append('outline')
    if any(section['id'] not in taken for section in merged):
        changed.append('outline')
    if not changed:
        return draft
    now = studio.now()
    _keep_removed(
        root,
        ident,
        [{**section, 'index': current.index(section), 'at': now} for section in gone],
    )
    draft['sections'] = merged
    draft = desk_images.fitted({**draft, 'images': images}, before=draft.get('images'))
    draft = _write(root, ident, draft, sorted(set(changed)))
    if record is not None:
        directory, _ = _paths(root, ident)
        fresh = studio.read_json(studio.metadata_path(directory, 'articles'))
        for key in ('artifact_hashes', 'artifact_events', 'stage', 'title'):
            if key in fresh:
                record[key] = fresh[key]
    return draft


REMOVED = desk_record.REMOVED  # removed sections kept to bring back


def _removed_path(root, ident):
    return _drafting(root)._removed_path(ident)


def removed(root, ident):
    """Sections taken out on the Outline tab, newest first, each with its text and brief."""
    return _drafting(root).removed(ident)


def _keep_removed(root, ident, sections):
    _drafting(root).keep_removed(ident, sections)


def unremove(root, ident, seen, index):
    """Bring a removed section back where it was, with its id, so its History comes too."""
    return _drafting(root).unremove(ident, seen, index)


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


PART = parts.MARKDOWN.part
SOURCES = desk_versions.SOURCES + (
    'chat',  # A whole draft saved in chat, or restored from its history (`reimport`).
    'google',  # Google's accepted text brought back (`reimport`).
)


def _versions(root):
    return _drafting(root).versions


def _versions_path(root, ident, part):
    return _versions(root).path(ident, part)


_entries = desk_versions.entries


def keep(root, ident, part, text, source, session=None, extra=None):
    """Keep a part's text before it changes, newest last, at most KEEP per part.

    Saves from one editing session (the page's session token) keep only the text before
    the first of them; every rewrite, revision, selection edit and restore keeps one."""
    _versions(root).keep(ident, part, text, source, session, extra)


def versions(root, ident, part):
    """The kept versions of one part, newest first, each as the page shows it: a version kept
    before images moved out of the text shows their references, not their data."""
    return _versions(root).versions(ident, part)


def _kept(root, ident, part):
    """The kept versions of one part, newest first, as they were kept."""
    return _versions(root).kept(ident, part)


def counts(root, ident):
    """How many versions each part keeps, for parts that keep any."""
    return _versions(root).counts(ident)


def restore(root, ident, seen, part, index):
    """Bring back a kept version; the text it replaces is kept as a version too. A version
    from before a first pass divided the draft undoes the division as a whole: the sections
    that pass added go to the Outline tab's removed list, to bring back if wanted."""
    found = _kept(root, ident, part)
    if type(index) is not int or not 0 <= index < len(found):
        raise ValueError('Choose a saved version.')
    entry = found[index]
    added = entry.get('divided') if part == 'opening' else None
    if part == 'opening' and not added:
        current = read(root, ident)
        text = desk_images.take(entry['text'])[0]
        if has_heading(text, limit(current)):
            return _restore_divided(root, ident, seen, current, entry)
    if not added:
        return save(root, ident, seen, part, entry['text'], source='restore')
    import desk_jobs

    draft = read(root, ident)
    had = draft.get('images') or {}
    text, images = desk_images.take(entry['text'], had, rename=True)  # Its references are its own.
    remaining = [section for section in draft['sections'] if section['id'] not in added]
    checked_text(part, text, limit({**draft, 'sections': remaining}))
    order = [section['id'] for section in draft['sections']]
    taken = [section for section in draft['sections'] if section['id'] in added]
    checked(draft, seen, [part, 'outline'] + [section['id'] for section in taken])
    if any(
        job['kind'] in WHOLE_DRAFT and desk_jobs.busy(job) for job in desk_jobs.jobs(root, ident)
    ):
        raise ValueError('The draft is being written. Wait for it, or stop it, then restore.')
    opening = draft['opening']
    draft = {
        **draft,
        'images': images,
        'sections': [section for section in draft['sections'] if section['id'] not in added],
    }
    _set(draft, part, text)
    draft = desk_images.fitted(draft, before=had)
    keep(root, ident, part, opening, 'restore')
    now = studio.now()
    _keep_removed(
        root,
        ident,
        [{**section, 'index': order.index(section['id']), 'at': now} for section in taken],
    )
    return _write(root, ident, draft, [part, 'outline'] + [section['id'] for section in taken])


def _restore_divided(root, ident, seen, draft, entry):
    """Bring back an opening kept before its headings started sections, such as the whole
    draft before a first pass on a record the desk later divided: its headings start the
    sections again, as `split` reads them, and the sections there now go to the Outline
    tab's removed list, to bring back if wanted. The opening there now is kept first."""
    import desk_jobs

    had = draft.get('images') or {}
    text, images = desk_images.take(entry['text'], had, rename=True)  # Its references are its own.
    opening, sections = _divide(text.strip('\n').split('\n'))
    if len(sections) > SECTIONS:
        raise ValueError(TOO_MANY)
    checked_text('opening', opening, limit({'sections': sections}))
    current = draft['sections']
    checked(draft, seen, ['opening', 'outline'] + [section['id'] for section in current])
    if any(
        job['kind'] in WHOLE_DRAFT and desk_jobs.busy(job) for job in desk_jobs.jobs(root, ident)
    ):
        raise ValueError('The draft is being written. Wait for it, or stop it, then restore.')
    taken = {section['id'] for section in current}
    for section in sections:
        section['id'] = _id(taken)
    keep(root, ident, 'opening', draft['opening'], 'restore')
    now = studio.now()
    _keep_removed(
        root, ident, [{**section, 'index': at, 'at': now} for at, section in enumerate(current)]
    )
    draft = {**draft, 'opening': opening.strip(), 'sections': sections, 'images': images}
    draft = desk_images.fitted(draft, before=had)
    parts = ['opening', 'outline'] + [s['id'] for s in current] + [s['id'] for s in sections]
    return _write(root, ident, draft, parts)


# The page's desk routes (POST /api/desk-<action>), under management's studio lock.
ROUTES = {
    'create': CREATE | {'operation', 'first_pass', 'humanize', 'angles', 'keep'},
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
    'retry': {'id', 'seconds', 'skip_research'},
    'outline-save': {'id', 'seen', 'sections'},
    'draft': {'id', 'seen'},
    'sources': {'id', 'sources', 'library', 'keep'},
    # Finishing (desk_finish.py): a tool proposes, then the person applies or skips.
    'finish': {'id', 'seen', 'tool', 'level', 'guide'},
    # Review mode's check: Copy edit, then Humanize when it is on (desk_jobs.review).
    'review': {'id', 'seen', 'humanize'},
    'apply': {'id', 'seen', 'job', 'items', 'all'},
    'skip': {'id', 'job', 'items'},
    # Before publishing: a repurpose result as a new blog, and Google suggestions.
    'repurpose': {'id', 'job', 'title', 'content'},
    'google-plan': {'id', 'mode'},
    'google-send': {'id', 'plan', 'confirmed'},
}
SESSION = re.compile(r'[a-f0-9]{16,64}')
# Routes the page's dispatch does not record as a decision on this blog (management.py).
UNSHARED = ('skip', 'google-plan', 'google-send', 'repurpose')


# First passes that are a Finishing tool: they propose, and the draft is left as it is.
FINISH_FIRST = ('copyedit', 'feedback')


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
    # Check spelling and grammar first is Finishing's Copy edit, and feedback first is its
    # feedback, each queued once the blog is made: suggestions and comments only, so the
    # person accepts or rejects each fix (the page's Review mode) and nothing changes before.
    choice = data.pop('first_pass', 'leave')
    if choice not in (*desk_jobs.FIRST_PASSES, *FINISH_FIRST):
        raise ValueError(
            'Choose Check spelling and grammar, feedback, reshape, tighten or leave it as it is.'
        )
    # Check spelling and grammar may also suggest human-sounding wording, at a strength.
    humanize = desk_jobs.humanize_level(data.pop('humanize', None))
    if humanize and choice != 'copyedit':
        raise ValueError('Human-sounding suggestions go with Check spelling and grammar.')
    if data.get('way', 'draft') != 'draft' and choice != 'leave':
        raise ValueError('A first pass is for a draft you bring.')
    if choice == 'reshape' and not data.get('style'):
        raise ValueError('Choose a kind of post to reshape the draft to.')
    path = studio.inside(root, '.blog-runs', 'desk-creations', operation + '.json')
    asked = [data, choice, kept] + ([humanize] if humanize else [])
    fingerprint = studio.digest(json.dumps(asked, sort_keys=True).encode())
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
        if choice == 'copyedit':
            desk_jobs.review(root, made['id'], 1, humanize)
        elif choice in FINISH_FIRST:
            desk_jobs.finish(root, made['id'], 1, choice)
        else:
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
        raise ValueError('This request has fields the page does not take.')
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
        desk_jobs.retry(root, ident, data.get('seconds'), data.get('skip_research', False))
        return desk_jobs.view(root, ident)
    # A result an older process finished lands before anything else changes the draft. Not on
    # requests that record no decision for the team, which would leave what landed unshared.
    if action not in UNSHARED:
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
    elif action in ('google-plan', 'google-send'):
        import desk_finish

        if action == 'google-plan':
            return desk_finish.google_plan(root, ident, data.get('mode', 'auto'))
        return desk_finish.google_send(root, ident, data)
    elif action == 'repurpose':
        import desk_finish

        made = desk_finish.repurpose(
            root, ident, data.get('job'), data.get('title'), data.get('content')
        )
        return {**desk_jobs.view(root, ident), 'made': made}
    elif action == 'finish':
        desk_jobs.finish(root, ident, seen, data.get('tool'), data.get('level'), data.get('guide'))
    elif action == 'review':
        desk_jobs.review(
            root, ident, seen, data['humanize'] if 'humanize' in data else desk_jobs.PINNED
        )
    elif action in ('apply', 'skip'):
        import desk_finish

        if action == 'apply':
            done = desk_finish.apply(
                root, ident, seen, data.get('job'), data.get('items'), data.get('all', False)
            )
        else:
            done = desk_finish.skip(root, ident, data.get('job'), data.get('items'))
        return {**desk_jobs.view(root, ident), 'finished': done}
    return desk_jobs.view(root, ident)
