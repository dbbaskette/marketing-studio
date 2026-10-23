"""Finishing on the desk: tools that propose changes the person previews, then applies,
edits or skips.

Nothing changes until Apply. A proposal set waits on this computer only, in
.blog-runs/desk-proposals/<blog id>/<job id>.json, never in the blog's own folder, so a team
workspace records only what Apply writes, as a decision. Each Apply keeps a `finishing`
version of every part it changes first. Like desk.py, every function expects the caller to
hold the studio lock.
"""

import re
import shutil

import desk
import studio

# The finishing job kinds and the tool each one is in the panel.
TOOLS = {
    'finish-humanize': 'humanize',
    'finish-facts': 'facts',
    'finish-headline': 'headline',
    'finish-feedback': 'feedback',
}
KINDS = tuple(TOOLS)
JOB = re.compile(r'[a-f0-9]{32}')
ITEM = re.compile(r'p[0-9]{1,3}')
ITEMS = 200  # proposals in one set
GONE = 'That text is no longer in this part, so the suggestion was not applied. Skip it.'
NONE_LEFT = 'None of these suggestions match the text now, so nothing was applied.'


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('Desk writes run under the studio lock.')


def _folder(root, ident):
    return studio.inside(root, '.blog-runs', 'desk-proposals', studio.identifier(ident))


def _path(root, ident, job):
    if not isinstance(job, str) or not JOB.fullmatch(job):
        raise ValueError('Choose a set of suggestions on this blog.')
    return studio.inside(
        root, '.blog-runs', 'desk-proposals', studio.identifier(ident), job + '.json'
    )


def keep(root, ident, job, kind, items, **extra):
    """Keep a set of proposals for the person to preview; nothing in the draft changes."""
    _require_lock()
    if kind not in TOOLS:
        raise ValueError('Choose a finishing tool.')
    record = {
        'schema': 1,
        'job': job,
        'kind': kind,
        'blog': ident,
        'made_at': studio.now(),
        **extra,
        'items': [
            {**item, 'id': 'p' + str(number + 1), 'state': 'open'}
            for number, item in enumerate(items[:ITEMS])
        ],
    }
    studio.write_json(_path(root, ident, job), record)
    return record


def read(root, ident, job):
    target = _path(root, ident, job)
    if not target.is_file() or target.is_symlink():
        raise ValueError('These suggestions are no longer here. Run the tool again.')
    found = studio.read_json(target)
    if not isinstance(found, dict) or found.get('blog') != ident:
        raise ValueError('These suggestions are no longer here. Run the tool again.')
    return found


def sets(root, ident):
    """Every set kept for this blog, oldest first."""
    folder = _folder(root, ident)
    found = []
    for target in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        if target.is_symlink() or not JOB.fullmatch(target.stem):
            continue
        try:
            value = studio.read_json(target)
        except (ValueError, OSError):
            continue
        if isinstance(value, dict) and value.get('kind') in TOOLS and value.get('blog') == ident:
            found.append(value)
    return sorted(found, key=lambda value: value.get('made_at') or '')


def forget(root, ident):
    """Let a deleted blog's waiting suggestions go: they hold its text."""
    folder = _folder(root, ident)
    if folder.is_dir() and not folder.is_symlink():
        shutil.rmtree(folder)


def present(draft, item):
    """Whether a proposal still fits the draft: its text is in its part, once, or the whole
    part is as it was for an alternative to the whole part. A comment needs only its part."""
    if item.get('part') == 'whole':
        return True
    try:
        text = desk.text_of(draft, item.get('part'))
    except ValueError:
        return False
    if 'comment' in item:
        return True
    if item.get('whole'):
        return text == item.get('before')
    before = item.get('before') or ''
    return bool(before) and text.count(before) == 1


def summary(root, ident, draft):
    """The newest set for each tool, as the panel shows it."""
    newest = {}
    for value in sets(root, ident):
        newest[TOOLS[value['kind']]] = value
    return {
        tool: {
            **value,
            'items': [{**item, 'present': present(draft, item)} for item in value['items']],
        }
        for tool, value in newest.items()
    }


