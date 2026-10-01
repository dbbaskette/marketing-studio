#!/usr/bin/env python3
"""Validate the portable source library without network or upstream execution."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'blog', 'blog-write', 'content-strategy', 'copywriting', 'copy-editing'}


def validate(root=ROOT):
    root = Path(root).resolve()
    errors = []
    try:
        manifest = json.loads((root / 'sources.lock.json').read_text())
    except (OSError, ValueError) as exc:
        return [f'Cannot read source manifest: {exc}']

    def local(path):
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            errors.append(f'Path escapes package: {path}')
            return None
        if not target.is_file():
            errors.append(f'Missing file: {path}')
            return None
        return target

    modules = manifest.get('modules', [])
    if len(modules) != 5 or {m.get('id') for m in modules} != EXPECTED:
        errors.append('Module registry must contain exactly the five shortlisted skills')
    active = [p.relative_to(root).as_posix() for p in root.rglob('SKILL.md')]
    if active != ['SKILL.md']:
        errors.append(f'Expected one active entry point; found {active}')
    paths = set()
    upstream_sources = set()
    source_ids = {s['id'] for s in manifest.get('sources', [])}
    for source in manifest.get('sources', []):
        if not re.fullmatch(r'[0-9a-f]{40}', source.get('commit', '')):
            errors.append(f'Unpinned source: {source.get("id")}')
        local(source['license_path'])
    for record in manifest.get('files', []):
        path = record['path']
        if path in paths:
            errors.append(f'Duplicate source file: {path}')
        paths.add(path)
        if record.get('source') not in source_ids:
            errors.append(f'Unknown repository for {path}')
        target = local(path)
        if target and hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
            errors.append(f'Source checksum mismatch: {path}')
        if record['upstream_path'].endswith('/SKILL.md'):
            upstream_sources.add(path)
    actual = {p.relative_to(root).as_posix() for p in (root / 'references/upstream').rglob('*') if p.is_file()}
    if actual != paths:
        errors.append(f'Source inventory differs: missing={sorted(paths-actual)}, unrecorded={sorted(actual-paths)}')
    if upstream_sources != {m['source_document'] for m in modules}:
        errors.append('Each collected skill must have exactly one registered source document')
    authored = [root / 'SKILL.md', root / 'references/package-notes.md']
    entry = (root / 'SKILL.md').read_text() if (root / 'SKILL.md').is_file() else ''
    for module in modules:
        wrapper = local(module['entrypoint'])
        local(module['source_document'])
        if module['entrypoint'] not in entry:
            errors.append(f'Module not discoverable from entry point: {module["id"]}')
        if wrapper:
            authored.append(wrapper)
            links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', wrapper.read_text())
            if not any((wrapper.parent / urlsplit(link).path).resolve() == (root / module['source_document']).resolve() for link in links):
                errors.append(f'Wrapper does not link to source: {module["id"]}')
    for document in authored:
        if not document.is_file():
            errors.append(f'Missing authored document: {document}')
            continue
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', document.read_text()):
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (document.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                errors.append(f'Broken local link in {document.relative_to(root)}: {link}')
    return errors


if __name__ == '__main__':
    issues = validate()
    for issue in issues:
        print(f'ERROR: {issue}', file=sys.stderr)
    if issues:
        sys.exit(1)
    print('Package valid: 5 modules, pinned source hashes, licenses, and authored links verified.')
