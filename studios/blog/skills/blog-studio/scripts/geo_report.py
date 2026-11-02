"""A GEO report for a published post: recommendations only, nothing brought to the desk.

The person gives a link, checks the read-only preview (published_post), and presses one
button: one job reads the post and returns what already works, the changes ranked by how
much they help, the additions (an FAQ, key takeaways, a definition-style opening, a
comparison table where the post compares things, alt text for images that lack it), the
questions the post answers and the claims that need a source. Every part is read by the
desk's own readers (desk_finish), so the report keeps their rules: placement only after
whole paragraphs, a flag on any number or link the post does not have, quotations never
invented. The post's own text is its evidence; nothing is invented, no score or grade is
given and no ranking is promised.

A report is kept on this computer (.blog-runs/geo-reports), listed in Blog Studio's list as
a GEO report rather than a draft, and reopened from there. From it the person may:
- download it as Markdown, or as one self-contained HTML file that prints cleanly to PDF;
- Edit this post on the desk: a desk copy with the recommendations waiting in Finishing;
- make a new Google Doc of the post with each change as a suggestion and its reason as a
  comment (through the desk copy, which is the blog the Doc is linked to);
- Run again: the page is read again and a new report made, saying what changed since.
The live page is never changed, and no fetch, job or Google call starts without a press.
"""

import difflib
import html

import re
import secrets

import desk
import desk_finish
import desk_images
import studio
import tool_jobs

KIND = 'geo-report'
FOLDER = ('.blog-runs', 'geo-reports')
CHANGES_MOST = 12
WORKS_MOST = 5
SOURCES_MOST = 10
FAQ_WANTED = 5
NOT_READY = 'This report is not ready yet. Wait for it, then try again.'
NO_REPORT = 'This GEO report is not kept on this computer.'
DESK_CHANGED = (
    'This post’s desk copy has changed since the report, so its Google Doc would not match '
    'the report. Send the desk copy’s changes from the desk instead: Before publishing, '
    'Send to Google Doc as suggestions.'
)
REPORT = """This is a GEO report on a post that is already published. The post's own text is its
evidence: there are no other sources, research or brief. Recommend; do not rewrite the post.
Return one JSON object in content, with no score, grade or ranking promise, shaped:
{"works": [...], "suggestions": [...], "summary": "...", "faq": {...}, "takeaways": {...},
"tables": [...], "alts": [...], "opener": {...}, "queries": [...], "sources_needed": [...]}

- works: up to five sentences, each something the post already does well for readers and
  for AI assistants that read it (a direct answer, a clear definition, consistent names,
  passages that stand on their own), each true of the post's own text.
- suggestions: the changes, at most twelve, ranked so the one that helps most comes first.
  Each is {"part", "before", "after", "why", "help"}: part is "title", "opening" or the id
  of a section in sections; before occurs exactly once in that part, copied exactly; after
  replaces it; why is a short reason of a few words, such as "states the answer first" or
  "names the product the same way throughout"; help is one sentence saying how the change
  helps a reader or an assistant. Keep every qualifier, number, link and quotation the
  passage has. Empty suggestions means no changes.
- summary: one or two sentences of advice that needs no edit, or "": a vague heading named
  with a clearer one goes here, since a suggestion cannot change a heading, as does a
  detail the author must supply (a date, a current name, what a chart or video shows).
- faq: {"questions": [{"question", "answer"}], "closing_cta", "summary"} as below.
- takeaways: {"takeaways": ["..."], "summary"} as below.
- tables: [{"part", "after_text", "table", "why"}] as below, or [] where the post compares
  nothing.
- alts: [{"image", "alt", "why"}] for each image in images_without_alt, as below.
- opener: {"before", "after", "why"} as below.
- queries: the questions people might ask an AI assistant that this post answers, as below.
- sources_needed: at most ten claims the post makes that would be stronger with a cited
  source: {"part", "claim", "kind"}. claim is the sentence copied exactly from that part;
  kind says what kind of source would support it, such as "a benchmark the team ran",
  "the product's documentation" or "a dated source with the baseline for the 40%". Never
  name, link or invent a source, statistic, date or quote.
"""


