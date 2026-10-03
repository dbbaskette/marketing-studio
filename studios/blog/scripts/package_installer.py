#!/usr/bin/env python3
"""Build a checked, self-contained installer bundle; never install it globally."""
from pathlib import Path
import hashlib
import json
import zipfile

repo = Path(__file__).resolve().parents[1]
bootstrap = repo / 'bootstrap/blog-studio'
for name in ('studio.py', 'performance.py', 'local_cache.py', 'local_reads.py', 'text_checks.py', 'linkedin_import.py', 'hub.py', 'hub_store.py', 'hub_workspace.py', 'google_workflow.py', 'experience.py', 'author_workflow.py', 'writing_defaults.py', 'hub_browse.py', 'google_drive.py', 'google_roundtrip.py', 'google_suggestions.py', 'google_review_comments.py'):
    (bootstrap / 'scripts' / name).write_bytes((repo / 'skills/blog-studio/scripts' / name).read_bytes())
for name in ('gcloud.md', 'checkpoints.md', 'roundtrip.md', 'status.md', 'suggestions.md'):
    destination = bootstrap / 'references/google' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((repo / 'skills/blog-studio/references/google' / name).read_bytes())
for name in ('short-commands.md', 'workspace/status.md', 'workspace/changes.md', 'workspace/defaults.md', 'workspace/performance.md'):
    destination = bootstrap / 'references' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((repo / 'skills/blog-studio/references' / name).read_bytes())
files = {p.relative_to(bootstrap).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(bootstrap.rglob('*')) if p.is_file() and
         p.name not in ('install-manifest.json', 'config.json') and
         '__pycache__' not in p.parts and p.suffix != '.pyc'}
manifest = {'schema': 1, 'version': '1.10.0', 'files': files}
(bootstrap / 'install-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
for path in bootstrap.rglob('*.py'):
    compile(path.read_text(), str(path), 'exec')
compile((repo / 'installer/install.py').read_text(), 'installer/install.py', 'exec')
output = repo / 'dist/blog-studio-installer.zip'
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for folder in ('bootstrap', 'installer'):
        for path in sorted((repo / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                archive.write(path, 'blog-studio-setup/' + path.relative_to(repo).as_posix())
    for name in ('installation.md', 'troubleshooting.md', 'team-hub.md', 'i4-m4-m5-validation.md', 'google-docs.md', 'new-user-guide.md', 'prompt-cheat-sheet.md', 'status-card.md', 'live-acceptance.md', 'usability-validation.md', 'team-hub-library-validation.md', 'google-roundtrip-validation.md', 'google-suggestions-validation.md'):
        path = repo / 'docs' / name
        if path.exists():
            archive.write(path, 'blog-studio-setup/docs/' + name)
output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
print(output)
