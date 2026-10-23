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
    if 'after' not in item:
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
        if 'after' not in item:
            raise ValueError('A comment changes nothing. Make it a note, or skip it.')
        if item['state'] != 'open':
            raise ValueError('This suggestion was already applied or skipped.')
        after = entry.get('after', item['after'])
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