def _folder(root):
    folder = studio.inside(root, *FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _path(root, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError(NO_REPORT)
    return studio.inside(root, *FOLDER, ident + '.json')


def read(root, ident):
    path = _path(root, ident)
    if not path.is_file() or path.is_symlink():
        raise ValueError(NO_REPORT)
    return studio.read_json(path)


def _write(root, record):
    _folder(root)
    studio.write_json(_path(root, record['id']), record)


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('GEO reports are written under the studio lock.')


# The job: one request with every part of the report, read by the desk's own readers.
def _draft(found):
    """The post as the desk reads it (title, opening, sections and images), with no record."""
    import published_post

    draft = desk.split(found['markdown'], title=found.get('title') or '')
    # The title as a reader sees it: a page's words are escaped in its Markdown.
    title = published_post.plain(draft['title'])
    draft['title'] = (title or found.get('title') or 'Untitled post')[:500]
    for section in draft['sections']:
        section.setdefault('brief', '')
    return draft


def _payload(draft):
    payload = desk_finish._payload(draft, {})
    payload['questions_wanted'] = FAQ_WANTED
    wanted = desk_finish._alt_wanted(draft)
    if wanted:
        payload['images_without_alt'] = wanted
    for key, pattern in (
        ('faq_section', desk_finish.FAQ_FOUND),
        ('takeaways_section', desk_finish.TAKEAWAYS_FOUND),
    ):
        found = desk_finish._found_section(draft, pattern)
        if found:
            payload[key] = {name: found[name] for name in ('id', 'heading', 'text')}
    return payload


def guidance():
    import manuscript_editor

    parts = [
        manuscript_editor.CHECKS['geo'],
        desk_finish._reference('modules', 'blog-geo-review.md'),
        desk_finish.GEO_RULES,
        REPORT,
        'The FAQ: ' + desk_finish.FAQ,
        'Key takeaways: ' + desk_finish.TAKEAWAYS,
        'Comparison tables: ' + desk_finish.TABLE,
        'Alt text: ' + desk_finish.ALT,
        'The definition-style opening: ' + desk_finish.OPENER,
        'Questions: ' + desk_finish.QUERIES,
    ]
    return '\n\n'.join(parts)


def start(root, operation, found, previous=None):
    """Make a report from a read the person checked, and queue its one job. The same
    operation again returns the same report."""
    _require_lock()
    if not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9]{32}', operation):
        raise ValueError('A GEO report needs its page operation ID. Reload and retry.')
    path = _path(root, operation)
    if path.is_file():
        return view(root, operation)
    draft = _draft(found)
    if not (draft['opening'].strip() or any(s['text'].strip() for s in draft['sections'])):
        raise ValueError('This post has no text to review.')
    payload = _payload(draft)
    import published_post

    record = {
        'schema': 1,
        'id': operation,
        'kind': KIND,
        **published_post.origin(found),
        'title': draft['title'],
        'markdown': found['markdown'],
        'draft': draft,
        'access': found.get('access'),
        'created_at': studio.now(),
        'job': operation,
        'status': 'working',
        'error': '',
        'result': None,
    }
    if previous:
        earlier = read(root, previous)
        record['previous'] = previous
        record['changed'] = changes_since(earlier, record)
    tool_jobs.create(
        root,
        operation,
        'geo-report',
        payload,
        guidance(),
        studio.digest(found['markdown'].encode()),
        {'report': operation, 'url': record['url']},
    )
    _write(root, record)
    _wake(root)
    return view(root, operation)


def _wake(root):
    try:
        import blog_runner

        blog_runner.engine(root).wake.set()
    except Exception:  # noqa: BLE001 - the worker finds the job on its next pass anyway.
        pass


def _fake_job(draft, payload):
    return {'payload': payload, 'metadata': {'desk': {'count': FAQ_WANTED}}}


def _reader(read_one, *args):
    """One part of the result through its desk reader; a part that cannot be read is
    counted as dropped rather than failing the whole report."""
    try:
        return read_one(*args)
    except (ValueError, TypeError, AttributeError, KeyError):
        return [], 1, {}


def _texts(value, most, limit):
    if not isinstance(value, list):
        return []
    kept = []
    for entry in value[: most * 3]:
        text = desk_finish._line(entry, limit) if isinstance(entry, str) else ''
        if text and text.casefold() not in {k.casefold() for k in kept}:
            kept.append(text)
    return kept[:most]


def read_result(draft, payload, found):
    """The job's result as the report keeps it, each part read by the desk's own reader."""
    if not isinstance(found, dict):
        raise ValueError(desk_finish.UNREADABLE)
    job = _fake_job(draft, payload)
    rows = found.get('suggestions') if isinstance(found.get('suggestions'), list) else []
    geo = {'suggestions': rows[: CHANGES_MOST * 2]}
    changes, dropped, extra = _reader(desk_finish._read_geo, draft, geo)
    helps = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('before'), str):
            helps.setdefault((row.get('part'), row['before'].strip()), row.get('help'))
    for item in changes:
        item['help'] = desk_finish._text(helps.get((item['part'], item['before'].strip())), 500)
    dropped += max(0, len(changes) - CHANGES_MOST)
    changes = changes[:CHANGES_MOST]
    additions = {}
    faq, more, _ = _reader(desk_finish._read_faq, draft, found.get('faq'), job)
    takeaways, also, _ = _reader(desk_finish._read_takeaways, draft, found.get('takeaways'), job)
    tables, other, _ = _reader(
        desk_finish._read_table, draft, {'tables': found.get('tables') or []}, job
    )
    alts, alt_dropped, _ = (
        _reader(desk_finish._read_alt, draft, {'alts': found.get('alts') or []}, job)
        if payload.get('images_without_alt')
        else ([], 0, {})
    )
    opener, opener_dropped, _ = (
        _reader(desk_finish._read_opener, draft, found.get('opener'), job)
        if isinstance(found.get('opener'), dict)
        else ([], 0, {})
    )
    dropped += more + also + other + alt_dropped + opener_dropped
    additions = {
        'faq': faq[0] if faq else None,
        'takeaways': takeaways[0] if takeaways else None,
        'tables': tables,
        'alts': alts,
        'opener': opener[0] if opener else None,
    }
    _, _, asked = _reader(desk_finish._read_queries, draft, {'queries': found.get('queries')}, job)
    sources = []
    for row in found.get('sources_needed') or []:
        if not isinstance(row, dict) or len(sources) >= SOURCES_MOST:
            continue
        part = row.get('part')
        claim = (
            desk_finish._located(draft, part, row.get('claim'))
            if part in desk_finish._prose_parts(draft)
            else None
        )
        kind = desk_finish._line(row.get('kind'), 200)
        if claim is None or not kind:
            dropped += 1
            continue
        sources.append({'part': part, 'claim': claim, 'kind': kind})
    return {
        'works': _texts(found.get('works'), WORKS_MOST, 400),
        'changes': changes,
        'summary': desk_finish._text(found.get('summary'), 2000),
        'additions': additions,
        'queries': (asked or {}).get('queries', []),
        'sources_needed': sources,
        'dropped': dropped,
        # As the job returned it, for a desk copy's Finishing to read again (desk_copy).
        'raw': found,
    }


def ended(root, job):
    """The report's job ended: its result read into the report, or why it did not finish."""
    meta = job.get('metadata') or {}
    try:
        record = read(root, meta.get('report'))
    except (ValueError, OSError):
        return None
    if job.get('status') == 'ready':
        try:
            found = desk_finish.shared.read_result(
                (job.get('result') or {}).get('content'), desk_finish.UNREADABLE
            )
            record['result'] = read_result(record['draft'], job['payload'], found)
            record.update(status='ready', error='', finished_at=studio.now())
        except ValueError as error:
            record.update(status='failed', error=str(error)[:1000])
    else:
        record.update(
            status='failed', error=job.get('error') or 'The report did not finish. Run it again.'
        )
    _write(root, record)
    return None


def listing(root):
    """The reports kept on this computer, newest first, each marked a GEO report."""
    folder = studio.inside(root, *FOLDER)
    rows = []
    for path in folder.glob('*.json') if folder.is_dir() else []:
        try:
            record = studio.read_json(path)
            rows.append(
                {
                    'id': record['id'],
                    'kind': KIND,
                    'title': record['title'],
                    'url': record.get('url') or '',
                    'read_at': record.get('read_at'),
                    'created_at': record.get('created_at'),
                    'status': _status(root, record),
                    'previous': record.get('previous'),
                    'desk': record.get('desk'),
                    'post': _post_key(record),
                }
            )
        except (ValueError, OSError, KeyError, TypeError):
            continue
    rows.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    newest = {}
    for row in rows:
        newest.setdefault(row['post'], row['id'])
    for row in rows:
        row['newer'] = newest[row['post']] if newest[row['post']] != row['id'] else None
        del row['post']
    return {'items': rows}


def _post_key(record):
    """Which post a report is of: its link, or its team collection entry; reports of the same
    post are one line of reports, the newest current."""
    item = record.get('collection_item') or {}
    if record.get('url'):
        return record['url']
    return 'item:' + str(item.get('id')) if item else record['id']


def _status(root, record):
    """'working' while its job is queued or under way, then 'ready' or 'failed'."""
    if record.get('status') != 'working':
        return record.get('status')
    try:
        job = tool_jobs.read(root, record['job'])
    except (ValueError, OSError):
        return 'failed'
    return 'working' if job.get('status') in ('queued', 'working') else 'failed'


def _settled(root, record):
    """A report whose job ended while nothing was there to read it (an interrupted worker,
    a result left by an older process) is read now, under the lock the view holds."""
    if record.get('status') != 'working' or not studio.lock_held():
        return record
    try:
        job = tool_jobs.read(root, record['job'])
    except (ValueError, OSError):
        return record
    if job.get('status') in ('ready', 'failed', 'cancelled'):
        ended(root, job)
        return read(root, record['id'])
    return record


# What changed on the page since the last report (Run again).
def _parts(record):
    draft = record['draft']
    rows = [('the title', draft['title']), ('the opening', draft['opening'])]
    rows += [(section['heading'] or 'a section', section['text']) for section in draft['sections']]
    return rows