def _busy_parts(root, ident):
    """The parts a desk job under way may change, so an Apply never races it."""
    import desk_jobs

    parts = set()
    for job in desk_jobs.jobs(root, ident):
        if desk_jobs.busy(job):
            parts.add(((job.get('metadata') or {}).get('desk') or {}).get('part'))
    return parts


def apply(root, ident, seen, job, chosen):
    """Apply chosen proposals, each with its suggested text or the person's own (Edit).

    One proposal that no longer fits is refused with nothing changed. Several at once
    (Apply all) apply every one that still fits and leave the rest open, counted in `left`.
    Each part changed keeps one `finishing` version first."""
    found = read(root, ident, job)
    if not isinstance(chosen, list) or not chosen or len(chosen) > ITEMS:
        raise ValueError('Choose the suggestions to apply.')
    items = {item['id']: item for item in found['items']}
    picks, named = [], set()
    for entry in chosen:
        if (
            not isinstance(entry, dict)
            or set(entry) - {'id', 'after'}
            or entry.get('id') not in items
            or entry['id'] in named
        ):
            raise ValueError('Choose suggestions from this set.')
        named.add(entry['id'])
        item = items[entry['id']]
        if 'comment' in item:
            raise ValueError('A comment changes nothing. Make it a note, or skip it.')
        if 'after' not in item and 'after' not in entry:
            raise ValueError('Write the wording to use, then apply it.')
        if item['state'] != 'open':
            raise ValueError('This suggestion was already applied or skipped.')
        after = entry['after'] if 'after' in entry else item['after']
        if not isinstance(after, str) or len(after) > desk.LIMIT:
            raise ValueError('Keep one part under 200,000 characters.')
        picks.append((item, after))
    draft = desk.read(root, ident)
    parts = sorted({item['part'] for item, _ in picks})
    desk.checked(draft, seen, parts)
    working = _busy_parts(root, ident)
    if any(part in working or ('sections' in working and part not in desk.PARTS) for part in parts):
        raise ValueError('A desk job is working on this part. Wait for it, or stop it, then apply.')
    single = len(picks) == 1
    texts, applied, left = {}, [], []
    for item, after in picks:
        part = item['part']
        try:
            text = texts[part] if part in texts else desk.text_of(draft, part)
            fits = text == item['before'] if item.get('whole') else text.count(item['before']) == 1
            if not item['before'] and not item.get('whole'):
                fits = False
            if not fits:
                raise ValueError(GONE)
            if item.get('whole'):
                updated = after.strip()
            else:
                at = text.index(item['before'])
                updated = text[:at] + after + text[at + len(item['before']) :]
            desk.checked_text(part, updated)
            if part == 'title' and not updated.strip():
                raise ValueError('Keep the title to one line, up to 500 characters.')
        except ValueError:
            if single:
                raise
            left.append(item['id'])
            continue
        texts[part] = updated
        applied.append(item)
    if not applied:
        raise ValueError(NONE_LEFT)
    changed = []
    for part, text in texts.items():
        before = desk.text_of(draft, part)
        if before.strip() == text.strip():
            continue
        desk.keep(root, ident, part, before, 'finishing')
        desk._set(draft, part, text)
        changed.append(part)
    for item in applied:
        item['state'] = 'applied'
        if item.get('group'):
            for other in found['items']:
                if other.get('group') == item['group'] and other['state'] == 'open':
                    other['state'] = 'skipped'  # An alternative to the one chosen.
    studio.write_json(_path(root, ident, job), found)
    if changed:
        desk._write(root, ident, draft, changed)
    return {'applied': len(applied), 'left': left}


