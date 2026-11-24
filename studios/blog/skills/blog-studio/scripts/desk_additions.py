"""Reader aids and AI search additions on the desk: an FAQ, key takeaways, a comparison
table, quotes from sources, alt text, likely search questions and a definition-style opening,
each a proposal read from a finishing job.

Part of desk_finish, which keeps every name its callers use.
"""

import re

import desk
import desk_images
import studio
from desk_finishing import (
    UNREADABLE,
    _located,
    _payload,
    _prose_parts,
    _reference,
    _replacement,
    _rows,
    _text,
)
from desk_proposals import (
    EMPTY,
    GONE,
    QUOTE_LINE,
    TABLE_LINE,
    _flags,
    _once,
    _path,
    basis,
    json_text,
    present,
)


# Reader aids and AI search additions, each on request: an FAQ or key takeaways as a new section, a
# comparison table or a quotation from a source after a paragraph, alt text for an image that
# has none, a definition-style opening, and likely search questions (advice only). Each is a
# proposal the person previews, then applies or skips; nothing is applied by itself. Each
# writes only from the draft, its brief and its selected sources (blog-geo-review.md), and
# works on any desk post, so a review of a published post can ask for the same ones.
ADDITIONS = ('faq', 'table', 'quotes', 'takeaways', 'alt', 'queries', 'opener')
GEO_RULES = (
    'Write only from the draft, its brief, its selected sources and any research supplied. '
    'Never invent a statistic, quotation, citation, link, name, result or experience: where '
    'the evidence is missing, leave the addition out and say in summary what source would be '
    'needed. Keep the author’s voice, stance and qualifiers. Do not promise rankings, '
    'citations or traffic, and do not mention search engines or AI assistants in the text.'
)
FAQ_HEADING = 'Frequently asked questions'
TAKEAWAYS_HEADING = 'Key takeaways'
FAQ_FOUND = re.compile(
    r'(?:faqs?|frequently asked questions|questions and answers|q\s?&\s?a|common questions)',
    re.I,
)
TAKEAWAYS_FOUND = re.compile(r'(?:key takeaways|takeaways|tl;?\s?dr|at a glance|in short)', re.I)
# A heading that closes a post with a call to action: an FAQ goes before it.
CTA = re.compile(
    r'\b(?:next steps?|get started|try it|call to action|learn more|sign up|contact us|'
    r'get in touch|what to do next|your turn|join us|book a demo|start (?:your|a) free)\b',
    re.I,
)
FAQ_COUNTS = (3, 4, 5, 6)
TAKEAWAYS_MOST = 6
TABLES_MOST = 2
QUOTES_MOST = 3
QUERIES_MOST = 10
ALT_MOST = 20
ALT_LIMIT = 125  # characters of alt text, as screen readers read it comfortably
NO_COUNT = 'Choose 3 to 6 questions.'
NO_QUOTE_SOURCES = 'Add a source first: quotations come only from your sources, word for word.'
NO_IMAGES = 'This post has no images to describe.'
ALL_ALT = 'Every image in this post already has alt text.'
STALE_ADDITION = (
    'This was suggested before the post’s latest changes, so it was not added. Run it again '
    'for the latest.'
)
ALT_NOTE = (
    'Written from what the post says about this image: its caption, the text around it and '
    'its file name. Blog Studio cannot see the image itself, so check this describes it.'
)
ALT_KEEP = (
    'Keep the image reference as it is, and change only the words between ![ and ], on one '
    'line of up to 125 characters.'
)
FAQ = (
    'Write a short FAQ for this post: the questions a reader of it would ask next, each with '
    'an answer of one to three sentences. Write questions_wanted questions, or fewer when the '
    'post cannot answer that many: a question the draft and its sources do not answer is left '
    'out, never guessed. Each answer says only what the draft or its sources say. Do not repeat '
    'the post’s headings as questions. Also name, in closing_cta, the id of the last section '
    'when it is a closing call to action (the FAQ goes before it), or "" when there is none.'
)
FAQ_AGAIN = (
    ' The post already has an FAQ, in faq_section: propose its new form instead of a second '
    'one, keeping each question and answer that still holds, correcting any the draft no '
    'longer supports, and adding the reader questions it misses.'
)
FAQ_JSON = (
    'Return JSON in content: {"questions": [{"question": ..., "answer": ...}], "closing_cta": '
    '..., "summary": ...}. Each question is one line ending with a question mark; each answer '
    'is plain prose with no heading; summary says in a sentence what was left out and why, '
    'or "".'
)
TAKEAWAYS = (
    'Write the key takeaways of this post: three to five of its own points, each one short '
    'line a reader could act on or remember, in the order the post makes them. Add no point '
    'the post does not make.'
)
TAKEAWAYS_AGAIN = (
    ' The post already has key takeaways, in takeaways_section: propose their new form instead '
    'of a second set.'
)
TAKEAWAYS_JSON = (
    'Return JSON in content: {"takeaways": ["...", ...], "summary": ...}, each takeaway one '
    'line with no list mark; summary is one sentence or "".'
)
TABLE = (
    'Where this post really compares things (options, versions, approaches, before and after), '
    'propose a Markdown comparison table of what it says about them, placed after the '
    'paragraph that makes the comparison. Build every cell from the post or its sources, '
    'never fill a cell the post does not support, and propose no table where the post does '
    'not compare things.'
)
TABLE_JSON = (
    'Return JSON in content: {"tables": [{"part": ..., "after_text": ..., "table": ..., '
    '"why": ...}], "summary": ...}, at most two. part is "opening" or the id of a section in '
    'sections; after_text is the last sentence of the paragraph the table follows, copied '
    'exactly from that part; table is a Markdown table with a header row and a separator '
    'row; summary says, when there is no table, why ("" otherwise).'
)
QUOTES = (
    'Propose up to three quotations from the sources that support a point the post makes: '
    'each an exact passage copied word for word from one source in sources, never '
    'paraphrased, joined or invented, placed after the paragraph whose point it supports. '
    'Choose passages a reader would find useful, of one to three sentences.'
)
QUOTES_JSON = (
    'Return JSON in content: {"quotes": [{"source": ..., "quote": ..., "part": ..., '
    '"after_text": ..., "why": ...}], "summary": ...}. source is the id of the source in '
    'sources; quote is copied exactly from its text; part is "opening" or the id of a section '
    'in sections; after_text is the last sentence of the paragraph the quotation follows, '
    'copied exactly from that part; summary is one sentence or "".'
)
ALT = (
    'Write alt text for each image in images_without_alt. You cannot see the images: write '
    'only from what the post says about each one, in its context (the paragraphs around it) '
    'and its file name. Never describe what the image shows beyond what that says. Keep each '
    'under 125 characters, plain, with no "Image of" or "Picture of". When the post says '
    'nothing that tells what an image shows, return "" for its alt.'
)
ALT_JSON = (
    'Return JSON in content: {"alts": [{"image": ..., "alt": ..., "why": ...}]}, image being '
    'the image id from images_without_alt; why names what the alt rests on, such as "the '
    'caption under it".'
)
QUERIES = (
    'List the questions people might ask an AI assistant or a search engine that this post '
    'answers well: five to ten, each as a person would type or say it. These are advice for '
    'the author only; they are not added to the post. List only questions the post really '
    'answers.'
)
QUERIES_JSON = 'Return JSON in content: {"queries": ["...", ...], "summary": ...}.'
OPENER = (
    'Propose a definition-style opening: one or two sentences that say plainly what the '
    'post’s topic is and what the post argues, to replace the opening’s first one or two '
    'sentences. Define only what the post itself says, in the author’s voice.'
)
OPENER_JSON = (
    'Return JSON in content: {"before": ..., "after": ..., "why": ...}. before is the '
    'opening’s first one or two sentences, copied exactly ("" when the opening is empty); '
    'after is the one- or two-sentence replacement, with no heading.'
)
HTTP_IMAGE = re.compile(r'!\[([^\[\]\n]*)\]\((?![ \t]*<?data:)([^()\s]+)((?:[ \t]+"[^"\n]*")?)\)')
SEPARATOR = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$')