def changes_since(earlier, later):
    """What changed on the page between two reports of it: the text read, never a score."""
    if earlier['markdown'] == later['markdown']:
        return {'same': True, 'since': earlier.get('read_at')}
    old, new = _parts(earlier), _parts(later)
    old_names = {name: text for name, text in old[2:]}
    new_names = {name: text for name, text in new[2:]}
    changed = [name for (name, a), (_, b) in zip(old[:2], new[:2], strict=True) if a != b]
    changed += [
        name for name in new_names if name in old_names and old_names[name] != new_names[name]
    ]
    taken = 0
    earlier_changes = ((earlier.get('result') or {}).get('changes')) or []
    now = _plain(later['markdown'])
    for item in earlier_changes:
        after, before = _plain(item.get('after')), _plain(item.get('before'))
        if after and after in now and (not before or before not in now or before in after):
            taken += 1
    words = lambda record: len(re.findall(r"[\w’']+", _plain(record['markdown'])))  # noqa: E731
    return {
        'same': False,
        'since': earlier.get('read_at'),
        'added': [name for name in new_names if name not in old_names][:20],
        'removed': [name for name in old_names if name not in new_names][:20],
        'changed': changed[:20],
        'words': [words(earlier), words(later)],
        'taken': taken,
        'of': len(earlier_changes),
    }


# The report as the page and the downloads show it.
LINK = re.compile(r'!?\[((?:\\.|[^\[\]\n\\])*)\]\(([^()\s]*)(?:\s+"[^"\n]*")?\)')
REFERENCE_IMAGE = re.compile(r'!\[([^\[\]\n]*)\]\[[^\[\]\n]*\]')


def _plain(text):
    """Markdown inline text as a reader sees it: a link's words, an image as its name and alt
    text, and no emphasis or code marks."""

    def image_or_link(found):
        if found.group(0).startswith('!'):
            name = found.group(2).rsplit('/', 1)[-1].split('?')[0] or 'image'
            alt = found.group(1).strip()
            return '[Image: ' + name + (' — alt text: ' + alt if alt else ', no alt text') + ']'
        return found.group(1)

    import published_post

    text = LINK.sub(image_or_link, str(text or ''))
    text = REFERENCE_IMAGE.sub(lambda found: '[Image: ' + (found.group(1) or 'image') + ']', text)
    text = re.sub(r'(?<!\\)(\*\*|__|`)', '', text)
    text = re.sub(r'(?<![\w*\\])\*(?=\S)([^*\n]+?)(?<=[^\s\\])\*(?![\w*])', r'\1', text)
    return published_post.plain(text)  # A page's escaped characters, as a reader sees them.


def _segments(before, after):
    """A change as runs of kept, deleted and inserted words, in reading order."""
    a, b = re.findall(r'\s+|\S+', _plain(before)), re.findall(r'\s+|\S+', _plain(after))
    out = []

    def add(kind, words):
        text = ''.join(words)
        if not text:
            return
        if out and out[-1]['t'] == kind:
            out[-1]['v'] += text
        else:
            out.append({'t': kind, 'v': text})

    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == 'equal':
            add('text', a[i1:i2])
        else:
            add('del', a[i1:i2])
            add('ins', b[j1:j2])
    return out


def _numbered(result):
    """Every recommendation with its number, in the order the summary lists them: the
    changes most helpful first, then the definition opening, tables, alt text, the FAQ and
    key takeaways."""
    rows = []
    for item in result.get('changes') or []:
        rows.append(('change', item))
    additions = result.get('additions') or {}
    if additions.get('opener'):
        rows.append(('opener', additions['opener']))
    rows += [('table', item) for item in additions.get('tables') or []]
    rows += [('alt', item) for item in additions.get('alts') or []]
    if additions.get('faq'):
        rows.append(('faq', additions['faq']))
    if additions.get('takeaways'):
        rows.append(('takeaways', additions['takeaways']))
    return [(n, kind, item) for n, (kind, item) in enumerate(rows, 1)]


LABELS = {
    'opener': 'Definition-style opening',
    'table': 'Comparison table',
    'alt': 'Image alt text',
    'faq': 'FAQ',
    'takeaways': 'Key takeaways',
}
WHY = {
    'opener': 'says plainly what the post is about',
    'table': 'sets the comparison out at a glance',
    'alt': 'alt text from what the post says about the image; check it describes it',
    'faq': 'answers the questions readers ask next',
    'takeaways': 'gives the post’s points at a glance',
}
# Each addition in the summary, in a sentence.
HELPS = {
    'opener': 'Opens by saying plainly what the post is about, so the first lines answer it.',
    'table': 'Sets out the comparison the post makes, so it can be read at a glance.',
    'alt': 'Describes an image that has no alt text, for screen readers and assistants.',
    'faq': 'Answers the questions a reader asks next, from the post’s own text.',
    'takeaways': 'Gives the post’s own points at a glance near the top.',
}


def _why(kind, item):
    """The short reason beside a mark: the job's own for a change, an opening or a table."""
    if kind in ('change', 'opener', 'table') and item.get('note'):
        return item['note']
    return WHY.get(kind, '')


def _alt_segments(item):
    """An image given alt text: its name, then the alt text it would have, inserted."""
    found = LINK.fullmatch(item['after'].strip())
    if not found:
        return _segments(item['before'], item['after'])
    name = found.group(2).rsplit('/', 1)[-1].split('?')[0] or 'image'
    return [
        {'t': 'text', 'v': '[Image: ' + name + ' — alt text: '},
        {'t': 'ins', 'v': found.group(1)},
        {'t': 'text', 'v': ']'},
    ]


def _where(draft, item, kind):
    if kind in ('faq', 'takeaways') and item.get('insert'):
        at = item.get('at')
        if at == 'end':
            return 'at the end of the post'
        found = desk.CODEC.section(draft, at)
        return 'before “' + (found['heading'] if found else 'a section') + '”'
    return 'in ' + _part_name(draft, item.get('part'))


def _part_name(draft, part):
    if part == 'title':
        return 'the title'
    if part == 'opening':
        return 'the opening'
    found = desk.CODEC.section(draft, part)
    return '“' + found['heading'] + '”' if found and found['heading'] else 'a section'


BLANK = re.compile(r'\n[ \t]*\n')
IMAGE_ONLY = re.compile(r'\s*!\[([^\[\]\n]*)\]\(([^()\s]+)(?:\s+"[^"\n]*")?\)\s*')


