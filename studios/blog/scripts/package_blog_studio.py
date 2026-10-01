#!/usr/bin/env python3
"""Create a portable skill archive with source-integrity validation."""
from pathlib import Path
import hashlib
import subprocess
import sys
import zipfile

repo=Path(__file__).resolve().parents[1]
root=repo/'skills/blog-studio'
subprocess.run([sys.executable,str(root/'scripts/validate_package.py')],check=True)
output=repo/'dist/blog-studio.zip'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            archive.write(path,'blog-studio/'+path.relative_to(root).as_posix())
output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(output)