def _found_section(draft, pattern):
    """The section whose heading is just its name, as "FAQ" or "Frequently asked questions"
    (or "Key takeaways"), at any level; "Why FAQs fail" is not the post's FAQ. None."""
    for section in draft['sections']:
        heading = re.sub(r'[*_#:.!?\s]+$', '', re.sub(r'^[*_#\s]+', '', section['heading'] or ''))
        if pattern.fullmatch(' '.join(heading.split())):
            return section
    return None


def _addition(root, ident, draft, tool, extra, shared_words, count):
    """The payload, guidance and job details for one of the Reader aids and AI search additions."""
    import desk_jobs

    research, said = desk_jobs._research_extra(root, ident)
    payload = {**_payload(draft, extra), **research}
    common = _reference('modules', 'blog-geo-review.md') + '\n\n' + shared_words + said
    common += '\n\n' + GEO_RULES + '\n'
    meta = {}
    if tool == 'faq':
        if type(count) is not int or count not in FAQ_COUNTS:
            raise ValueError(NO_COUNT)
        meta['count'] = count
        payload['questions_wanted'] = count
        found = _found_section(draft, FAQ_FOUND)
        guidance = FAQ
        if found:
            payload['faq_section'] = {key: found[key] for key in ('id', 'heading', 'text')}
            guidance += FAQ_AGAIN
        guidance += '\n\n' + common + FAQ_JSON
    elif tool == 'takeaways':
        found = _found_section(draft, TAKEAWAYS_FOUND)
        guidance = TAKEAWAYS
        if found:
            payload['takeaways_section'] = {key: found[key] for key in ('id', 'heading', 'text')}
            guidance += TAKEAWAYS_AGAIN
        guidance += '\n\n' + common + TAKEAWAYS_JSON
    elif tool == 'table':
        guidance = TABLE + '\n\n' + common + TABLE_JSON
    elif tool == 'quotes':
        if not extra['sources']:
            raise ValueError(NO_QUOTE_SOURCES)
        guidance = QUOTES + '\n\n' + common + QUOTES_JSON
    elif tool == 'alt':
        wanted = _alt_wanted(draft)
        if not wanted:
            raise ValueError(ALL_ALT if _has_images(draft) else NO_IMAGES)
        payload['images_without_alt'] = wanted
        guidance = ALT + '\n\n' + common + ALT_JSON
    elif tool == 'queries':
        guidance = QUERIES + '\n\n' + common + QUERIES_JSON
    else:
        guidance = OPENER + '\n\n' + common + OPENER_JSON
    return payload, guidance, meta


