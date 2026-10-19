#!/usr/bin/env python3
"""Check installed tools offline; all generated files use a disposable home."""
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    base = Path.home() / '.local/share/presentation-studio-local-bundle'
    record = json.loads((base / 'installation.json').read_text())
    suite, extra, brand = (Path(record[key]) for key in ('suite', 'tools', 'brand'))
    slides = Path.home() / 'Library/Application Support/Harness Slides/current'
    with tempfile.TemporaryDirectory(prefix='presentation-bundle-verify-') as temporary:
        home = Path(temporary)
        paths = [extra / 'bin', extra / 'tools/bin', suite / 'runtime/python/bin', suite / 'runtime/node/bin']
        env = {'HOME': temporary, 'USERPROFILE': temporary, 'TMPDIR': temporary,
               'PATH': ':'.join(map(str, paths)) + ':/usr/bin:/bin',
               'CODEX_HOME': str(home / '.codex'), 'CLOUDSDK_CONFIG': str(home / 'gcloud'),
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

        for args in (['codex', '--version'], ['gcloud', '--version'], ['git', '--version'],
                     ['pdfinfo', '-v'], ['node', brand / 'scripts/audit-brand.mjs', '--self'],
                     ['node', slides / 'scripts/harness-slides.mjs', 'images', 'status', '--json']):
            run(args)
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
