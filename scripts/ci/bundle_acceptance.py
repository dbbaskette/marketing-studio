#!/usr/bin/env python3
"""Exercise a real platform download without system Python, Node, npm, or providers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def run(command, env, **kwargs):
    done = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=300, **kwargs)
    if done.returncode:
        raise RuntimeError('Command failed: ' + str(command) + '\n' + done.stdout[-2000:] + done.stderr[-2000:])
    return done.stdout


def check(archive):
    with tempfile.TemporaryDirectory(prefix='marketing-bundle-acceptance-') as temporary:
        root = Path(temporary).resolve()
        home = root / 'home'
        home.mkdir()
        env = {'HOME': str(home), 'USERPROFILE': str(home), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
               'TMPDIR': str(root), 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
               'STUDIOS_CONFIG': str(home / '.config/studios-config.json'),
               'CODEX_HOME': str(home / '.codex'), 'CLAUDE_CONFIG_DIR': str(home / '.claude')}
        # Stub provisioning/assistant commands fail if setup attempts to use them.
        deny = root / 'deny'
        deny.mkdir()
        for name in ('npm', 'brew', 'apt-get', 'dnf', 'curl', 'codex', 'claude', 'gcloud', 'gemini'):
            path = deny / name
            path.write_text('#!/bin/sh\necho "Unexpected install/provider command" >&2\nexit 99\n')
            path.chmod(0o755)
        env['PATH'] = str(deny) + ':' + env['PATH']
        unpacked = root / 'download'
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                path = Path(entry.filename)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe release archive')
                source.extract(entry, unpacked)
                (unpacked / entry.filename).chmod((entry.external_attr >> 16) & 0o777)
        source = next(unpacked.iterdir())
        install = source / 'installer/install.sh'
        run(['/bin/bash', str(install), '--yes', '--prerequisites', 'check', '--target', 'codex'], env)
        distribution = json.loads((source / 'distribution.json').read_text())
        shutil.rmtree(unpacked)
        data = home / '.local/share/marketing-studio'
        current = (data / 'current').resolve()
        python = current / 'runtime/python/bin/python3'
        node = current / 'runtime/node/bin/node'
        report = json.loads(run([str(home / '.local/bin/marketing-studio'), 'status', '--json'], env))
        assert all(studio['installed'] for studio in report['studios']), report
        for identifier in ('blog', 'presentation', 'training'):
            helper = home / '.local/share' / (identifier + '-studio') / identifier
            run(['/bin/sh', str(helper), '--help'], env)
            assert 'runtime/node/bin' in helper.read_text(), helper
        skills = home / '.agents/skills'
        for name in ('harness-research', 'harness-slides'):
            runtime = skills / name
            assert runtime.is_dir(), runtime
            if name == 'harness-research':
                result = run([str(node), '-e', 'console.log(JSON.parse(require("node:fs").readFileSync(process.argv[1])).version)', str(runtime / 'package.json')], env)
            else:
                result = run([str(node), str(runtime / 'scripts' / (name + '.mjs')), 'version'], env)
            assert distribution['companions'][name]['version'] in result, result
        # Exercise the shipped Research CLI contract without launching a worker.
        research = (skills / 'harness-research').resolve()
        project = root / 'synthetic-research'
        project.mkdir()
        plan = root / 'research-plan.json'
        plan.write_text(json.dumps({'topic': 'Synthetic offline contract', 'purpose': 'planning',
            'scope': 'supplied-only', 'sources': [], 'items': [{'id': 'availability',
            'question': 'What do the selected documents establish?', 'public_query': None, 'claim': None}]}))
        planned = json.loads(run([str(node), str(research / 'scripts/harness-research.mjs'),
            'plan', '--project', str(project), '--file', str(plan)], env))
        status = json.loads(run([str(node), str(research / 'scripts/harness-research.mjs'),
            'status', '--project', str(project)], env))
        assert planned['run'] == status['run'] and status['scope'] == 'supplied-only'
        assert status['pending'] == ['availability'] and status['completed'] == 0
        slides = (skills / 'harness-slides').resolve()
        output = root / 'synthetic.pptx'
        program = '''import PptxGenJS from './node_modules/pptxgenjs/dist/pptxgen.cjs.js';
import fontkit from './node_modules/fontkit/dist/main.cjs';
const p=new PptxGenJS();p.addSlide().addText('Offline bundle check',{x:1,y:1,w:5,h:1});
await p.writeFile({fileName:process.argv[1]});'''
        run([str(node), '--input-type=module', '-e', program, str(output)], env, cwd=slides)
        assert output.stat().st_size > 1000
        run([str(python), '-c', 'import ssl,sqlite3,ctypes; print("Private standard library ready")'], env)
        print(json.dumps({'result': 'PASS', 'archive': archive.name,
                          'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                          'platform': distribution['platform'], 'private_python': distribution['runtimes']['python']['version'],
                          'private_node': distribution['runtimes']['node']['version'],
                          'studios': 3, 'providers_called': False, 'download_removed': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    check(parser.parse_args().archive.resolve())