def _known(job):
    """Every word the job read: the post, its sources and its research, for the facts check."""
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    texts = [str(payload.get('title') or ''), str(payload.get('opening') or '')]
    for key in ('sections', 'sources'):
        texts += [
            str(row.get('text') or '') for row in payload.get(key) or [] if isinstance(row, dict)
        ]
    for key in ('research_bundle', 'research'):
        if payload.get(key):
            texts.append(json_text(payload[key]))
    return '\n'.join(texts)


def _added_facts(text, known):
    """A flag when an addition has a number or a link that nothing the job read has."""
    from studio_core import text_checks

    found, have = text_checks.facts(text), text_checks.facts(known)
    said = [
        word
        for key, word in (('numbers', 'a number'), ('links', 'a link'))
        if {value for value, _ in found[key]} - {value for value, _ in have[key]}
    ]
    if not said:
        return ''
    return (
        'Check the facts: this adds '
        + ' and '.join(said)
        + ' the post and its sources do not have.'
    )


def _line(value, limit):
    """One line of plain text, or '' when it is not one."""
    if not isinstance(value, str):
        return ''
    value = ' '.join(value.split()).strip()
    return value if value and len(value) <= limit else ''


def _payload_section(job, key):
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    found = payload.get(key)
    return found if isinstance(found, dict) and isinstance(found.get('id'), str) else None


def _faq_place(draft, cta):
    """Where an FAQ goes by default: before a closing call to action, else at the end. The
    call to action is the last section, as the job named it or as its heading says."""
    if len(draft['sections']) < 2:
        return 'end', None
    last = draft['sections'][-1]
    if cta == last['id'] or CTA.search(last['heading'] or ''):
        return last['id'], last['id']
    return 'end', None


def _section_item(draft, job, key, heading, text, at, extra):
    """A new section, or a new form of the one the post already has (its whole text)."""
    found = _payload_section(job, key)
    current = desk.CODEC.section(draft, found['id']) if found else None
    if current is not None:
        return {
            'part': current['id'],
            'whole': True,
            'before': desk_images.scrub(found.get('text') or ''),
            'after': text,
            **extra,
        }
    return {
        'part': 'new',
        'insert': True,
        'heading': heading,
        'before': '',
        'after': text,
        'at': at,
        'basis': basis(job.get('payload') or {}),
        **extra,
    }


