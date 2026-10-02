#!/usr/bin/env python3
"""Check self-contained routing, provenance, and authored local links."""
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
NEW = {'blog-source-intake', 'blog-voice-profile', 'blog-author-interview', 'blog-argument-outline',
       'blog-voice-check', 'blog-humanize', 'blog-fact-check', 'blog-geo-review', 'blog-repurpose'}
GOOGLE = {'blog-google-' + name for name in ('source', 'handoff', 'return', 'review', 'template', 'export')}
OLD = {'blog', 'blog-write', 'content-strategy', 'copywriting', 'copy-editing'}


def validate(root=ROOT):
    root = Path(root).resolve()
    errors = []
    try:
        source = json.loads((root / 'sources.lock.json').read_text())
        blogforge = json.loads((root / 'blogforge.lock.json').read_text())
    except (OSError, ValueError) as exc:
        return [f'Cannot read provenance: {exc}']
    if {m.get('id') for m in source.get('modules', [])} != OLD or len(source['modules']) != 5:
        errors.append('Expected the five original source modules.')
    if {m.get('id') for m in source.get('capabilities', [])} != NEW or len(source['capabilities']) != 9:
        errors.append('Expected nine BlogForge-derived capabilities.')
    if sorted(p.relative_to(root).as_posix() for p in root.rglob('SKILL.md')) != ['SKILL.md']:
        errors.append('Expected exactly one discoverable skill entry point.')
    recorded = set()
    for item in source.get('files', []) + blogforge.get('files', []):
        path = root / item['path']
        if not path.resolve().is_relative_to(root):
            errors.append(f'Path outside package: {item["path"]}');continue
        recorded.add(item['path'])
        if not path.is_file(): errors.append(f'Missing source file: {item["path"]}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            errors.append(f'Source hash mismatch: {item["path"]}')
    actual = {p.relative_to(root).as_posix() for folder in ('references/upstream', 'references/blogforge')
              for p in (root / folder).rglob('*') if p.is_file()}
    if actual != recorded:
        errors.append('Bundled source inventory differs from provenance.')
    for repo in source['sources']:
        if not re.fullmatch('[0-9a-f]{40}', repo['commit']):errors.append('Unpinned upstream repository.')
        if not (root / repo['license_path']).is_file():errors.append('Missing upstream license.')
    if not re.fullmatch('[0-9a-f]{40}', blogforge['commit']):errors.append('Unpinned BlogForge provenance.')
    entry = (root / 'SKILL.md').read_text()
    for module in source['modules'] + source['capabilities']:
        if not (root / module['entrypoint']).is_file():errors.append(f'Missing module {module["id"]}')
        if module['entrypoint'] not in entry:errors.append(f'Unreachable module {module["id"]}')
    router = root / 'references/google/workflow.md'
    if not router.is_file() or 'references/google/workflow.md' not in entry:
        errors.append('Missing conditional Google router.')
    else:
        for module in GOOGLE:
            if not (root / 'references/modules' / (module + '.md')).is_file() or module not in router.read_text():
                errors.append(f'Unreachable Google module {module}')
    for p in [root / 'SKILL.md', *sorted((root / 'references').rglob('*.md'))]:
        relative = p.relative_to(root).as_posix()
        if relative.startswith(('references/upstream/', 'references/blogforge/')):continue
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text()):
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:continue
            target = (p.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():errors.append(f'Broken link in {relative}: {link}')
    for script in ('studio.py', 'text_checks.py', 'linkedin_import.py', 'hub.py', 'hub_store.py', 'hub_workspace.py', 'google_workflow.py'):
        p = root / 'scripts' / script
        if not p.is_file():errors.append(f'Missing helper {script}')
        else:
            try:compile(p.read_text(), str(p), 'exec')
            except SyntaxError as exc:errors.append(str(exc))
    return errors


if __name__ == '__main__':
    failures = validate()
    if failures:
        print('\n'.join(f'ERROR: {e}' for e in failures), file=sys.stderr)
        sys.exit(1)
    print('Blog Studio valid: 20 modules, source hashes, licenses, authored links, and helpers checked.')