def skip(root, ident, job, ids):
    """Set proposals aside. Only this computer's waiting set changes."""
    found = read(root, ident, job)
    if not isinstance(ids, list) or not ids or len(ids) > ITEMS:
        raise ValueError('Choose the suggestions to skip.')
    items = {item['id']: item for item in found['items']}
    if any(not isinstance(name, str) or name not in items for name in ids):
        raise ValueError('Choose suggestions from this set.')
    for name in ids:
        if items[name]['state'] == 'open':
            items[name]['state'] = 'skipped'
    studio.write_json(_path(root, ident, job), found)
    return {'skipped': len(ids)}


# Proofread: mechanical checks in process, no job. Advisory, never an authorship verdict.
AI_TELLS = ('blogforge', 'voice', 'assets', 'ai-tells')
COMMON_STARTS = frozenset({'the', 'a', 'an'})
PROOF_LIMIT = 300  # findings shown at once
BOUNDARY = re.compile(
    r'(?<=[.!?…])["”’)\]]*[ \t]+|\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d{1,3}[.)]|#|>)[ \t])'
)
WORD = re.compile(r'[^\W\d_]+(?:[’\'-][^\W\d_]+)*')
SENTENCE_MAX = 2000  # a passage Fix rewrites; a longer run is cut to its line


def _listed(name):
    import blog_runner

    path = blog_runner.REFERENCES.joinpath(*AI_TELLS, name)
    return [
        line.strip()
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]


def proof_rules():
    """The desk's mechanical rules: no em dashes or double hyphens, and the words and
    phrases BlogForge listed as reading machine-written. A desk blog has no voice rules."""
    return {
        'no_em_dashes': True,
        'no_ascii_double_hyphen': True,
        'banished_words': _listed('words.txt'),
        'banished_phrases': _listed('phrases.txt'),
    }


def _sentences(text):
    """(start, end) of each sentence-like run in a part, without the spaces around it."""
    spans, at = [], 0
    for cut in [*BOUNDARY.finditer(text), None]:
        end = cut.start() if cut else len(text)
        piece = text[at:end]
        lead = len(piece) - len(piece.lstrip())
        if piece.strip():
            spans.append((at + lead, at + len(piece.rstrip())))
        if cut:
            at = cut.end()
    return spans


def _sentence(text, start, spans=None):
    """The sentence holding `start`, as (its text, where it starts in the part)."""
    for begin, end in spans or _sentences(text):
        if begin <= start < end:
            if end - begin > SENTENCE_MAX:
                line_start = text.rfind('\n', 0, start) + 1
                line_end = text.find('\n', start)
                begin, end = line_start, line_end if line_end != -1 else len(text)
                end = min(end, begin + SENTENCE_MAX)
            return text[begin:end], begin
    return text[start : start + 1], start


def _offsets(draft):
    """Where each part sits in the Markdown desk.join makes, to place findings in it."""
    places, at = [], 0
    if draft.get('title'):
        places.append(('title', at + 2, draft['title']))
        at += 2 + len(draft['title']) + 2
    if draft.get('opening'):
        places.append(('opening', at, draft['opening']))
        at += len(draft['opening']) + 2
    for section in draft['sections']:
        at += 3 + len(section['heading'])
        if section['text']:
            places.append((section['id'], at + 2, section['text']))
            at += 2 + len(section['text'])
        at += 2
    return places


def _label(rule, target):
    if rule == 'em-dash':
        return 'A dash (' + target + '). Many readers take it as machine writing.', (
            'Replace the dash with a comma, a full stop, a colon or brackets.'
        )
    if rule == 'double-hyphen':
        return 'A double hyphen (--).', 'Replace the double hyphen with suitable punctuation.'
    if rule.startswith('banished:'):
        term = rule.partition(':')[2]
        return '“' + target + '” often reads as machine-written.', (
            'Say it without “' + term + '”, in plain words.'
        )
    if rule == 'duplicate-paragraph':
        return 'This paragraph repeats an earlier one.', 'Cut the repetition, or say something new.'
    if rule == 'ai-starter':
        return '“' + target + '” to start a sentence often reads as machine-written.', (
            'Start the sentence without “' + target + '”.'
        )
    if rule == 'repeated-start':
        return 'Two sentences in a row start with “' + target + '”.', (
            'Vary how this sentence starts.'
        )
    if rule == 'repeated-word':
        return '“' + target + '” three times in one paragraph.', (
            'Use “' + target + '” less often here.'
        )
    return 'This section opens the way another one does.', 'Open this section differently.'


