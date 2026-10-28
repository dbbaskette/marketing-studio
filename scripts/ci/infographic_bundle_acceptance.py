#!/usr/bin/env python3
"""Source-independent Infographic Studio platform journey, with no provider or provisioning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def check(archive):
    with tempfile.TemporaryDirectory(prefix='infographic-platform-acceptance-') as temp:
        root = Path(temp).resolve(); home = root / 'home'; home.mkdir()
        env = {'HOME': str(home), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'TMPDIR': str(root),
               'STUDIOS_CONFIG': str(root / 'shared.json'), 'INFOGRAPHIC_STUDIO_DATA': str(home / '.local/share/infographic-studio'),
               'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
               'CODEX_HOME': str(home / '.codex'), 'CLAUDE_CONFIG_DIR': str(home / '.claude')}
        deny = root / 'deny'; deny.mkdir()
        for name in ('npm', 'brew', 'apt-get', 'curl', 'codex', 'claude', 'gcloud', 'gemini'):
            file = deny / name; file.write_text('#!/bin/sh\nexit 99\n'); file.chmod(0o755)
        env['PATH'] = str(deny) + ':' + env['PATH']
        def run(command):
            done = subprocess.run([str(p) for p in command], env=env, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=180)
            if done.returncode: raise RuntimeError(done.stderr[-2000:] + done.stdout[-2000:])
            return json.loads(done.stdout)
        unpacked = root / 'download'
        with zipfile.ZipFile(archive) as zipped:
            for item in zipped.infolist():
                path = Path(item.filename)
                if path.is_absolute() or '..' in path.parts: raise ValueError('Unsafe package path.')
                zipped.extract(item, unpacked); (unpacked / item.filename).chmod((item.external_attr >> 16) & 0o777)
        source = next(unpacked.iterdir())
        distribution = json.loads((source / 'distribution.json').read_text())
        manifest = json.loads((source / 'bundle-manifest.json').read_text())
        assert manifest['studios'] == ['infographic'] and distribution['companions'] == {}
        run(['/bin/bash', source / 'installer/install.sh', '--yes', '--prerequisites', 'check', '--target', 'codex', '--studios', 'infographic', '--json'])
        suite = (home / '.local/share/marketing-studio/current').resolve()
        native = (home / '.local/share/infographic-studio/current').resolve()
        python = suite / 'runtime/python/bin/python3'
        helper = home / '.local/share/infographic-studio/infographic'
        shutil.rmtree(unpacked)
        cli = lambda *args: run(['/bin/sh', helper, *args])
        assert not cli('status')['configured']
        assert cli('preferences')['renderer'].startswith(str(native / 'renderer'))
        assert not (home / '.agents/skills/harness-research').exists()
        assert not (home / '.agents/skills/harness-slides').exists()
        workspace = root / 'workspace'; cli('setup', '--workspace', workspace)
        p = cli('create', 'Synthetic rolling restart', '--preset', 'digital', '--direction', 'direct')
        ident = p['id']; text = 'One instance restarts while the others serve.'
        sourcefile = root / 'source.txt'; sourcefile.write_text(text)
        p = cli('source', ident, '--file', sourcefile, '--expected-revision', p['revision'])
        def data(name, value):
            file = root / (name + '.json'); file.write_text(json.dumps(value)); return file
        fact = {'id': 'f1', 'statement': text, 'value': text, 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': p['sources'][0]['id'], 'start': 0, 'end': len(text), 'quote': text}]}
        p = cli('facts', ident, '--file', data('facts', [fact]), '--expected-revision', p['revision'])
        contract = {'schema': 1, 'revision': 'synthetic-v1', 'identity': {'id': 'fixture', 'name': 'Synthetic brand'},
                    'design': {'fontFamily': 'Arial', 'colors': {'canvasPrimary': '#FFFFFF', 'inkPrimary': '#18212B', 'headingPrimary': '#215B85'}}}
        p = cli('brand', ident, '--file', data('brand', contract), '--expected-revision', p['revision'])
        story = {'id': 's1', 'headline': 'Keep serving', 'takeaway': 'Restart one instance at a time.',
                 'rationale': 'Explain the supplied relationship.', 'qualifications': [], 'omissions': [],
                 'blocks': [{'id': 'b1', 'kind': 'concept', 'title': 'One at a time', 'text': 'Others continue serving.',
                             'fact_ids': ['f1'], 'required_ids': [], 'illustration': False, 'illustration_role': ''}]}
        p = cli('stories', ident, '--file', data('stories', [story]), '--expected-revision', p['revision'])
        p = cli('select', ident, '--story-id', 's1', '--expected-revision', p['revision'])
        p = cli('layout', ident, '--expected-revision', p['revision'])
        delivery = cli('preview', ident, '--expected-revision', p['revision'])
        cli('review', ident, '--export-id', delivery['id'], '--observation', 'Synthetic offline fixture inspected by its test owner.', '--expected-revision', p['revision'])
        p = cli('check', ident, '--expected-revision', p['revision'])
        p = cli('approve', ident, '--expected-revision', p['revision'])
        delivery = cli('export', ident, '--expected-revision', p['revision'])
        assert not delivery['draft'] and len(delivery['files']) == 4
        for item in delivery['files']:
            file = workspace / 'projects' / ident / item['file']
            assert hashlib.sha256(file.read_bytes()).hexdigest() == item['sha256']
        # Marketing Studio removal leaves the independently runnable native copy,
        # renderer and private interpreter retained in immutable version storage.
        run([python, suite / 'installer/install.py', 'uninstall', '--home', home, '--yes', '--json'])
        assert cli('status')['configured']
        assert cli('inspect', ident)['project']['approval'] is not None
        assert Path(cli('preferences')['renderer']).is_file()
        assert not any(p.is_symlink() for p in native.rglob('*'))
        document_intake = tuple(int(v) for v in (native / 'VERSION').read_text().strip().split('.')) >= (0, 2, 0)
        if document_intake:
            supplied = root / 'synthetic.docx'
            with zipfile.ZipFile(supplied, 'w') as zipped:
                zipped.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Selected Word material.</w:t></w:r></w:p></w:body></w:document>')
            preview = cli('source-preview', '--file', supplied)
            assert preview['readable'] and preview['excerpt'].strip() == 'Selected Word material.'
            imported = cli('source-import', ident, '--capture-id', preview['id'], '--expected-revision', p['revision'])
            assert imported['approval'] is None
            source = next(s for s in imported['sources'] if s['kind'] == 'docx')
            assert cli('source-show', ident, '--source-id', source['id'])['text'].strip() == 'Selected Word material.'
            refused = subprocess.run(['/bin/sh', str(helper), 'remote-preview', '--kind', 'google-doc',
                '--url', 'https://invalid.example/document'],
                env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            assert refused.returncode == 2 and 'Google' in json.loads(refused.stderr)['error']

        print(json.dumps({'result': 'PASS', 'archive': archive.name,
                          'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'platform': distribution['platform'],
                          'python': distribution['runtimes']['python']['version'],
                          'renderer': distribution['infographic_renderer']['version'], 'formats': 4,
                          'source_and_download_removed': True, 'marketing_studio_removed': True,
                          'research_slide_companions': 0, 'document_intake': document_intake, 'providers_called': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('archive', type=Path)
    check(parser.parse_args().archive.resolve())
