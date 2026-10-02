#!/usr/bin/env python3
"""Build a checked, self-contained installer bundle; never install it globally."""
from pathlib import Path
import hashlib
import json
import zipfile

repo = Path(__file__).resolve().parents[1]
bootstrap = repo / 'bootstrap/blog-studio'
for name in ('studio.py', 'text_checks.py', 'linkedin_import.py', 'hub.py', 'hub_store.py', 'hub_workspace.py', 'google_workflow.py'):
    (bootstrap / 'scripts' / name).write_bytes((repo / 'skills/blog-studio/scripts' / name).read_bytes())
files = {p.relative_to(bootstrap).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(bootstrap.rglob('*')) if p.is_file() and
         p.name not in ('install-manifest.json', 'config.json') and
         '__pycache__' not in p.parts and p.suffix != '.pyc'}
manifest = {'schema': 1, 'version': '1.2.0', 'files': files}
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
    for name in ('installation.md', 'troubleshooting.md', 'team-hub.md', 'i4-m4-m5-validation.md', 'google-docs.md'):
        path = repo / 'docs' / name
        if path.exists():
            archive.write(path, 'blog-studio-setup/docs/' + name)
output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
print(output)