def _finding(part, text, rule, start, target, spans=None):
    sentence, at = _sentence(text, start, spans)
    label, fix = _label(rule, target)
    return {
        'part': part,
        'rule': rule,
        'label': label,
        'fix': fix,
        'target': target,
        'sentence': sentence,
        'start': at,
        'at': start,
    }


def _repetition(part, text):
    """Within one part: an AI-tell sentence opener, two sentences in a row with the same
    first word, and a long word three times in one paragraph."""
    from text_checks import mask_protected

    clean = mask_protected(text)
    spans = _sentences(text)
    starters = {word.casefold() for word in _listed('sentence-starters.txt')}
    found, previous = [], None
    for begin, end in spans:
        first = WORD.search(clean, begin, end)
        word = first.group() if first and first.start() == begin else None
        if word and word.casefold() in starters:
            found.append(_finding(part, text, 'ai-starter', begin, word, spans))
        elif (
            word
            and previous
            and word.casefold() == previous.casefold()
            and word.casefold() not in COMMON_STARTS
        ):
            found.append(_finding(part, text, 'repeated-start', begin, word, spans))
        previous = word
    for paragraph in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', clean):
        seen = {}
        for match in WORD.finditer(paragraph.group()):
            word = match.group().casefold()
            if len(word) < 6:
                continue
            seen[word] = seen.get(word, 0) + 1
            if seen[word] == 3:
                start = paragraph.start() + match.start()
                found.append(_finding(part, text, 'repeated-word', start, match.group(), spans))
    return found


def _openers(draft):
    found, seen = [], {}
    for section in draft['sections']:
        paragraph = section['text'].strip().split('\n\n')[0]
        opener = ' '.join(paragraph.lower().split()[:8])
        if len(opener.split()) >= 6:
            if opener in seen:
                found.append(_finding(section['id'], section['text'], 'echoed-opener', 0, opener))
            seen[opener] = section['id']
    return found


def proofread(root, ident):
    """Mechanical findings for each part, in draft order, each with the sentence Fix would
    rewrite. Reading only: nothing is written and no job starts."""
    from text_checks import lint

    draft = desk.read(root, ident)
    places = _offsets(draft)
    findings = []
    for hit in lint(desk.join(draft), proof_rules())['findings']:
        if 'start' not in hit:
            continue
        for part, offset, text in places:
            if offset <= hit['start'] < offset + len(text):
                local = hit['start'] - offset
                target = text[local : local + len(hit['target'])].split('\n')[0][:200]
                findings.append(_finding(part, text, hit['rule'], local, target))
                break
    for part, _, text in places:
        findings += _repetition(part, text)
    findings += _openers(draft)
    order = {part: number for number, (part, _, _) in enumerate(places)}
    findings.sort(key=lambda found: (order.get(found['part'], 0), found['at'], found['rule']))
    return {
        'id': ident,
        'revision': draft['revision'],
        'findings': findings[:PROOF_LIMIT],
        'more': max(0, len(findings) - PROOF_LIMIT),
        'limitations': 'Mechanical matches and repetition hints only; read for meaning. Code, '
        'links and quotations are left out.',
    }