def faq_text(rows):
    """An FAQ's questions and answers as Markdown: each question in bold, then its answer."""
    return '\n\n'.join('**' + row['question'] + '**\n\n' + row['answer'] for row in rows)


def takeaways_text(rows):
    return '\n'.join('- ' + row['point'] for row in rows)


def _read_faq(draft, found, job):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    rows, dropped = _rows(found, 'questions', ('question', 'answer'))
    count = ((job.get('metadata') or {}).get('desk') or {}).get('count') or 5
    kept, seen = [], set()
    deepest = desk.limit(draft)
    for row in rows:
        question = _line(row['question'], 300).strip('*# ').strip()
        answer = row['answer'].strip()
        if (
            not question
            or not answer
            or len(answer) > 2000
            or desk.has_heading(answer, deepest)
            or question.casefold() in seen
        ):
            dropped += 1
            continue
        seen.add(question.casefold())
        kept.append({'question': question, 'answer': answer})
    dropped += max(0, len(kept) - count)
    kept = kept[:count]
    extra = {'count': count}
    if _text(found.get('summary'), 2000):
        extra['summary'] = _text(found['summary'], 2000)
    if not kept:
        return [], dropped, extra
    text = faq_text(kept)
    at, cta = _faq_place(draft, found.get('closing_cta'))
    item = _section_item(
        draft,
        job,
        'faq_section',
        FAQ_HEADING,
        text,
        at,
        {
            'questions': kept,
            'cta': cta,
            'note': 'Each answer comes only from the post and its sources; a question they '
            'do not answer was left out.',
            'flag': _added_facts(text, _known(job)),
        },
    )
    return [item], dropped, extra


def _read_takeaways(draft, found, job):
    if not isinstance(found, dict) or not isinstance(found.get('takeaways'), list):
        raise ValueError(UNREADABLE)
    kept, seen, dropped = [], set(), 0
    for value in found['takeaways'][:20]:
        point = _line(value.get('point') if isinstance(value, dict) else value, 300)
        point = point.lstrip('-*• ').strip()
        if not point or point.casefold() in seen or desk.has_heading(point, desk.limit(draft)):
            dropped += 1
            continue
        seen.add(point.casefold())
        kept.append({'point': point})
    dropped += max(0, len(kept) - TAKEAWAYS_MOST)
    kept = kept[:TAKEAWAYS_MOST]
    summary = _text(found.get('summary'), 2000)
    extra = {'summary': summary} if summary else {}
    if not kept:
        return [], dropped, extra
    text = takeaways_text(kept)
    first = draft['sections'][0]['id'] if draft['sections'] else 'end'
    item = _section_item(
        draft,
        job,
        'takeaways_section',
        TAKEAWAYS_HEADING,
        text,
        first,
        {
            'points': kept,
            'note': 'The post’s own points, in its order.',
            'flag': _added_facts(text, _known(job)),
        },
    )
    return [item], dropped, extra


BLANK = re.compile(r'\n[ \t]*\n')
HEADING_LINE = re.compile(r' {0,3}#{1,6}(?:[ \t]|$)')
INDENTED = re.compile(r'(?: {4}|\t)')


def _paragraph_end(draft, part, text):
    """`text` located once in its part, where it ends a paragraph of prose: what follows it is
    nothing or a blank line, and the paragraph it ends is not a list, a table, a quotation, a
    heading or code. Something can go after it as a block of its own; None otherwise."""
    if part not in _prose_parts(draft):
        return None
    anchor = _located(draft, part, text)
    if anchor is None:
        return None
    whole = desk.text_of(draft, part)
    at = whole.index(anchor)
    end = at + len(anchor)
    rest = whole[end:].lstrip(' \t')
    if rest.strip() and not BLANK.match(rest):
        return None  # It ends a line, not a paragraph: the next line would join the block.
    lines = whole[:end].split('\n')
    fenced = False
    for line in lines:
        if desk_images.FENCE.match(line):
            fenced = not fenced
    if fenced:
        return None  # Inside fenced code.
    starts = [m.end() for m in BLANK.finditer(whole, 0, at)]
    paragraph = whole[starts[-1] if starts else 0 : end].strip('\n').split('\n')
    for line in paragraph:
        if (
            desk_images.FENCE.match(line)
            or desk_images.LIST_LINE.match(line)
            or TABLE_LINE.match(line)
            or QUOTE_LINE.match(line)
            or HEADING_LINE.match(line)
            or INDENTED.match(line)
        ):
            return None
    return anchor