def _blocks(text):
    """A part's paragraphs, each (start, end) in its text, a fenced code block kept whole."""
    spans, at, fenced, start = [], 0, False, None
    for found in re.finditer(r'[^\n]*(?:\n|$)', text):
        line = found.group(0)
        if not line:
            break
        if desk_images.FENCE.match(line):
            fenced = not fenced
        blank = not line.strip() and not fenced
        if blank and start is not None:
            spans.append((start, at))
            start = None
        elif not blank and start is None:
            start = found.start()
        at = found.start() + len(line.rstrip('\n'))
    if start is not None:
        spans.append((start, len(text.rstrip())))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _part_entries(text, marks):
    """A part's text as entries: plain blocks as Markdown, and blocks with changes marked.
    `marks` are (start, end, n, kind, item) spans, an insertion having start == end."""
    entries = []
    blocks = _blocks(text)
    groups = []
    for start, end in blocks:
        hit = [
            m
            for m in marks
            if m[0] < end and m[1] > start or (m[0] == m[1] and start < m[0] <= end)
        ]
        if groups and hit and any(m in groups[-1]['marks'] for m in hit):
            groups[-1]['end'] = end
            groups[-1]['marks'] += [m for m in hit if m not in groups[-1]['marks']]
        else:
            groups.append({'start': start, 'end': end, 'marks': hit})
    for group in groups:
        start, end = group['start'], group['end']
        replaced = sorted((m for m in group['marks'] if m[3] != 'table'), key=lambda m: m[0])
        if not replaced:
            block = text[start:end]
            image = IMAGE_ONLY.fullmatch(block)
            if image:
                name = image.group(2).rsplit('/', 1)[-1].split('?')[0]
                entries.append({'type': 'image', 'name': name, 'alt': image.group(1).strip()})
            else:
                entries.append({'type': 'text', 'markdown': block})
        else:
            segments, notes, at = [], [], start
            for m_start, m_end, n, kind, item in replaced:
                if m_start > at:
                    segments.append({'t': 'text', 'v': _plain(text[at:m_start])})
                segments += (
                    _alt_segments(item)
                    if kind == 'alt'
                    else _segments(item['before'], item['after'])
                )
                segments.append({'t': 'note', 'n': n})
                notes.append({'n': n, 'why': _why(kind, item)})
                at = m_end
            if at < end:
                segments.append({'t': 'text', 'v': _plain(text[at:end])})
            entries.append({'type': 'marked', 'segments': segments, 'notes': notes})
        for _start, _, n, kind, item in sorted(group['marks'], key=lambda m: m[0]):
            if kind == 'table':
                table = item['after'][len(item['before']) :].strip()
                entries.append(
                    {
                        'type': 'addition',
                        'n': n,
                        'kind': 'table',
                        'label': LABELS['table'],
                        'markdown': table,
                        'note': _why('table', item),
                        'flag': item.get('flag') or '',
                    }
                )
    return entries


def marked(draft, result):
    """The post with each change marked where it falls, and each addition where it would go.
    A change whose words another one already changes is listed, not marked twice."""
    by_part, inserts, overlaps = {}, {}, []
    for n, kind, item in _numbered(result):
        if kind in ('faq', 'takeaways') and item.get('insert'):
            inserts.setdefault(item.get('at'), []).append((n, kind, item))
            continue
        part = item.get('part')
        if kind in ('faq', 'takeaways'):
            # The post's own FAQ or takeaways, in a new form: the whole section, changed,
            # marked only when no other change falls in it.
            taken = by_part.setdefault(part, [])
            if taken:
                overlaps.append(n)
            else:
                taken.append((0, len(desk.text_of(draft, part) or ''), n, kind, item))
            continue
        text = (
            desk.text_of(draft, part)
            if part in ('title', 'opening') or desk.CODEC.section(draft, part)
            else None
        )
        if text is None or not item.get('before') or text.count(item['before']) != 1:
            overlaps.append(n)
            continue
        start = text.index(item['before'])
        span = (
            (start + len(item['before']),) * 2
            if kind == 'table'
            else (start, start + len(item['before']))
        )
        taken = by_part.setdefault(part, [])
        clash = any(
            (span[0] < b and span[1] > a) if span[0] != span[1] else a < span[0] < b
            for a, b, *_ in taken
        )
        if clash:
            overlaps.append(n)
            continue
        taken.append((*span, n, kind, item))
    post = []
    title = by_part.get('title')
    overlaps += [mark[2] for mark in (title or [])[1:]]
    if title:
        _, _, n, _, item = title[0]
        post.append(
            {
                'type': 'title',
                'segments': _segments(item['before'], item['after']) + [{'t': 'note', 'n': n}],
                'notes': [{'n': n, 'why': item.get('note') or ''}],
            }
        )
    else:
        post.append({'type': 'title', 'text': draft['title']})
    post += _part_entries(draft['opening'], by_part.get('opening', []))

    def insert(at):
        for n, kind, item in inserts.get(at, []):
            post.append(
                {
                    'type': 'addition',
                    'n': n,
                    'kind': kind,
                    'label': LABELS[kind],
                    'heading': item.get('heading'),
                    'markdown': item.get('after') or '',
                    'note': item.get('note') or WHY[kind],
                    'flag': item.get('flag') or '',
                }
            )

    for section in draft['sections']:
        insert(section['id'])
        post.append(
            {'type': 'heading', 'level': section.get('level', 2), 'text': section['heading']}
        )
        post += _part_entries(section['text'], by_part.get(section['id'], []))
    insert('end')
    return post, overlaps


def _summary(draft, result):
    rows = []
    for n, kind, item in _numbered(result):
        if kind == 'change':
            rows.append(
                {
                    'n': n,
                    'kind': 'change',
                    'why': item.get('note') or '',
                    'help': item.get('help') or '',
                    'where': _where(draft, item, kind),
                    'flag': item.get('flag') or '',
                }
            )
        else:
            rows.append(
                {
                    'n': n,
                    'kind': kind,
                    'label': LABELS[kind],
                    'why': _why(kind, item),
                    'help': HELPS[kind],
                    'where': _where(draft, item, kind),
                    'flag': item.get('flag') or '',
                }
            )
    return rows


def view(root, ident):
    """The report as the page reads it."""
    record = _settled(root, read(root, ident))
    status = _status(root, record)
    shown = {
        'id': record['id'],
        'kind': KIND,
        'title': record['title'],
        'url': record.get('url') or '',
        'final_url': record.get('final_url') or '',
        'read_at': record.get('read_at'),
        'created_at': record.get('created_at'),
        'status': status,
        'error': record.get('error') or '',
        'access': record.get('access'),
        'collection_item': record.get('collection_item'),
        'previous': record.get('previous'),
        'changed': record.get('changed'),
        'desk': _desk_shown(root, record),
    }
    shown['newer'] = next(
        (row['newer'] for row in listing(root)['items'] if row['id'] == ident), None
    )
    result = record.get('result')
    if status == 'ready' and result:
        post, overlaps = marked(record['draft'], result)
        shown.update(
            works=result['works'],
            recommendations=_summary(record['draft'], result),
            advice=result.get('summary') or '',
            post=post,
            overlaps=overlaps,
            questions=result.get('queries') or [],
            sources_needed=[
                {**row, 'where': _part_name(record['draft'], row['part'])}
                for row in result.get('sources_needed') or []
            ],
            dropped=result.get('dropped', 0),
        )
    return shown


def _desk_shown(root, record):
    ident = record.get('desk')
    if not ident:
        return None
    try:
        directory, article = studio.item(root, 'articles', ident)
    except (ValueError, OSError):
        return None
    if not desk.on_desk(directory):
        return None
    return {'id': ident, 'title': article.get('title'), 'changed': _desk_changed(directory, record)}


def _desk_changed(directory, record):
    draft = directory / 'DRAFT.md'
    return not draft.is_file() or studio.digest(draft.read_bytes()) != record.get('desk_digest')


# Downloads: Markdown, and one self-contained HTML file that prints cleanly to PDF.
def _date(value):
    return (value or '')[:10]