# The tools that propose through a job: what each asks for, and how its result is read.
UNREADABLE = 'The suggestions came back in a shape Blog Studio cannot read. Run it again.'
NO_TEXT = 'Write the draft first: Finishing works on written text.'
NO_SOURCES = 'Add a source first: facts are checked against your sources.'
LEVELS = {
    'light': 'Intensity: light. Smooth the flow and replace formulaic wording only; keep each '
    'sentence’s structure where you can.',
    'medium': 'Intensity: medium. Also vary rhythm and sentence openings, and let the point of '
    'view come through.',
    'strong': 'Intensity: strong. Rework sentences that read as generic so they sound like a '
    'person explaining their own work, keeping every fact.',
}
HUMANIZE = (
    'Find the sentences in this draft that read as machine-written: formulaic or stock '
    'wording, monotonous rhythm, repeated entrances, generic stance. Suggest a rewrite for each. '
    'Keep every number, name, quotation and link exactly. Never invent an opinion, experience, '
    'hesitation or anecdote. Leave sentences that already read well alone.'
)
HUMANIZE_JSON = (
    'Return JSON in content: {"suggestions": [{"part": ..., "before": ..., "after": ..., '
    '"why": ...}]}, at most 40. part is "opening" or the id of a section in sections; before is '
    'one or two whole sentences copied exactly from that part, character for character; after '
    'replaces before; why says in a few words what reads as machine-written.'
)
FACTS = (
    'Check each factual claim in the draft against sources and any research. A claim is '
    'supported when a source passage says it, not-in-sources when no source says it, and '
    'contradicted when a source says otherwise. Judge only from what is supplied; do not '
    'research.'
)
FACTS_JSON = (
    'Return JSON in content: {"claims": [{"part": ..., "before": ..., "verdict": ..., '
    '"passage": ..., "source": ..., "after": ..., "why": ...}]}, at most 40. part is "opening" '
    'or the id of a section in sections; before is the claim, copied exactly from that part; '
    'verdict is "supported", "not-in-sources" or "contradicted"; passage is the source passage '
    'it rests on, copied exactly ("" when none); source names that source; after is a rewording '
    'the sources support, for a claim that is not supported ("" when none fits); why says why.'
)
HEADLINE = (
    'Suggest alternatives for the title and the opening of this draft, from the draft itself, '
    'its brief and its sources. The title promises the topic; the opening pulls the reader into '
    'the argument. Make the alternatives meaningfully different from each other and from what '
    'is there. No clickbait, no promise the post cannot keep, no number the draft does not have.'
)
HEADLINE_JSON = (
    'Return JSON in content: {"titles": [{"text": ..., "why": ...}], "openings": [{"text": ..., '
    '"why": ...}]}, with up to five titles of one line each and up to three openings, each a '
    'whole replacement for the opening with no heading; why names what it does differently.'
)
FEEDBACK = (
    'Give editorial feedback on this draft without rewriting it: its shape, its argument, '
    'whether it serves its audience, and claims that need evidence. Quote the passage each '
    'comment is about and say the reader’s difficulty and a specific move. Nothing you say is '
    'applied to the text.'
)
FEEDBACK_JSON = (
    'Return JSON in content: {"summary": ..., "comments": [{"part": ..., "quote": ..., '
    '"aspect": ..., "comment": ...}]}, at most 30 comments. part is "title", "opening", the id '
    'of a section in sections, or "whole" for the draft as a whole; quote is a short passage '
    'copied exactly from that part ("" for none); aspect is "shape", "argument", "audience" or '
    '"claims"; summary is two or three sentences on the draft overall.'
)
VERDICTS = {
    'supported': 'supported',
    'not-in-sources': 'not-in-sources',
    'unsupported': 'not-in-sources',
    'contradicted': 'contradicted',
}
ASPECTS = ('shape', 'argument', 'audience', 'claims')
NAME = re.compile(r'\b[A-Z][A-Za-z0-9]+\b')


def _reference(*path):
    import blog_runner

    return blog_runner.REFERENCES.joinpath(*path).read_text(encoding='utf-8').rstrip()


def _payload(draft, extra):
    return {
        'title': draft['title'],
        'brief': draft.get('brief') or {},
        'opening': draft['opening'],
        'sections': [
            {'id': s['id'], 'heading': s['heading'], 'text': s['text']} for s in draft['sections']
        ],
        **extra,
    }