def _read_table(draft, found, job):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    rows, dropped = _rows(found, 'tables', ('part', 'after_text', 'table'))
    items, known = [], _known(job)
    for row in rows:
        anchor = _paragraph_end(draft, row['part'], row['after_text'])
        lines = [line.strip() for line in row['table'].strip().splitlines()]
        if (
            anchor is None
            or not 3 <= len(lines) <= 40
            or not all(TABLE_LINE.match(line) for line in lines)
            or not SEPARATOR.match(lines[1])
            or len(items) >= TABLES_MOST
        ):
            dropped += 1
            continue
        table = '\n'.join(lines)
        items.append(
            {
                'part': row['part'],
                'before': anchor,
                'after': anchor + '\n\n' + table,
                'note': _text(row.get('why'), 500),
                'flag': _added_facts(table, known),
            }
        )
    summary = _text(found.get('summary'), 2000)
    return items, dropped, {'summary': summary} if summary else {}


def _plain(text):
    return ' '.join(str(text or '').replace('’', "'").replace('‘', "'").split())


QUOTE_OPEN = '"\'“‘(['
QUOTE_CLOSE = '"\'”’)]'


def _whole_sentences(quote, source):
    """Whether `quote` is in `source` (spacing aside) as one or more whole sentences: what
    comes before it ends a sentence or a clause (or is nothing), and it ends a sentence."""
    quote, source = _plain(quote).strip(QUOTE_OPEN + QUOTE_CLOSE + ' '), _plain(source)
    if not quote or quote[-1] not in '.!?':
        return False
    at = source.find(quote)
    while at != -1:
        before = source[:at].rstrip(QUOTE_OPEN + ' ')
        after = source[at + len(quote) :].lstrip(QUOTE_CLOSE)
        if (not before or before[-1] in '.!?:;' + QUOTE_CLOSE) and (not after or after[0] == ' '):
            return True
        at = source.find(quote, at + 1)
    return False


def _read_quotes(draft, found, job):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    rows, dropped = _rows(found, 'quotes', ('source', 'quote', 'part', 'after_text'))
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    sources = [s for s in payload.get('sources') or [] if isinstance(s, dict)]
    items, seen = [], set()
    for row in rows:
        source = next((s for s in sources if row['source'] in (s.get('id'), s.get('name'))), None)
        quote = ' '.join(row['quote'].split()).strip('"“”').strip()
        anchor = _paragraph_end(draft, row['part'], row['after_text'])
        # Word for word: the passage is in the source's own text, spacing aside.
        if (
            source is None
            or not 20 <= len(quote) <= 800
            or not _whole_sentences(quote, source.get('text'))
            or anchor is None
            or quote in seen
            or len(items) >= QUOTES_MOST
        ):
            dropped += 1
            continue
        seen.add(quote)
        name = _line(source.get('name'), 300) or 'a source'
        why = _text(row.get('why'), 500)
        items.append(
            {
                'part': row['part'],
                'before': anchor,
                'after': anchor + '\n\n> ' + quote + '\n>\n> — ' + name,
                'source': name,
                'note': ' '.join(filter(None, [why, 'Word for word from ' + name + '.'])),
                'flag': '',
            }
        )
    summary = _text(found.get('summary'), 2000)
    return items, dropped, {'summary': summary} if summary else {}


def _image(text):
    """(kind, target, alt) for text that is exactly one image: a reference to an image the
    draft holds, or an ordinary http(s) image; None otherwise."""
    text = text.strip()
    found = desk_images.REFERENCE.fullmatch(text)
    if found:
        label = found.group(2) or found.group(1)
        return 'reference', desk_images.key(label), found.group(1) if found.group(2) else ''
    found = HTTP_IMAGE.fullmatch(text)
    if found:
        return 'link', found.group(2) + found.group(3), found.group(1)
    return None


def _with_alt(reference, alt):
    found = desk_images.REFERENCE.fullmatch(reference)
    if found:
        return '![' + alt + '][' + (found.group(2) or found.group(1)) + ']'
    found = HTTP_IMAGE.fullmatch(reference)
    return '![' + alt + '](' + found.group(2) + found.group(3) + ')'


