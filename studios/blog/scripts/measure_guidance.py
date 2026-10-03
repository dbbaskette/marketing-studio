#!/usr/bin/env python3
"""Refresh the character-based guidance inventory and existing route estimates."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'skills/blog-studio'
INVENTORY = REPO / 'docs/estimates/blog-studio-token-inventory.json'


def measure(path):
    content = path.read_text(encoding='utf-8')
    return {'characters': len(content), 'estimated_tokens': (len(content) + 3) // 4,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def refreshed(inventory):
    result = json.loads(json.dumps(inventory))
    result['files'] = {p.relative_to(ROOT).as_posix(): measure(p)
                       for p in sorted(ROOT.rglob('*'))
                       if p.is_file() and p.suffix in ('.md', '.txt', '.j2')}
    result['library_tokens'] = sum(f['estimated_tokens'] for f in result['files'].values())
    for routes in (result['routes'], result['team_hub_routes'],
                   result.get('workspace_operations', {}), result.get('craft_guides', {}),
                   result.get('editorial_operations', {}), result.get('google_operations', {}), result.get('house_style_operations', {})):
        for route in routes.values():
            route['estimated_tokens'] = sum(result['files'][p]['estimated_tokens']
                                            for p in dict.fromkeys(route['files']))
    privacy = result['conditional_privacy_reference']
    privacy['estimated_tokens'] = sum(result['files'][p]['estimated_tokens']
                                      for p in dict.fromkeys(privacy['files']))
    bootstrap = measure(REPO / result['bootstrap']['path'])
    result['bootstrap'].update({key: bootstrap[key] for key in ('estimated_tokens', 'sha256')})
    entry_files = ['SKILL.md', 'references/entry-flows.md']
    result['entry_guidance'] = {
        'files': entry_files,
        'estimated_tokens': sum(result['files'][p]['estimated_tokens'] for p in entry_files),
        'target_tokens': [800, 1200],
        'note': 'Parent plus entry flow; bootstrap measured separately. Conditional reads are additional.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if the recorded inventory is stale.')
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    result = refreshed(inventory)
    if args.check:
        if result != inventory:
            print('Guidance inventory is stale; run scripts/measure_guidance.py.', file=sys.stderr)
            return 1
    else:
        INVENTORY.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'library_tokens': result['library_tokens'],
                      'library_files': len(result['files']),
                      'entry_tokens': result['entry_guidance']['estimated_tokens'],
                      'bootstrap_tokens': result['bootstrap']['estimated_tokens'],
                      'workspace_tokens': {key: value['estimated_tokens']
                                           for key, value in result.get('workspace_operations', {}).items()},
                      'craft_tokens': {key: value['estimated_tokens']
                                       for key, value in result.get('craft_guides', {}).items()},
                      'editorial_tokens': {key: value['estimated_tokens'] for key, value in result.get('editorial_operations', {}).items()},
                      'google_tokens': {key: value['estimated_tokens']
                                        for key, value in result.get('google_operations', {}).items()},
                      'house_style_tokens': {key: value['estimated_tokens']
                                             for key, value in result.get('house_style_operations', {}).items()},
                      'route_tokens': {key: value['estimated_tokens']
                                       for key, value in result['routes'].items()}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