def request(root, ident, draft, tool, level=None):
    """The kind, payload, guidance and job details for one finishing tool on this draft."""
    import blog_runner
    import desk_jobs
    import manuscript_editor

    kinds = {tool: kind for kind, tool in TOOLS.items()}
    if tool not in kinds:
        raise ValueError('Choose a finishing tool.')
    written = draft['opening'].strip() or any(s['text'].strip() for s in draft['sections'])
    if tool != 'headline' and not written:
        raise ValueError(NO_TEXT)
    extra, shared = desk_jobs._context(root, draft)
    extra.pop('response_kind', None)  # The suggestions are JSON in content.
    extra.pop('gaps', None)
    meta = {}
    if tool == 'humanize':
        if level not in LEVELS:
            raise ValueError('Choose light, medium or strong.')
        meta['level'] = level
        payload = {**_payload(draft, extra), 'level': level}
        guidance = (
            HUMANIZE + ' ' + LEVELS[level] + '\n\n' + _reference('modules', 'blog-humanize.md')
        )
        guidance += '\n\n' + shared + '\n' + HUMANIZE_JSON
    elif tool == 'facts':
        research, said = desk_jobs._research_extra(root, ident)
        if not extra['sources'] and not research:
            raise ValueError(NO_SOURCES)
        payload = {**_payload(draft, extra), **research}
        guidance = manuscript_editor.CHECKS['factual-support'] + ' ' + FACTS + '\n\n'
        guidance += _reference('modules', 'blog-fact-check.md') + '\n\n'
        guidance += _reference('review', 'evidence.md') + '\n\n' + shared + said
        guidance += '\nThe sources are in sources, with their names and stance.\n' + FACTS_JSON
    elif tool == 'headline':
        payload = _payload(draft, extra)
        guidance = HEADLINE + '\n\n' + _reference('headline-lab.md') + '\n\n' + shared
        guidance += '\n' + HEADLINE_JSON
    else:
        payload = _payload(draft, extra)
        guidance = FEEDBACK + '\n\n' + blog_runner.STAGES['review'][2] + ' '
        guidance += manuscript_editor.CHECKS['shape'] + '\n\n' + _reference('review', 'shape.md')
        guidance += '\n\n' + shared + '\n' + FEEDBACK_JSON
    return kinds[tool], payload, guidance, meta


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _names(text):
    """Capitalised words that are not the first word of a sentence: likely names."""
    found = set()
    for match in NAME.finditer(text):
        before = text[: match.start()].rstrip()
        if before and before[-1] not in '.!?:"“(' and len(match.group()) > 1:
            found.add(match.group())
    return found


def changes_facts(before, after):
    """What a rewrite changes that it should keep: numbers, links, quotes or names."""
    from text_checks import preserve

    changed = list(preserve(before, after)['changes'])
    if _names(before) - _names(after) - {'I'}:
        changed.append('names')
    if not changed:
        return ''
    words = {'numbers': 'a number', 'links': 'a link', 'quotes': 'a quotation', 'names': 'a name'}
    return 'Check the facts: this changes ' + ' and '.join(words[key] for key in changed) + '.'


def _located(draft, part, before):
    """`before` as it occurs once in its part, or None."""
    try:
        text = desk.text_of(draft, part)
    except ValueError:
        return None
    before = before.strip() if isinstance(before, str) else ''
    if not before or text.count(before) != 1:
        return None
    return before


def _prose_parts(draft):
    return {'opening'} | {s['id'] for s in draft['sections']}


def _read_humanize(draft, found):
    rows = found.get('suggestions') if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    items, dropped, seen = [], 0, set()
    for row in rows[:60]:
        row = row if isinstance(row, dict) else {}
        part, after = row.get('part'), row.get('after')
        before = _located(draft, part, row.get('before')) if part in _prose_parts(draft) else None
        if (
            before is None
            or not isinstance(after, str)
            or not after.strip()
            or after.strip() == before
            or desk.has_heading(after)
            or (part, before) in seen
        ):
            dropped += 1
            continue
        seen.add((part, before))
        after = after.strip()
        items.append(
            {
                'part': part,
                'before': before,
                'after': after,
                'note': _text(row.get('why'), 500),
                'flag': changes_facts(before, after),
            }
        )
    return items, dropped, {}


