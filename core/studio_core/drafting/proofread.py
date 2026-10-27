"""The desk's in-process mechanical checks (Blog Studio's Quick check): no job, no writes.

Findings are advisory, never an authorship verdict. Each names its part, its rule, what to
do and the sentence Fix would rewrite. The rule lists are the studio's: Blog Studio passes
BlogForge's AI-tell words, phrases and sentence starters.
"""

import re

from .. import text_checks
from . import parts as _parts

COMMON_STARTS = frozenset({'the', 'a', 'an'})
PROOF_LIMIT = 300  # findings shown at once
BOUNDARY = re.compile(
    r'(?<=[.!?…])["”’)\]]*[ \t]+|\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d{1,3}[.)]|#|>)[ \t])'
)
WORD = re.compile(r'[^\W\d_]+(?:[’\'-][^\W\d_]+)*')
SENTENCE_MAX = 2000  # a passage Fix rewrites; a longer run is cut to its line
LIST_LINE = re.compile(r'[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]')
LIMITATIONS = (
    'Mechanical matches and repetition hints only; read for meaning. Code, '
    'links and quotations are left out.'
)


def sentences(text):
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


def sentence(text, start, spans=None):
    """The sentence holding `start`, as (its text, where it starts in the part)."""
    for begin, end in spans or sentences(text):
        if begin <= start < end:
            if end - begin > SENTENCE_MAX:
                line_start = text.rfind('\n', 0, start) + 1
                line_end = text.find('\n', start)
                begin, end = line_start, line_end if line_end != -1 else len(text)
                end = min(end, begin + SENTENCE_MAX)
            return text[begin:end], begin
    return text[start : start + 1], start


def offsets(draft):
    """Where each part sits in the Markdown `parts.join` makes, to place findings in it."""
    places, at = [], 0
    if draft.get('title'):
        places.append(('title', at + 2, draft['title']))
        at += 2 + len(draft['title']) + 2
    if draft.get('opening'):
        places.append(('opening', at, draft['opening']))
        at += len(draft['opening']) + 2
    mark = _parts.level(draft) + 1  # The heading's marks and its space, as join writes them.
    for section in draft['sections']:
        at += mark + len(section['heading'])
        if section['text']:
            places.append((section['id'], at + 2, section['text']))
            at += 2 + len(section['text'])
        at += 2
    return places


def label(rule, target):
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


def finding(part, text, rule, start, target, spans=None):
    found, at = sentence(text, start, spans)
    said, fix = label(rule, target)
    return {
        'part': part,
        'rule': rule,
        'label': said,
        'fix': fix,
        'target': target,
        'sentence': found,
        'start': at,
        'at': start,
    }


def mask_indented(text):
    """Indented code (four spaces or a tab after a blank line, outside a list) as spaces of
    the same length, so findings keep their places and code is never read as prose."""
    out, code, listed, blank = [], False, False, True
    for line in text.split('\n'):
        indented = line.startswith(('    ', '\t'))
        if not line.strip():
            out.append(line)
            blank = True
            continue
        if indented and (code or (blank and not listed)):
            code, blank = True, False
            out.append(' ' * len(line))
            continue
        code = False
        if LIST_LINE.match(line):
            listed = True
        elif not indented:
            listed = False
        out.append(line)
        blank = False
    return '\n'.join(out)


def clean(text):
    return text_checks.mask_protected(mask_indented(text))


def units(paragraph):
    """A paragraph, or each item of a list on its own: parallel items repeat by design."""
    starts = [m.start() for m in re.finditer(r'(?m)^' + LIST_LINE.pattern, paragraph)]
    if not starts:
        return [(0, paragraph)]
    cuts = ([0] if starts[0] else []) + starts + [len(paragraph)]
    return [(a, paragraph[a:b]) for a, b in zip(cuts, cuts[1:], strict=False)]


def repetition(part, text, starters):
    """Within one part: a listed sentence opener (`starters`), two sentences in a row with
    the same first word, and a long word three times in one paragraph."""
    masked = clean(text)
    spans = sentences(text)
    starters = {word.casefold() for word in starters}
    found, previous = [], None
    for begin, end in spans:
        first = WORD.search(masked, begin, end)
        word = first.group() if first and first.start() == begin else None
        if word and word.casefold() in starters:
            found.append(finding(part, text, 'ai-starter', begin, word, spans))
        elif (
            word
            and previous
            and word.casefold() == previous.casefold()
            and word.casefold() not in COMMON_STARTS
        ):
            found.append(finding(part, text, 'repeated-start', begin, word, spans))
        previous = word
    for paragraph in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', masked):
        for offset, unit in units(paragraph.group()):
            seen = {}
            for match in WORD.finditer(unit):
                word = match.group().casefold()
                if len(word) < 6:
                    continue
                seen[word] = seen.get(word, 0) + 1
                if seen[word] == 3:
                    start = paragraph.start() + offset + match.start()
                    found.append(finding(part, text, 'repeated-word', start, match.group(), spans))
    return found


def openers(draft):
    """Sections whose first eight words open the way an earlier section's do."""
    found, seen = [], {}
    for section in draft['sections']:
        paragraph = clean(section['text']).strip().split('\n\n')[0]
        opener = ' '.join(paragraph.lower().split()[:8])
        if len(opener.split()) >= 6:
            if opener in seen:
                found.append(finding(section['id'], section['text'], 'echoed-opener', 0, opener))
            seen[opener] = section['id']
    return found


def check(draft, rules, starters, ident, join=None, lint=None):
    """Mechanical findings for each part, in draft order, each with the sentence Fix would
    rewrite: `text_checks.lint` with `rules` over the joined text, then repetition with the
    listed `starters`, then echoed openers. `join` is the item's text as the page shows it
    (`parts.join` by default) and `lint` the lint to run. Reading only."""
    join = join or _parts.join
    lint = lint or text_checks.lint
    places = offsets(draft)
    findings = []
    for hit in lint(mask_indented(join(draft)), rules)['findings']:
        if 'start' not in hit:
            continue
        for part, offset, text in places:
            if offset <= hit['start'] < offset + len(text):
                local = hit['start'] - offset
                target = text[local : local + len(hit['target'])].split('\n')[0][:200]
                findings.append(finding(part, text, hit['rule'], local, target))
                break
    for part, _, text in places:
        findings += repetition(part, text, starters)
    findings += openers(draft)
    order = {part: number for number, (part, _, _) in enumerate(places)}
    findings.sort(key=lambda found: (order.get(found['part'], 0), found['at'], found['rule']))
    return {
        'id': ident,
        'revision': draft['revision'],
        'findings': findings[:PROOF_LIMIT],
        'more': max(0, len(findings) - PROOF_LIMIT),
        'limitations': LIMITATIONS,
    }