def _segment_markdown(segments):
    """A marked passage in Markdown: deletions struck through, insertions in bold, a space
    kept between a deletion and the insertion that replaces it."""
    out = []
    for at, segment in enumerate(segments):
        value = segment.get('v', '')
        if segment['t'] == 'text':
            out.append(value)
        elif segment['t'] in ('del', 'ins') and value.strip():
            mark = '~~' if segment['t'] == 'del' else '**'
            lead = value[: len(value) - len(value.lstrip())]
            tail = value[len(value.rstrip()) :]
            following = segments[at + 1]['t'] if at + 1 < len(segments) else ''
            if segment['t'] == 'del' and following == 'ins' and not tail:
                tail = ' '
            out.append(lead + mark + value.strip() + mark + tail)
        elif segment['t'] == 'note':
            out.append(' [' + str(segment['n']) + ']')
        else:
            out.append(value)
    return ''.join(out)


def _access_rows(access):
    return (access or {}).get('checks') or []


ACCESS_WORDS = {'ok': 'Fine', 'problem': 'Check this', 'note': 'Note', 'unknown': 'Couldn’t check'}


def markdown(root, ident):
    """The report as Markdown: insertions in bold, deletions struck through, each numbered."""
    shown = view(root, ident)
    if shown['status'] != 'ready':
        raise ValueError(NOT_READY)
    import published_post

    lines = ['# GEO report: ' + published_post._md(shown['title']), '']
    lines += [
        'Link: ' + shown['url'] if shown['url'] else 'From a team collection',
        '',
        'Read ' + _date(shown['read_at']) + '. Recommendations only: nothing on the page was '
        'changed. These are not ranking promises.',
        '',
    ]
    if shown.get('changed'):
        lines += ['## Since the last report', '', _changed_words(shown['changed']), '']
    lines += ['## Summary', '']
    if shown['works']:
        lines += ['What already works:', ''] + ['- ' + text for text in shown['works']] + ['']
    if shown['recommendations']:
        lines += ['Recommended, most helpful first:', '']
        for row in shown['recommendations']:
            label = row.get('label') + ': ' if row.get('label') else ''
            said = (row['help'] or row['why']).strip()
            lines.append(str(row['n']) + '. ' + label + said + ' (' + row['where'] + ')')
        lines.append('')
    else:
        lines += ['No changes are recommended.', '']
    if shown['advice']:
        lines += [shown['advice'], '']
    lines += ['## The post with changes marked', '']
    lines += ['Inserted words are in **bold**, deleted ones ~~struck through~~.', '']
    for entry in shown['post']:
        kind = entry['type']
        if kind == 'title':
            lines += [
                '### '
                + (
                    _segment_markdown(entry['segments']) if entry.get('segments') else entry['text']
                ),
                '',
            ]
            lines += _notes_markdown(entry)
        elif kind == 'heading':
            lines += ['#' * min(6, entry['level'] + 2) + ' ' + entry['text'], '']
        elif kind == 'text':
            lines += [entry['markdown'], '']
        elif kind == 'image':
            lines += [
                '[Image: '
                + entry['name']
                + (' — alt text: ' + entry['alt'] if entry['alt'] else ', no alt text')
                + ']',
                '',
            ]
        elif kind == 'marked':
            lines += [_segment_markdown(entry['segments']), '']
            lines += _notes_markdown(entry)
        else:
            lines += [
                '> **Suggested addition ['
                + str(entry['n'])
                + ']: '
                + entry['label']
                + '.** '
                + entry['note'],
                '>',
            ]
            if entry.get('heading'):
                lines.append('> **' + entry['heading'] + '**')
                lines.append('>')
            lines += ['> ' + line if line else '>' for line in entry['markdown'].split('\n')]
            if entry.get('flag'):
                lines += ['>', '> ' + entry['flag']]
            lines.append('')
    if shown['questions']:
        lines += ['## Questions this post answers', '']
        lines += [
            'Advice only: questions people might ask an AI assistant that this post answers.',
            '',
        ]
        lines += ['- ' + question for question in shown['questions']] + ['']
    if shown['sources_needed']:
        lines += ['## Sources needed', '']
        for row in shown['sources_needed']:
            lines.append(
                '- “' + _plain(row['claim']) + '” (' + row['where'] + '): ' + row['kind'] + '.'
            )
        lines.append('')
    if _access_rows(shown['access']):
        lines += ['## Page access', '', shown['access']['eligibility'], '']
        for row in _access_rows(shown['access']):
            lines.append('- ' + ACCESS_WORDS.get(row['status'], '') + ': ' + row['said'])
        lines += ['', shown['access']['site_owner'], '']
    # The page's and the assistant's words never become raw HTML or a non-http(s) link.
    content = published_post.safe_markdown('\n'.join(lines).rstrip() + '\n', download=True)
    return {'filename': _filename(shown, '.md'), 'content': content}


def _notes_markdown(entry):
    notes = entry.get('notes') or []
    if not notes:
        return []
    return (
        [
            '*'
            + '; '.join('[' + str(note['n']) + '] ' + note['why'] for note in notes if note['why'])
            + '*',
            '',
        ]
        if any(note['why'] for note in notes)
        else []
    )


def _changed_words(changed):
    if changed.get('same'):
        return 'The page’s text is the same as when it was read on ' + _date(changed['since']) + '.'
    said = ['Since the page was read on ' + _date(changed['since']) + ':']
    if changed.get('changed'):
        said.append('changed ' + ', '.join(changed['changed']) + ';')
    if changed.get('added'):
        said.append('added ' + ', '.join('“' + name + '”' for name in changed['added']) + ';')
    if changed.get('removed'):
        said.append('removed ' + ', '.join('“' + name + '”' for name in changed['removed']) + ';')
    before, after = changed.get('words') or [0, 0]
    said.append(str(before) + ' words then, ' + str(after) + ' now.')
    if changed.get('of'):
        said.append(
            str(changed['taken'])
            + ' of the '
            + str(changed['of'])
            + ' changes the last report recommended now read as it suggested.'
        )
    return ' '.join(said)


def _filename(shown, suffix):
    stem = re.sub(r'[^a-z0-9]+', '-', shown['title'].lower()).strip('-')[:60] or 'post'
    return 'geo-report-' + stem + suffix