def _read_facts(draft, found):
    rows = found.get('claims') if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    items, dropped = [], 0
    for row in rows[:60]:
        row = row if isinstance(row, dict) else {}
        part, verdict = row.get('part'), VERDICTS.get(row.get('verdict'))
        before = _located(draft, part, row.get('before')) if part in _prose_parts(draft) else None
        if before is None or verdict is None:
            dropped += 1
            continue
        item = {
            'part': part,
            'before': before,
            'verdict': verdict,
            'passage': _text(row.get('passage'), 2000),
            'source': _text(row.get('source'), 300),
            'note': _text(row.get('why'), 500),
        }
        after = _text(row.get('after'), desk.LIMIT)
        if verdict != 'supported' and after and after != before and not desk.has_heading(after):
            item['after'] = after
            item['flag'] = ''
        items.append(item)
    order = {'contradicted': 0, 'not-in-sources': 1, 'supported': 2}
    items.sort(key=lambda item: order[item['verdict']])
    return items, dropped, {}


def _read_headline(draft, found):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    titles, openings = found.get('titles') or [], found.get('openings') or []
    if not isinstance(titles, list) or not isinstance(openings, list) or not titles + openings:
        raise ValueError(UNREADABLE)
    items, dropped = [], 0
    for part, rows, limit in (('title', titles[:5], 500), ('opening', openings[:3], 20_000)):
        for row in rows:
            row = row if isinstance(row, dict) else {}
            text = row.get('text')
            text = text.strip() if isinstance(text, str) else ''
            if part == 'title':
                text = text.lstrip('#').strip()
            if (
                not text
                or len(text) > limit
                or (part == 'title' and '\n' in text)
                or (part == 'opening' and desk.has_heading(text))
                or text == draft[part]
            ):
                dropped += 1
                continue
            items.append(
                {
                    'part': part,
                    'before': draft[part],
                    'after': text,
                    'note': _text(row.get('why'), 500),
                    'flag': '',
                    'whole': True,
                    'group': part,
                }
            )
    return items, dropped, {}


def _read_feedback(draft, found):
    rows = found.get('comments') if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    parts = _prose_parts(draft) | {'title'}
    items = []
    for row in rows[:40]:
        row = row if isinstance(row, dict) else {}
        comment = _text(row.get('comment'), 2000)
        if not comment:
            continue
        part = row.get('part') if row.get('part') in parts else 'whole'
        quote = _located(draft, part, row.get('quote')) if part != 'whole' else None
        aspect = row.get('aspect') if row.get('aspect') in ASPECTS else 'shape'
        items.append({'part': part, 'quote': quote or '', 'aspect': aspect, 'comment': comment})
    summary = _text(found.get('summary'), 2000)
    if not items and not summary:
        raise ValueError(UNREADABLE)
    return items, 0, {'summary': summary}


READERS = {
    'finish-humanize': _read_humanize,
    'finish-facts': _read_facts,
    'finish-headline': _read_headline,
    'finish-feedback': _read_feedback,
}


def settle(root, ident, draft, job):
    """Read a finishing tool's result strictly and keep its proposals for the person. The
    draft is not changed; a result Blog Studio cannot read is refused readably."""
    import json

    content = ((job.get('result') or {}).get('content') or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', content, re.S)
    try:
        found = json.loads(fenced.group(1) if fenced else content)
    except ValueError:
        raise ValueError(UNREADABLE) from None
    items, dropped, extra = READERS[job['kind']](draft, found)
    meta = (job.get('metadata') or {}).get('desk') or {}
    if meta.get('level'):
        extra['level'] = meta['level']
    return keep(root, ident, job['id'], job['kind'], items, dropped=dropped, **extra)
