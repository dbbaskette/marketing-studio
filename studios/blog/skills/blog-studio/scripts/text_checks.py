#!/usr/bin/env python3
"""Mechanical text diagnostics; advisory, never an authorship verdict."""

import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys


URL = r'https?://[^\s<>\)]+'
PROTECTED = (
    r'(?ms)^\s*```[^\n]*\n.*?^\s*```[^\n]*(?:\n|$)',
    r'(?ms)^\s*~~~[^\n]*\n.*?^\s*~~~[^\n]*(?:\n|$)',
    r'`[^`\n]+`',
    URL,
    r'(?m)^\s*>[^\n]*',
    r'"[^"\n]+"',
    r'“[^”\n]+”',
)
# The carried-over check reads at most this many examples, this much of each.
EXAMPLE_LIMIT, EXAMPLE_CHARS, SHINGLE = 60, 200_000, 8
# A number followed by one of these is a count in a sentence, not a figure with a unit.
FUNCTION_WORDS = frozenset(
    'a an and are as at be but by can for from had has have if in into is it its no not of on '
    'or our so than that the their then there these they this those to was we were which who '
    'will with you your'.split()
)
# Two capitalised words with one of these are a heading or a phrase, not a name.
COMMON_WORDS = frozenset(
    'a about after all also an and any are as at be before but by each every first for from '
    'getting go how in into is it last learn more most new next no not note of on one or other '
    'our over part read results section see some started step steps such summary than that the '
    'their then there these they this those three to two under use used using what when where '
    'which who why will with your'.split()
)


def mask_protected(text, patterns=PROTECTED):
    clean = text
    for pattern in patterns:
        clean = re.sub(
            pattern, lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group()), clean
        )
    return clean


def lint(text, rules):
    clean = mask_protected(text)
    findings = []
    restrictions = [('em-dash', r'[—–]')] if rules.get('no_em_dashes') else []
    if rules.get('no_ascii_double_hyphen'):
        restrictions.append(('double-hyphen', r'--'))
    for term in rules.get('banished_words', []) + rules.get('banished_phrases', []):
        if term.strip():
            restrictions.append(('banished:' + term, r'(?<!\w)' + re.escape(term) + r'(?!\w)'))
    for key, pattern in restrictions:
        for hit in re.finditer(pattern, clean, re.IGNORECASE):
            findings.append(
                {
                    'rule': key,
                    'start': hit.start(),
                    'end': hit.end(),
                    'line': text.count('\n', 0, hit.start()) + 1,
                    'target': text[hit.start() : hit.end()],
                    'kind': 'mechanical',
                }
            )
    paragraphs = [
        m
        for m in re.finditer(r'(?m)(?:[^\n]+(?:\n(?!\s*\n)[^\n]+)*)', clean)
        if len(m.group().split()) >= 12
    ]
    for index, para in enumerate(paragraphs):
        normalized = ' '.join(para.group().lower().split())
        for prev in paragraphs[:index]:
            if (
                SequenceMatcher(None, normalized, ' '.join(prev.group().lower().split())).ratio()
                >= 0.9
            ):
                findings.append(
                    {
                        'rule': 'duplicate-paragraph',
                        'start': para.start(),
                        'end': para.end(),
                        'target': text[para.start() : para.end()],
                        'earlier_start': prev.start(),
                        'kind': 'advisory',
                    }
                )
                break
    sections = re.split(r'(?m)^##\s+[^\n]+\n', clean)[1:]
    openers = []
    for section in sections:
        paragraph = section.strip().split('\n\n')[0]
        opener = ' '.join(paragraph.lower().split()[:8])
        if len(opener.split()) >= 6:
            if opener in openers:
                findings.append({'rule': 'echoed-opener', 'target': opener, 'kind': 'advisory'})
            openers.append(opener)
    return {
        'findings': findings,
        'limitations': 'Mechanical rule matches and repetition hints only; read for meaning and voice. Protected code, URLs, and quotations are excluded.',
    }