def _image_parts(draft):
    return ['opening'] + [s['id'] for s in draft['sections']]


def _has_images(draft):
    return any(
        desk_images.REFERENCE.search(desk.text_of(draft, part))
        or HTTP_IMAGE.search(desk.text_of(draft, part))
        for part in _image_parts(draft)
    )


def _alt_wanted(draft):
    """Each image in the text with no alt text of its own, with what the post says around it
    and its file name, for a job that cannot see the images. An image kept in the Google Doc
    shows a placeholder and is left as it is."""
    held = draft.get('images') or {}
    images = {desk_images.key(label): entry for label, entry in held.items()}
    wanted = []
    for part in _image_parts(draft):
        text = desk.text_of(draft, part)
        masked = desk_images._masked(text)
        found = [(m, 'reference') for m in desk_images.REFERENCE.finditer(masked)]
        found += [(m, 'link') for m in HTTP_IMAGE.finditer(masked)]
        for match, kind in sorted(found, key=lambda pair: pair[0].start()):
            reference = text[match.start() : match.end()]
            alt = match.group(1).strip()
            if kind == 'reference':
                label = match.group(2) or match.group(1)
                if not match.group(2):
                    alt = ''  # ![image1][]: its words are its label, not alt text.
                entry = images.get(desk_images.key(label))
                name = (entry if isinstance(entry, dict) else {}).get('title') or label
            else:
                name = match.group(2).rsplit('/', 1)[-1].split('?')[0]
            if (
                (alt and not desk_images.OURS.fullmatch(alt))
                or match.group(1).strip() == desk_images.KEPT_ALT
                or not _once(text, reference)
            ):
                continue
            paragraphs = re.split(r'\n[ \t]*\n', text)
            at = len(re.split(r'\n[ \t]*\n', text[: match.start()])) - 1
            around = '\n\n'.join(paragraphs[max(0, at - 1) : at + 2])
            wanted.append(
                {
                    'image': 'i' + str(len(wanted) + 1),
                    'part': part,
                    'reference': reference,
                    'file_name': str(name)[:200],
                    'context': desk_images.scrub(around)[:1200],
                }
            )
            if len(wanted) >= ALT_MOST:
                return wanted
    return wanted


def _read_alt(draft, found, job):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    rows, dropped = _rows(found, 'alts', ('image', 'alt'))
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    wanted = {
        image.get('image'): image
        for image in payload.get('images_without_alt') or []
        if isinstance(image, dict)
    }
    items, unknown, done = [], 0, set()
    for row in rows:
        image = wanted.get(row['image'])
        if image is None or row['image'] in done:
            dropped += 1
            continue
        done.add(row['image'])
        if not row['alt'].strip():
            unknown += 1  # The post says nothing that tells what it shows.
            continue
        alt = _line(row['alt'], ALT_LIMIT)
        reference = image.get('reference') or ''
        if (
            not alt
            or '[' in alt
            or ']' in alt
            or _image(reference) is None
            or _located(draft, image.get('part'), reference) != reference
        ):
            dropped += 1
            continue
        why = _text(row.get('why'), 300).rstrip('.')
        items.append(
            {
                'part': image['part'],
                'before': reference,
                'after': _with_alt(reference, alt),
                'alt': True,
                'note': ALT_NOTE + (' It rests on ' + why + '.' if why else ''),
                'flag': _added_facts(alt, _known(job)),
            }
        )
    unknown += sum(1 for name in wanted if name not in done)
    return items, dropped, {'unknown': unknown} if unknown else {}


def _alt_fit(draft, item, after, text):
    """An image reference with new alt text in place of the one it had: the same image, and
    only its words changed."""
    if not _once(text, item['before']):
        raise ValueError(GONE)
    was, now = _image(item['before']), _image(after)
    alt = now[2] if now else ''
    if (
        now is None
        or was is None
        or now[:2] != was[:2]
        or not alt.strip()
        or len(alt) > ALT_LIMIT
        or '\n' in after.strip()
    ):
        raise ValueError(ALT_KEEP)
    if now[0] == 'reference':
        for label, entry in (draft.get('images') or {}).items():
            if desk_images.key(label) == now[1] and isinstance(entry, dict):
                draft['images'] = {**draft['images'], label: {**entry, 'alt': alt.strip()}}
    at = text.index(item['before'])
    return text[:at] + after.strip() + text[at + len(item['before']) :]


