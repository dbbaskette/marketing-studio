#!/usr/bin/env python3
"""Mechanical text diagnostics; advisory, never an authorship verdict."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys


def mask_protected(text):
    patterns = [r'(?ms)^\s*```[^\n]*\n.*?^\s*```[^\n]*(?:\n|$)',
                r'(?ms)^\s*~~~[^\n]*\n.*?^\s*~~~[^\n]*(?:\n|$)',
                r'`[^`\n]+`', r'https?://[^\s<>\)]+', r'(?m)^\s*>[^\n]*',
                r'"[^"\n]+"', r'“[^”\n]+”']
    clean = text
    for pattern in patterns:
        clean = re.sub(pattern, lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group()), clean)
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
            findings.append({'rule': key, 'start': hit.start(), 'end': hit.end(),
                             'line': text.count('\n', 0, hit.start()) + 1, 'target': text[hit.start():hit.end()],
                             'kind': 'mechanical'})
    paragraphs = [m for m in re.finditer(r'(?m)(?:[^\n]+(?:\n(?!\s*\n)[^\n]+)*)', clean)
                  if len(m.group().split()) >= 12]
    for index, para in enumerate(paragraphs):
        normalized = ' '.join(para.group().lower().split())
        for prev in paragraphs[:index]:
            if SequenceMatcher(None, normalized, ' '.join(prev.group().lower().split())).ratio() >= .9:
                findings.append({'rule': 'duplicate-paragraph', 'start': para.start(), 'end': para.end(),
                                 'target': text[para.start():para.end()], 'earlier_start': prev.start(),
                                 'kind': 'advisory'})
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
    return {'findings': findings, 'limitations': 'Mechanical rule matches and repetition hints only; read for meaning and voice. Protected code, URLs, and quotations are excluded.'}


def facts(text):
    return {'numbers': sorted(Counter(re.findall(r'\b\d[\d,]*(?:\.\d+)?(?:%|\b)', text)).items()),
            'links': sorted(Counter(re.findall(r'https?://[^\s<>\)]+', text)).items()),
            'quotes': sorted(Counter(re.findall(r'"([^"\n]+)"|“([^”\n]+)”', text)).items())}


def preserve(before, after):
    original, revised = facts(before), facts(after)
    changes = {key: {'before': original[key], 'after': revised[key]} for key in original if original[key] != revised[key]}
    return {'needs_review': bool(changes), 'changes': changes,
            'limitations': 'Token comparison is a warning only; unchanged tokens do not prove unchanged meaning, names, causality, or qualifiers.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    check = sub.add_parser('lint');check.add_argument('--file', required=True);check.add_argument('--rules-file')
    compare = sub.add_parser('preserve');compare.add_argument('--before', required=True);compare.add_argument('--after', required=True)
    count = sub.add_parser('count');count.add_argument('--file', required=True)
    args = p.parse_args()
    try:
        if args.action == 'preserve':
            result = preserve(Path(args.before).read_text(), Path(args.after).read_text())
        else:
            text = Path(args.file).read_text()
            if args.action == 'count': result = {'words': len(text.split()), 'characters': len(text)}
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
