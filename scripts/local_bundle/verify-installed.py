#!/usr/bin/env python3
"""Check installed tools offline; all generated files use a disposable home."""
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=Path.home() / '.local/share/presentation-studio-local-bundle/installation.json')
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    has_slides = any(name in ('presentation', 'training') for name in record.get('studios', ['presentation']))
    suite, extra, brand = (Path(record[key]) for key in ('suite', 'tools', 'brand'))
    slides = Path.home() / 'Library/Application Support/Harness Slides/current'
    search = ':'.join([str(Path.home() / '.local/bin'), '/opt/homebrew/bin', '/usr/local/bin',
                       os.environ.get('PATH', '/usr/bin:/bin')])
    agent = record.get('assistant')
    candidates = (agent,) if agent in ('codex', 'claude') else ('codex', 'claude')
    assistant = next((path for name in candidates if (path := shutil.which(name, path=search))), None)
    if assistant is None:
        raise SystemExit('FAILED: existing Codex or Claude Code installation is not on PATH.')
    with tempfile.TemporaryDirectory(prefix='presentation-bundle-verify-') as temporary:
        home = Path(temporary)
        paths = [extra / 'bin', extra / 'tools/bin', suite / 'runtime/python/bin',
                 suite / 'runtime/node/bin', Path(assistant).parent]
        env = {'HOME': temporary, 'USERPROFILE': temporary, 'TMPDIR': temporary,
               'PATH': ':'.join(map(str, paths)) + ':/usr/bin:/bin',
               'CODEX_HOME': str(home / '.codex'), 'CLOUDSDK_CONFIG': str(home / 'gcloud'),
               'CLAUDE_CONFIG_DIR': str(home / '.claude'),
               'CLOUDSDK_CORE_DISABLE_USAGE_REPORTING': 'true', 'GIT_CONFIG_NOSYSTEM': '1',
               'GIT_CONFIG_GLOBAL': '/dev/null', 'XDG_CACHE_HOME': str(home / 'cache')}
        (home / '.codex').mkdir()

        def run(args):
            result = subprocess.run(list(map(str, args)), env=env, cwd=home,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=180)
            print(result.stdout, flush=True)
            if result.returncode:
                raise SystemExit('FAILED: ' + str(args[0]))

        for command in ([assistant, '--version'], ['gcloud', '--version'], ['git', '--version'],
                        ['pdfinfo', '-v'], ['node', brand / 'scripts/audit-brand.mjs', '--self']):
            run(command)
        if not has_slides:
            print('PASS: tools and brand. No provider calls were made.')
            return
        run(['node', slides / 'scripts/harness-slides.mjs', 'images', 'status', '--json'])
        javascript = (
            'const P=require(' + json.dumps(str(slides / 'node_modules/pptxgenjs')) + ');'
            'const p=new P();p.addSlide().addText("Presentation Studio offline verification",'
            '{x:1,y:1,w:8,h:1});await p.writeFile({fileName:"test.pptx"});'
        )
        run(['node', '--input-type=commonjs', '-e',
             '(async()=>{' + javascript + '})().catch(e=>{console.error(e);process.exit(1)})'])
        run(['soffice', '-env:UserInstallation=' + (home / 'office-profile').as_uri(),
             '--headless', '--convert-to', 'pdf', '--outdir', home, home / 'test.pptx'])
        run(['pdftoppm', '-png', '-singlefile', '-scale-to', '800', home / 'test.pdf', home / 'test-preview'])
        if not (home / 'test-preview.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
            raise SystemExit('FAILED: PNG preview signature')
        print('PASS: tools, skills, PowerPoint, PDF and PNG. No provider calls were made.')


if __name__ == '__main__':
    main()