def _words(text):
    """Each word with where it is, casefolded, for runs of words shared between texts."""
    return [(m.start(), m.end(), m.group().casefold()) for m in re.finditer(r'[^\W_]+', text)]


def _paragraphs(text):
    """The words of each paragraph, with where they are: a run of words never crosses a
    blank line or a heading, since shared headings are the shape an example is for."""
    prose = re.sub(r'(?m)^\s*#[^\n]*', lambda m: ' ' * len(m.group()), text)
    return [
        [(para.start() + a, para.start() + b, word) for a, b, word in _words(para.group())]
        for para in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', prose)
    ]


def _figure_or_name(clean, match):
    """Whether a matched number or two-word name is worth comparing: a figure with a real
    unit, or a name mid-sentence off a heading line, with no common word in it."""
    unit, name = match.group('unit'), match.group('name')
    if unit is not None:
        return unit.casefold() not in FUNCTION_WORDS
    if name is None:
        return True
    if any(word.casefold() in COMMON_WORDS for word in name.split()):
        return False
    before = clean[: match.start(1)]
    line = before.rsplit('\n', 1)[-1]
    if line.lstrip().startswith('#'):
        return False  # A shared section heading is the shape an example is for.
    return bool(before.rstrip()) and before.rstrip()[-1] not in '.!?:' and not before.endswith('\n')


def carried_over(text, examples, allowed):
    """Passages in `text` that come from one of `examples` ({name, text}) and from none of
    the `allowed` texts: runs of eight words, numbers with a unit or a percent, URLs and
    capitalised two-word names. Advisory: it flags, never rewrites, and reading for meaning
    is still the person's. Code and blockquotes in `text` are left alone; a quotation is
    not, since a quotation copied from an example is exactly what this finds."""
    text = text[:EXAMPLE_CHARS]
    code = tuple(p for p in PROTECTED if '"' not in p and '“' not in p)
    clean = mask_protected(text, code)
    linkable = mask_protected(text, tuple(p for p in code if p != URL))
    permitted = '\n'.join(str(value or '') for value in allowed).casefold()
    words, groups, runs = [], [], {}
    for number, group in enumerate(_paragraphs(clean)):
        base = len(words)
        words += group
        groups += [number] * len(group)
        for index in range(len(group) - SHINGLE + 1):
            runs.setdefault(
                tuple(word for _, _, word in group[index : index + SHINGLE]), []
            ).append(base + index)
    allowed_words = [word for _, _, word in _words(permitted)]
    permitted_runs = {
        run
        for index in range(len(allowed_words) - SHINGLE + 1)
        if (run := tuple(allowed_words[index : index + SHINGLE])) in runs
    }
    tokens = [
        (m.start(1), m.end(1))
        for m in re.finditer(
            r'(?=((?<!\w)\d[\d,]*(?:\.\d+)?(?:\s?%|\s?percent\b|\s+(?P<unit>[A-Za-z]{1,12})\b)|\b(?P<name>[A-Z][a-z]+ [A-Z][a-z]+)\b))',
            clean,
        )
        if _figure_or_name(clean, m)
    ] + [
        (m.start(), m.end() - len(m.group()) + len(m.group().rstrip('.,;:!?')))
        for m in re.finditer(URL, linkable)
    ]
    found = []
    for example in examples[:EXAMPLE_LIMIT]:
        body = str(example.get('text') or '')[:EXAMPLE_CHARS]
        if not body.strip():
            continue
        folded = body.casefold()
        hits = set()
        for group in _paragraphs(body):
            for index in range(len(group) - SHINGLE + 1):
                run = tuple(word for _, _, word in group[index : index + SHINGLE])
                if run in runs and run not in permitted_runs:
                    hits.update(runs[run])
        spans = []
        for index in sorted(hits):
            start, end = words[index][0], words[index + SHINGLE - 1][1]
            if (
                spans
                and index <= spans[-1][2] + SHINGLE - 1
                and groups[index] == groups[spans[-1][2]]
            ):
                spans[-1] = (spans[-1][0], end, index)
            else:
                spans.append((start, end, index))
        spans = [(start, end) for start, end, _ in spans]
        for start, end in tokens:
            token = ' '.join(text[start:end].split()).casefold()
            if token in folded and token not in permitted:
                spans.append((start, end))
        for start, end in spans:
            found.append(
                {
                    'rule': 'from-example',
                    'kind': 'advisory',
                    'start': start,
                    'end': end,
                    'line': text.count('\n', 0, start) + 1,
                    'target': text[start:end],
                    'example': str(example.get('name') or ''),
                }
            )
    findings, edge = [], -1
    for finding in sorted(found, key=lambda f: (f['start'], -f['end'])):
        if finding['start'] >= edge:
            findings.append(finding)
            edge = finding['end']
    return {
        'findings': findings,
        'limitations': 'Shared runs of eight words, numbers with a unit or a percent, URLs and '
        'capitalised two-word names only; a paraphrased fact from an example is not found. '
        'Code and quotations are excluded. Read for meaning.',
    }