STYLE = """
:root{color-scheme:light;--ink:#1d2433;--quiet:#5b6475;--rule:#d9dde5;--paper:#fff;
--ins:#0b6b3a;--ins-bg:#e3f4ea;--del:#9b1c1c;--del-bg:#fbe7e7;--note:#8a4b00;--tint:#f5f6f8}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--ink:#e6e8ee;--quiet:#a3aab8;
--rule:#3a4150;--paper:#151922;--ins:#7fd4a2;--ins-bg:#14321f;--del:#f0a3a3;--del-bg:#3a1b1b;
--note:#f2c27a;--tint:#1d222d}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,"Iowan Old Style",
"Times New Roman",serif}
main{max-width:46rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
h1,h2,h3,h4,.label,.quiet,header p,table,figure,.access{font-family:-apple-system,
BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
h1{font-size:1.9rem;line-height:1.2;margin:.2rem 0 .6rem}
h2{font-size:1.25rem;margin:2.4rem 0 .8rem;padding-top:.6rem;border-top:1px solid var(--rule)}
h3,h4{font-size:1.05rem;margin:1.6rem 0 .5rem}
header p,.quiet{color:var(--quiet);font-size:.9rem}
a{color:inherit}
ins{color:var(--ins);background:var(--ins-bg);text-decoration:none;border-radius:2px}
del{color:var(--del);background:var(--del-bg);border-radius:2px}
sup.n{font:600 .7rem/1 -apple-system,Helvetica,Arial,sans-serif;color:var(--note);margin-left:1px}
.why{font:.85rem/1.4 -apple-system,Helvetica,Arial,sans-serif;color:var(--note);margin:-.4rem 0 1rem}
.addition{border-left:3px solid var(--note);background:var(--tint);padding:.7rem 1rem;
margin:1rem 0;break-inside:avoid}
.addition .label{font-weight:600;font-size:.85rem;margin:0 0 .4rem}
figure{margin:1rem 0;padding:.6rem .8rem;border:1px dashed var(--rule);font-size:.85rem;
color:var(--quiet)}
table{border-collapse:collapse;font-size:.9rem;margin:.6rem 0}
td,th{border:1px solid var(--rule);padding:.3rem .5rem;text-align:left}
ol,ul{padding-left:1.4rem}
pre{white-space:pre-wrap;font-size:.85rem}
.flag{font:.85rem -apple-system,Helvetica,Arial,sans-serif;color:var(--del)}
@media print{:root{color-scheme:light;--ink:#000;--quiet:#444;--paper:#fff;--tint:#f4f4f4}
main{max-width:none;padding:0}@page{margin:18mm 16mm}h2{break-after:avoid}
.marked,.addition,figure,table{break-inside:avoid}a{text-decoration:none}}
"""


def _inline_html(text):
    """Escaped inline Markdown: links (shown, never followed by the report), code, bold and
    italic. Nothing a document says is ever taken as markup."""
    out, at = [], 0
    for found in LINK.finditer(text):
        out.append(_emphasis(html.escape(text[at : found.start()])))
        if found.group(0).startswith('!'):
            out.append(html.escape(_plain(found.group(0))))
        elif re.match(r'https?://', found.group(2)):
            out.append(
                '<a href="'
                + html.escape(found.group(2), quote=True)
                + '">'
                + _emphasis(html.escape(found.group(1)))
                + '</a>'
            )
        else:
            out.append(_emphasis(html.escape(found.group(1))))
        at = found.end()
    out.append(_emphasis(html.escape(text[at:])))
    return ''.join(out)


def _emphasis(escaped):
    """Code, bold and italic in already escaped text; a backslash-escaped mark stays text and
    loses its backslash."""
    escaped = re.sub(r'(?<!\\)`([^`\n]+)(?<!\\)`', r'<code>\1</code>', escaped)
    escaped = re.sub(r'(?<!\\)\*\*([^*\n]+?)(?<!\\)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(
        r'(?<![\w*\\])\*(?=\S)([^*\n]+?)(?<=[^\s\\])\*(?![\w*])', r'<em>\1</em>', escaped
    )
    return re.sub(r'\\(&lt;|&gt;|&amp;|&quot;|&#x27;|[\\`*_{}\[\]()#+\-.!|~])', r'\1', escaped)


QUOTES_DEEP = 6  # quotation levels drawn; deeper ones are drawn as text at that depth


def _markdown_html(text, depth=0):
    """A block of Markdown as HTML: paragraphs, lists, quotations, code and tables. Never
    recursive past QUOTES_DEEP, however the text is nested."""
    out = []
    for start, end in _blocks(text):
        block = text[start:end]
        lines = block.split('\n')
        if desk_images.FENCE.match(lines[0]):
            code = '\n'.join(lines[1:-1] if desk_images.FENCE.match(lines[-1]) else lines[1:])
            out.append('<pre><code>' + html.escape(code) + '</code></pre>')
        elif all(re.match(r'\s*\|', line) for line in lines) and len(lines) >= 2:
            rows = [
                [cell.strip() for cell in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
                for line in lines
                if not desk_finish.SEPARATOR.match(line)
            ]
            head, body = rows[0], rows[1:]
            out.append(
                '<table><thead><tr>'
                + ''.join('<th>' + _inline_html(cell) + '</th>' for cell in head)
                + '</tr></thead><tbody>'
                + ''.join(
                    '<tr>' + ''.join('<td>' + _inline_html(c) + '</td>' for c in row) + '</tr>'
                    for row in body
                )
                + '</tbody></table>'
            )
        elif all(re.match(r'\s*(?:[-*+]|\d+[.)])\s', line) for line in lines if line.strip()):
            tag = 'ol' if re.match(r'\s*\d', lines[0]) else 'ul'
            items = [
                re.sub(r'^\s*(?:[-*+]|\d+[.)])\s+', '', line) for line in lines if line.strip()
            ]
            out.append(
                '<'
                + tag
                + '>'
                + ''.join('<li>' + _inline_html(i) + '</li>' for i in items)
                + '</'
                + tag
                + '>'
            )
        elif all(line.lstrip().startswith('>') for line in lines) and depth < QUOTES_DEEP:
            inner = '\n'.join(re.sub(r'^\s*>\s?', '', line) for line in lines)
            out.append('<blockquote>' + _markdown_html(inner, depth + 1) + '</blockquote>')
        elif re.match(r'#{1,6}\s', lines[0]):
            out.append('<h4>' + _inline_html(lines[0].lstrip('#').strip()) + '</h4>')
            if lines[1:]:
                out.append(_markdown_html('\n'.join(lines[1:]), QUOTES_DEEP))
        else:
            out.append('<p>' + '<br>'.join(_inline_html(line) for line in lines) + '</p>')
    return ''.join(out)


def _segments_html(segments):
    out = []
    for at, segment in enumerate(segments):
        value = html.escape(segment.get('v', ''))
        following = segments[at + 1]['t'] if at + 1 < len(segments) else ''
        if segment['t'] == 'text':
            out.append(value)
        elif segment['t'] == 'del':
            out.append('<del>' + value + '</del>' + (' ' if following == 'ins' else ''))
        elif segment['t'] == 'ins':
            out.append('<ins>' + value + '</ins>')
        else:
            out.append('<sup class="n">' + str(segment['n']) + '</sup>')
    return ''.join(out)


def _notes_html(entry):
    notes = [note for note in entry.get('notes') or [] if note['why']]
    if not notes:
        return ''
    return (
        '<p class="why">'
        + ' · '.join(str(note['n']) + ': ' + html.escape(note['why']) for note in notes)
        + '</p>'
    )


def page(root, ident):
    """The report as one self-contained HTML file: its own styles, no scripts and nothing
    fetched from anywhere, typeset to print cleanly to PDF."""
    shown = view(root, ident)
    if shown['status'] != 'ready':
        raise ValueError(NOT_READY)
    e = html.escape
    body = ['<header><p>GEO report</p><h1>' + e(shown['title']) + '</h1>']
    if shown['url']:
        body.append(
            '<p><a href="' + e(shown['url'], quote=True) + '">' + e(shown['url']) + '</a></p>'
        )
    body.append(
        '<p>Read ' + e(_date(shown['read_at'])) + '. Recommendations only: nothing on the page '
        'was changed. These are not ranking promises.</p></header>'
    )
    if shown.get('changed'):
        body.append(
            '<h2>Since the last report</h2><p>' + e(_changed_words(shown['changed'])) + '</p>'
        )
    body.append('<h2>Summary</h2>')
    if shown['works']:
        body.append(
            '<h3>What already works</h3><ul>'
            + ''.join('<li>' + e(t) + '</li>' for t in shown['works'])
            + '</ul>'
        )
    if shown['recommendations']:
        body.append('<h3>Recommended, most helpful first</h3><ol>')
        for row in shown['recommendations']:
            label = '<strong>' + e(row['label']) + ':</strong> ' if row.get('label') else ''
            body.append(
                '<li value="'
                + str(row['n'])
                + '">'
                + label
                + e((row['help'] or row['why']).strip())
                + ' <span class="quiet">('
                + e(row['where'])
                + ')</span></li>'
            )
        body.append('</ol>')
    else:
        body.append('<p>No changes are recommended.</p>')
    if shown['advice']:
        body.append('<p>' + e(shown['advice']) + '</p>')
    body.append(
        '<h2>The post with changes marked</h2><p class="quiet">Inserted words are '
        '<ins>marked like this</ins>, deleted ones <del>like this</del>; each number is a '
        'recommendation above.</p>'
    )
    for entry in shown['post']:
        kind = entry['type']
        if kind == 'title':
            text = _segments_html(entry['segments']) if entry.get('segments') else e(entry['text'])
            body.append('<h3 class="marked">' + text + '</h3>' + _notes_html(entry))
        elif kind == 'heading':
            body.append('<h4>' + _inline_html(entry['text']) + '</h4>')
        elif kind == 'text':
            body.append(_markdown_html(entry['markdown']))
        elif kind == 'image':
            body.append(
                '<figure>Image: '
                + e(entry['name'])
                + ' — '
                + (e('alt text: ' + entry['alt']) if entry['alt'] else 'no alt text')
                + '</figure>'
            )
        elif kind == 'marked':
            body.append(
                '<p class="marked" style="white-space:pre-line">'
                + _segments_html(entry['segments'])
                + '</p>'
                + _notes_html(entry)
            )
        else:
            body.append(
                '<section class="addition"><p class="label">Suggested addition '
                + str(entry['n'])
                + ': '
                + e(entry['label'])
                + '</p><p class="quiet">'
                + e(entry['note'])
                + '</p>'
                + ('<h4>' + e(entry['heading']) + '</h4>' if entry.get('heading') else '')
                + _markdown_html(entry['markdown'])
                + ('<p class="flag">' + e(entry['flag']) + '</p>' if entry.get('flag') else '')
                + '</section>'
            )
    if shown['questions']:
        body.append(
            '<h2>Questions this post answers</h2><p class="quiet">Advice only: questions people '
            'might ask an AI assistant that this post answers.</p><ul>'
            + ''.join('<li>' + e(q) + '</li>' for q in shown['questions'])
            + '</ul>'
        )
    if shown['sources_needed']:
        body.append('<h2>Sources needed</h2><ul>')
        for row in shown['sources_needed']:
            body.append(
                '<li>“'
                + e(_plain(row['claim']))
                + '” <span class="quiet">('
                + e(row['where'])
                + ')</span>: '
                + e(row['kind'])
                + '.</li>'
            )
        body.append('</ul>')
    if _access_rows(shown['access']):
        body.append(
            '<h2>Page access</h2><p class="quiet">'
            + e(shown['access']['eligibility'])
            + '</p><ul class="access">'
        )
        for row in _access_rows(shown['access']):
            body.append(
                '<li><strong>'
                + e(ACCESS_WORDS.get(row['status'], ''))
                + ':</strong> '
                + e(row['said'])
                + '</li>'
            )
        body.append('</ul><p class="quiet">' + e(shown['access']['site_owner']) + '</p>')
    document = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>GEO report: ' + e(shown['title']) + '</title><style>' + STYLE + '</style></head>'
        '<body><main>' + ''.join(body) + '</main></body></html>\n'
    )
    return {'filename': _filename(shown, '.html'), 'content': document}


