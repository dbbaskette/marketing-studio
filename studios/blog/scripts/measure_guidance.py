#!/usr/bin/env python3
"""Measure the guidance a model reads and keep it within the recorded budgets.

    python3 scripts/measure_guidance.py            # record the current sizes in the inventory
    python3 scripts/measure_guidance.py --check    # fail if an estimate grew past the margin

The inventory records a character-based token estimate for the entry, for each
route and for the whole library. --check measures the tree again and compares
those estimates with the recorded ones: each may be up to 5% or 50 tokens larger,
whichever is more. Rewording therefore passes. Growth past the margin fails until
the text is shortened or the new sizes are recorded on purpose by running this
script without --check.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'skills/blog-studio'
INVENTORY = REPO / 'docs/estimates/blog-studio-token-inventory.json'
ROUTE_GROUPS = (
    'routes',
    'team_hub_routes',
    'workspace_operations',
    'craft_guides',
    'editorial_operations',
    'google_operations',
    'house_style_operations',
)
MARGIN_PERCENT = 5
MARGIN_TOKENS = 50  # A sentence or two, so a small file is not held to a handful of words.


def measure(path):
    content = path.read_text(encoding='utf-8')
    return {
        'characters': len(content),
        'estimated_tokens': (len(content) + 3) // 4,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def refreshed(inventory):
    result = json.loads(json.dumps(inventory))
    result['files'] = {
        p.relative_to(ROOT).as_posix(): measure(p)
        for p in sorted(ROOT.rglob('*'))
        if p.is_file() and p.suffix in ('.md', '.txt', '.j2')
    }
    result['library_tokens'] = sum(f['estimated_tokens'] for f in result['files'].values())
    for group in ROUTE_GROUPS:
        for route in result.get(group, {}).values():
            route['estimated_tokens'] = sum(
                result['files'][p]['estimated_tokens'] for p in dict.fromkeys(route['files'])
            )
    privacy = result['conditional_privacy_reference']
    privacy['estimated_tokens'] = sum(
        result['files'][p]['estimated_tokens'] for p in dict.fromkeys(privacy['files'])
    )
    # The installed skill has one entry file; the separate bootstrap entry is gone.
    result.pop('bootstrap', None)
    entry_files = ['SKILL.md', 'references/entry-flows.md']
    result['entry_guidance'] = {
        'files': entry_files,
        'estimated_tokens': sum(result['files'][p]['estimated_tokens'] for p in entry_files),
        'target_tokens': [800, 1200],
        'note': 'Entry file plus entry flow. Conditional reads are additional.',
    }
    return result


def budgets(inventory):
    """Every estimate the inventory records, as {label: tokens}."""
    found = {'library': inventory['library_tokens']}
    for single in ('entry_guidance', 'conditional_privacy_reference'):
        if single in inventory:
            found[single] = inventory[single]['estimated_tokens']
    for group in ROUTE_GROUPS:
        for name, route in inventory.get(group, {}).items():
            found[group + '.' + name] = route['estimated_tokens']
    return found


def over_budget(recorded, measured):
    """One line for each estimate that grew past the margin since the inventory was recorded."""
    now = budgets(measured)
    problems = []
    for label, was in budgets(recorded).items():
        limit = was + max(MARGIN_TOKENS, was * MARGIN_PERCENT // 100)
        if now.get(label, 0) > limit:
            problems.append(f'{label}: {now[label]} tokens now, {was} recorded, limit {limit}')
    return problems


def missing_files(inventory):
    """Listed guidance files that no longer exist, as 'group.route: path'."""
    listed = {'conditional_privacy_reference': inventory['conditional_privacy_reference']}
    for group in ROUTE_GROUPS:
        for name, route in inventory.get(group, {}).items():
            listed[group + '.' + name] = route
    return [
        label + ': ' + path
        for label, route in listed.items()
        for path in dict.fromkeys(route['files'])
        if not (ROOT / path).is_file()
    ]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Compare with the recorded inventory instead of rewriting it.',
    )
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    recorded_in = INVENTORY.relative_to(REPO).as_posix()
    missing = missing_files(inventory)
    if missing:
        print('These routes list guidance files that no longer exist:', file=sys.stderr)
        print(*('  ' + line for line in missing), sep='\n', file=sys.stderr)
        print('Correct their file lists in ' + recorded_in + '.', file=sys.stderr)
        return 1
    result = refreshed(inventory)
    if args.check:
        problems = over_budget(inventory, result)
        if problems:
            print(
                f'Guidance grew more than {MARGIN_PERCENT}% or {MARGIN_TOKENS} tokens '
                f'(whichever is larger) past the sizes recorded in {recorded_in}:',
                file=sys.stderr,
            )
            print(*('  ' + line for line in problems), sep='\n', file=sys.stderr)
            print(
                'Shorten the guidance, or record the new sizes on purpose: '
                'python3 scripts/measure_guidance.py',
                file=sys.stderr,
            )
            return 1
    else:
        INVENTORY.write_text(json.dumps(result, indent=2) + '\n')
    print(
        json.dumps(
            {
                'library_tokens': result['library_tokens'],
                'library_files': len(result['files']),
                'entry_tokens': result['entry_guidance']['estimated_tokens'],
                'workspace_tokens': {
                    key: value['estimated_tokens']
                    for key, value in result.get('workspace_operations', {}).items()
                },
                'craft_tokens': {
                    key: value['estimated_tokens']
                    for key, value in result.get('craft_guides', {}).items()
                },
                'editorial_tokens': {
                    key: value['estimated_tokens']
                    for key, value in result.get('editorial_operations', {}).items()
                },
                'google_tokens': {
                    key: value['estimated_tokens']
                    for key, value in result.get('google_operations', {}).items()
                },
                'house_style_tokens': {
                    key: value['estimated_tokens']
                    for key, value in result.get('house_style_operations', {}).items()
                },
                'route_tokens': {
                    key: value['estimated_tokens'] for key, value in result['routes'].items()
                },
            }
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