# A source ID or an editorial placeholder is a note for the author, never reader-facing text:
# [source-…], [Editorial placeholder…], [Placeholder…], [TODO…] and [TBD…], in any case, closed
# or left open at the end of a line. Bracketed text that is a Markdown link's own text, as in
# [source-available](https://…) or [source-code][1], is the reader's and is left alone; two
# notes side by side, [source-1][source-2], are two notes.
NOTE_START = r'(?:source-|editorial placeholder|placeholder\b|todo\b|tbd\b)'
READER_FACING_NOTE = re.compile(
    r'\[' + NOTE_START + r'[^\]\n]{0,300}+(?:\](?!\(|\[(?!' + NOTE_START + r'))|(?!\]))',
    re.I,
)


def reader_facing_notes(text):
    """Each source ID or editorial placeholder left in writing a reader reads."""
    return [
        {
            'rule': 'reader-facing-note',
            'target': hit.group(),
            'start': hit.start(),
            'line': text.count('\n', 0, hit.start()) + 1,
        }
        for hit in READER_FACING_NOTE.finditer(text)
    ]


def facts(text):
    return {
        'numbers': sorted(Counter(re.findall(r'\b\d[\d,]*(?:\.\d+)?(?:%|\b)', text)).items()),
        'links': sorted(Counter(re.findall(r'https?://[^\s<>\)]+', text)).items()),
        'quotes': sorted(Counter(re.findall(r'"([^"\n]+)"|“([^”\n]+)”', text)).items()),
    }


def preserve(before, after):
    original, revised = facts(before), facts(after)
    changes = {
        key: {'before': original[key], 'after': revised[key]}
        for key in original
        if original[key] != revised[key]
    }
    return {
        'needs_review': bool(changes),
        'changes': changes,
        'limitations': 'Token comparison is a warning only; unchanged tokens do not prove unchanged meaning, names, causality, or qualifiers.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    check = sub.add_parser('lint')
    check.add_argument('--file', required=True)
    check.add_argument('--rules-file')
    compare = sub.add_parser('preserve')
    compare.add_argument('--before', required=True)
    compare.add_argument('--after', required=True)
    count = sub.add_parser('count')
    count.add_argument('--file', required=True)
    args = p.parse_args()
    try:
        if args.action == 'preserve':
            result = preserve(Path(args.before).read_text(), Path(args.after).read_text())
        else:
            text = Path(args.file).read_text()
            if args.action == 'count':
                result = {'words': len(text.split()), 'characters': len(text)}
            else:
                rules = json.loads(Path(args.rules_file).read_text()) if args.rules_file else {}
                result = lint(text, rules)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, TypeError) as exc:
        print(f'Blog Studio text check: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