# Edit this post on the desk: a desk copy with the report's recommendations in Finishing.
SETS = (
    ('finish-geo', 'geo'),
    ('finish-opener', 'opener'),
    ('finish-table', 'table'),
    ('finish-alt', 'alt'),
    ('finish-faq', 'faq'),
    ('finish-takeaways', 'takeaways'),
    ('finish-queries', 'queries'),
)


def _remapped(raw, ids):
    """The job's result with each section id the report read put as the desk copy's."""

    def swap(value):
        if isinstance(value, dict):
            return {
                key: (ids.get(item, item) if key in ('part', 'closing_cta') else swap(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [swap(item) for item in value]
        return value

    return swap(raw)


def desk_copy(root, ident, operation):
    """Turn the report into an editable desk copy of the post, once: the post as it was
    read, with the report's recommendations waiting in Finishing to apply or skip. The same
    desk copy is opened again afterwards; the report is kept."""
    import desk_jobs
    import published_post

    _require_lock()
    record = read(root, ident)
    if _status(root, record) != 'ready' or not record.get('result'):
        raise ValueError(NOT_READY)
    shown = _desk_shown(root, record)
    if shown:
        return shown['id']
    staged = published_post.stage(
        root,
        {
            key: record.get(key)
            for key in ('title', 'markdown', 'url', 'final_url', 'read_at', 'collection_item')
        }
        | {'words': 0, 'headings': [], 'links': [], 'images': [], 'access': None},
    )
    made = desk.dispatch(
        root,
        'create',
        {
            'operation': operation,
            'title': record['title'],
            'first_pass': 'leave',
            'published': {'preview': staged['preview'], 'expected': staged['expected']},
        },
    )
    article = made['id']
    draft = desk.read(root, article)
    ids = {}
    if len(draft['sections']) == len(record['draft']['sections']):
        ids = {
            old['id']: new['id']
            for old, new in zip(record['draft']['sections'], draft['sections'], strict=True)
        }
    raw = _remapped((record['result'] or {}).get('raw') or {}, ids)
    payload = _payload(draft)
    found = read_result(draft, payload, raw)
    sets = {
        'geo': found['changes'],
        'opener': [found['additions']['opener']] if found['additions']['opener'] else [],
        'table': found['additions']['tables'],
        'alt': found['additions']['alts'],
        'faq': [found['additions']['faq']] if found['additions']['faq'] else [],
        'takeaways': [found['additions']['takeaways']] if found['additions']['takeaways'] else [],
    }
    geo_job = None
    for kind, tool in SETS:
        extra = {}
        if tool == 'queries':
            if not found['queries']:
                continue
            items, extra = [], {'queries': found['queries']}
        else:
            items = [{k: v for k, v in item.items() if k != 'help'} for item in sets[tool]]
            if not items and tool != 'geo':
                continue
        if tool == 'geo':
            extra = {'basis': desk_finish.basis(payload), 'auto': True}
            if found['summary']:
                extra['summary'] = found['summary']
        name = secrets.token_hex(16)
        desk_finish.keep(root, article, name, kind, items, dropped=0, report=ident, **extra)
        if tool == 'geo':
            geo_job = name
    # The report stands for the post's one GEO review: none runs again by itself.
    directory, kept = studio.item(root, 'articles', article)
    kept['geo_review'] = {
        'include': True,
        'queued_at': studio.now(),
        'job': geo_job,
        'report': ident,
    }
    studio.persist(directory, 'articles', kept)
    desk_jobs.geo_due(root, article)
    record['desk'] = article
    record['desk_digest'] = studio.digest((directory / 'DRAFT.md').read_bytes())
    _write(root, record)
    return article


# A new Google Doc of the post with each change as a suggestion and its reason as a comment.
def _visible(text):
    lines = [line for line in str(text or '').split('\n')]
    if len(lines) != 1:
        return None
    return desk_finish._visible(lines[0])


def findings(record):
    """The report's recommendations as Google findings: each change (and the definition
    opening) a suggested edit with its reason; each addition a comment where it would go."""
    result = record.get('result') or {}
    draft = record['draft']
    rows = []
    for n, kind, item in _numbered(result):
        reason = (item.get('note') or WHY.get(kind, '')).strip()
        if item.get('help'):
            reason = (reason + '. ' if reason else '') + item['help']
        if kind in ('change', 'opener'):
            before, after = _visible(item.get('before')), _visible(item.get('after'))
            if before and after and before != after:
                rows.append(
                    {
                        'id': 'geo-' + str(n),
                        'kind': 'edit',
                        'before': before,
                        'after': after,
                        'reason': ('GEO report ' + str(n) + ': ' + reason)[:1000],
                    }
                )
                continue
        anchor = _anchor(draft, kind, item)
        if not anchor:
            continue
        text = item.get('after') or ''
        if kind == 'table':
            text = text[len(item.get('before') or '') :].strip()
        words = (
            'GEO report '
            + str(n)
            + ': '
            + LABELS.get(kind, 'Change')
            + ' suggested '
            + _where(draft, item, kind)
            + ' ('
            + reason
            + '). '
            + _plain(text)
        )
        rows.append(
            {
                'id': 'geo-' + str(n),
                'kind': 'comment',
                'before': anchor,
                'reason': words[:990] + ('…' if len(words) > 990 else ''),
            }
        )
    return rows


def _anchor(draft, kind, item):
    """Visible words to hang a comment on: the heading an addition goes before, or the
    sentence it follows, or an image's paragraph."""
    if kind in ('faq', 'takeaways') and item.get('insert'):
        at = item.get('at')
        found = desk.CODEC.section(draft, at) if at != 'end' else None
        if found and _visible(found['heading']):
            return _visible(found['heading'])
        last = draft['sections'][-1] if draft['sections'] else None
        text = last['text'] if last else draft['opening']
        lines = [line for line in text.split('\n') if line.strip()]
        return _visible(lines[-1]) if lines else None
    before = item.get('before') or ''
    if kind == 'alt':
        return None  # An image has no words of its own to hang a comment on.
    lines = [line for line in before.split('\n') if line.strip()]
    return _visible(lines[-1]) if lines else None


def link_again(url):
    """The link Run again reads: a team collection's http:// link is read as https://, the
    only kind the bounded fetcher reads."""
    if isinstance(url, str) and url.startswith('http://'):
        return 'https://' + url[len('http://') :]
    return url


def _google_guard(root, record, article):
    directory, _ = studio.item(root, 'articles', article)
    if _desk_changed(directory, record):
        raise ValueError(DESK_CHANGED)
    return studio.digest((directory / 'DRAFT.md').read_bytes() + record['id'].encode())


MODES = ('auto', 'native', 'comments')


def google_prepare(root, ident, article):
    """Under the studio lock: the report's desk copy, unchanged since the report made it,
    with its private Google Doc made once and linked (google_handoff's own reservation and
    readback, which keep the blog's record in step and so run under the lock, as the desk's
    Make a Google Doc does). Returns what placing the findings needs; nothing is planned."""
    import google_handoff
    import google_suggestions as suggestions

    record = read(root, ident)
    if _status(root, record) != 'ready' or not record.get('result'):
        raise ValueError(NOT_READY)
    if record.get('desk') != article:
        raise ValueError('Make this post’s desk copy first.')
    expected = _google_guard(root, record, article)
    wanted = findings(record)
    if not wanted:
        raise ValueError('This report has nothing to send to a Google Doc.')
    made = google_handoff.open_as_doc(root, article, desk=True)
    _, _, target = suggestions.linked(root, article, 'draft')
    return {
        'article': article,
        'expected': expected,
        'url': made['url'],
        'findings': wanted,
        'document_id': target['document_id'],
        'tab_ids': target['tab_ids'],
        'projection': target.get('projection'),
    }


def google_place(root, prepared, mode):
    """Outside the lock: read the new Doc once and keep the findings it can take, each found
    once and clear of the others. ([placed], how many could not be placed)."""
    import google_drive as drive
    import google_suggestions as suggestions
    from google_manuscript import PROJECTION, view as manuscript_view

    if mode not in MODES:
        raise ValueError('Choose suggestions, comments or suggestions with comments fallback.')
    client = drive.Client(drive.account_for(root))
    inline, accepted, _ = suggestions.read_for_review(client, prepared['document_id'], mode)
    shown = manuscript_view(inline) if prepared['projection'] == PROJECTION else inline
    tabs = prepared['tab_ids']
    placed, left = [], 0
    for finding in prepared['findings']:
        try:
            located = suggestions.locate(shown, finding, tabs)
            suggestions.build(inline, placed + [located], tabs, accepted)
        except (ValueError, KeyError, TypeError):
            left += 1  # Words the Doc holds more than once, or that another change covers.
            continue
        placed.append(located)
    if not placed:
        raise ValueError('None of the recommendations could be placed in the Google Doc.')
    return placed, left


def google_finish(root, ident, prepared, placed, left, mode):
    """Under the lock again: the plan, bound to the desk copy as it still is (the desk's own
    planning, which reads the Doc once more to bind it). Nothing is sent."""
    import google_drive as drive
    import manuscript_editor

    record = read(root, ident)
    article = prepared['article']
    if _google_guard(root, record, article) != prepared['expected']:
        raise ValueError(DESK_CHANGED)
    client = drive.Client(drive.account_for(root))
    plan = manuscript_editor.google_plan(
        client, root, article, placed, mode, prepared['expected'], prepared['url']
    )
    record['google'] = {'url': prepared['url'], 'desk': article, 'planned_at': studio.now()}
    _write(root, record)
    return {
        **plan,
        'url': prepared['url'],
        'suggestions': sum(1 for f in placed if f['kind'] == 'edit'),
        'comments': sum(1 for f in placed if f['kind'] == 'comment'),
        'left': left,
    }


def google_plan(root, ident, mode, operation):
    """All three steps for a caller that holds the lock throughout (tests); the page's route
    reads Google outside the lock (management.report_google)."""
    article = desk_copy(root, ident, operation)
    prepared = google_prepare(root, ident, article)
    placed, left = google_place(root, prepared, mode)
    return google_finish(root, ident, prepared, placed, left, mode)


def google_send(root, ident, data):
    """Send a confirmed plan once, while the desk copy is as the report made it."""
    import google_drive as drive
    import manuscript_editor

    record = read(root, ident)
    google = record.get('google') or {}
    if not google.get('desk'):
        raise ValueError('Check the Google Doc first.')
    expected = _google_guard(root, record, google['desk'])
    client = drive.Client(drive.account_for(root))
    result = manuscript_editor.google_send(client, root, google['desk'], data, expected)
    record['google'] = {**google, 'sent_at': studio.now(), 'status': result.get('status')}
    _write(root, record)
    return {**result, 'url': google.get('url')}