def _read_queries(draft, found, job):
    if not isinstance(found, dict) or not isinstance(found.get('queries'), list):
        raise ValueError(UNREADABLE)
    kept, seen, dropped = [], set(), 0
    for value in found['queries'][:30]:
        query = _line(value.get('query') if isinstance(value, dict) else value, 200)
        if not query or query.casefold() in seen:
            dropped += 1
            continue
        seen.add(query.casefold())
        kept.append(query)
    dropped += max(0, len(kept) - QUERIES_MOST)
    extra = {'queries': kept[:QUERIES_MOST]}
    if _text(found.get('summary'), 2000):
        extra['summary'] = _text(found['summary'], 2000)
    return [], dropped, extra


def _read_opener(draft, found, job):
    if not isinstance(found, dict) or not isinstance(found.get('after'), str):
        raise ValueError(UNREADABLE)
    note = _text(found.get('why'), 500)
    opening = draft['opening']
    if not opening.strip():
        after = found['after'].strip()
        if not after or len(after) > 1000 or '\n' in after:
            return [], 1, {}
        item = {'part': 'opening', 'whole': True, 'before': '', 'after': after}
        return [{**item, 'note': note, 'flag': ''}], 0, {}
    before = _located(draft, 'opening', found.get('before'))
    # It replaces the opening's first sentences, so they are where the opening starts, in a
    # paragraph of prose (not a list, a table, a quotation or code), and it is prose too: one
    # paragraph that joins the rest of that paragraph as the sentences it replaces did.
    first = opening.lstrip().split('\n')[0]
    if (
        before is None
        or not opening.lstrip().startswith(before)
        or '\n' in before
        or any(
            rule.match(first)
            for rule in (
                desk_images.FENCE,
                desk_images.LIST_LINE,
                TABLE_LINE,
                QUOTE_LINE,
                HEADING_LINE,
                INDENTED,
            )
        )
    ):
        return [], 1, {}
    after = _replacement(draft, 'opening', before, found['after'])
    if after is None or len(after) > 1000 or '\n' in after:
        return [], 1, {}
    item = {'part': 'opening', 'before': before, 'after': after, 'note': note}
    return [{**item, 'flag': _flags(before, after)}], 0, {}


ADDITION_READERS = {
    'finish-faq': _read_faq,
    'finish-table': _read_table,
    'finish-quotes': _read_quotes,
    'finish-takeaways': _read_takeaways,
    'finish-alt': _read_alt,
    'finish-queries': _read_queries,
    'finish-opener': _read_opener,
}


def _insert(root, ident, seen, job, found, item, entry):
    """Add a proposed section (an FAQ or key takeaways) to the draft, where the person
    placed it: before a section, or at the end. Only while the post is as the job read it."""
    import desk_jobs

    if item['state'] != 'open':
        raise ValueError('This suggestion was already applied or skipped.')
    draft = desk.read(root, ident)
    desk.checked(draft, seen, ['outline'])
    if any(desk_jobs.busy(other) for other in desk_jobs.jobs(root, ident)):
        raise ValueError('A desk job is working on this draft. Wait for it, or stop it, then add.')
    if not present(draft, {**item, 'at': 'end'}):
        raise ValueError(STALE_ADDITION)
    after = entry.get('after', item['after'])
    if not isinstance(after, str) or not after.strip():
        raise ValueError(EMPTY)
    if len(after) > desk.LIMIT:
        raise ValueError('Keep one part under 200,000 characters.')
    after = after.strip()
    desk.checked_text('new', after, desk.limit(draft))
    at = entry.get('at', item.get('at'))
    ids = [section['id'] for section in draft['sections']]
    if at != 'end' and at not in ids:
        raise ValueError('Choose where the new section goes.')
    added = {'id': desk._id(set(ids)), 'heading': item['heading'], 'brief': '', 'text': after}
    draft['sections'].insert(len(ids) if at == 'end' else ids.index(at), added)
    desk._write(root, ident, draft, [added['id'], 'outline'])
    item.update(state='applied', landed=after, section=added['id'], placed=at)
    studio.write_json(_path(root, ident, job), found)
    return {'applied': 1, 'left': [], 'added': added['id']}
