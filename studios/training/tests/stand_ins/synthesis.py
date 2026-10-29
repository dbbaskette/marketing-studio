"""Disposable Harness Research synthesis protocol, with no providers or network.

The same command body runs through Research._json and the author's Node preflight.
It validates synthetic captures/review identities and exports digest-pinned files;
research quality is supplied by the scripted author and independent checker.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

OWNER = 'harness-research-synthesis'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode())


def inside(root, name):
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts or not path.is_file():
        raise ValueError('Source must be a captured file inside the case.')
    return path


def command(args):
    if args == ['--version']:
        return 'harness-research 1.0.1'
    if args[:1] != ['synthesis']:
        raise ValueError('This fixture implements synthesis commands only.')
    action = args[1]
    options = dict(zip(args[2::2], args[3::2]))
    root = Path(options['--project'])
    state_file = root / '.harness-research/synthesis.json'
    if action == 'save':
        value = json.loads(inside(root, options['--file']).read_text())
        worker = options['--worker']
        if value.get('schema') != 2 or any(not isinstance(value.get(key), list)
                for key in ('sources', 'facts', 'findings', 'sections', 'brief')):
            raise ValueError('A schema-2 dossier requires sources, facts, findings, sections and brief arrays.')
        sources = {s['id']: s for s in value['sources']}
        if not sources or not value['facts'] or not value['findings'] or not value['brief']:
            raise ValueError('The synthetic dossier needs evidence, findings and a brief.')
        for fact in value['facts']:
            if fact.get('author') != worker:
                raise ValueError('Every fact must identify the author invocation.')
            if not fact.get('citations'):
                raise ValueError('Facts require captured evidence.')
            for citation in fact['citations']:
                source = sources[citation['source']]
                if not citation.get('quote') or citation['quote'] not in inside(root, source['file']).read_text():
                    raise ValueError('Evidence must quote the captured source exactly.')
        stamp = digest(json.dumps(value, sort_keys=True).encode())
        pending = dict(verdict='pending', note='')
        originals = []
        for source in value['sources']:
            source['sha256'] = digest(inside(root, source['file']).read_bytes())
            item = dict(source=source['id'], sha256=source['sha256'], read_original=False)
            if source.get('original_file'):
                source['original_sha256'] = digest(inside(root, source['original_file']).read_bytes())
                item['original_sha256'] = source['original_sha256']
            originals.append(item)
        prose = [f"{s['id']}:{i}" for s in value['sections'] for i, _ in enumerate(s['blocks'])]
        prose += [f"brief:{s['id']}:{i}" for s in value['brief'] for i, _ in enumerate(s['blocks'])]
        template = dict(schema=2, digest=stamp, originals=originals,
            facts=[dict(id=f['id'], **pending) for f in value['facts']],
            findings=[dict(id=f['id'], **pending) for f in value['findings']],
            prose=[dict(id=p, **pending) for p in prose],
            assessment=dict(coverage='pending', usefulness='pending', note=''))
        state = dict(owner=OWNER, schema=2, digest=stamp, status='draft', dossier=value,
                     author=worker, review=None, review_template=template)
    else:
        if not state_file.exists():
            return dict(status='not-started')
        state = json.loads(state_file.read_text())
        if action == 'review':
            value = json.loads(inside(root, options['--file']).read_text())
            if options['--worker'] == state['author']:
                raise ValueError('Review requires a separate worker.')
            template = state['review_template']
            if value.get('digest') != state['digest'] or any(
                    [i.get('id', i.get('source')) for i in value.get(group, [])] !=
                    [i.get('id', i.get('source')) for i in template[group]]
                    for group in ('originals', 'facts', 'findings', 'prose')):
                raise ValueError('Review must cover this exact dossier.')
            accepted = (all(i.get('read_original') for i in value['originals']) and
                        all(i.get('verdict') == 'supported' for group in ('facts', 'findings', 'prose') for i in value[group]) and
                        value.get('assessment', {}).get('coverage') == 'accurate' and
                        value.get('assessment', {}).get('usefulness') == 'adequate')
            state['review'] = dict(value, worker=options['--worker'], accepted=accepted)
            state['status'] = 'complete' if accepted else 'needs-revision'
        elif action in ('status', 'verify'):
            manifest = json.loads((root / 'research/output.json').read_text())
            intact = all(digest(inside(root / 'research', e['file']).read_bytes()) == e['sha256']
                         for e in manifest['artifacts'])
            intact = intact and all(digest(inside(root, s[key]).read_bytes()) == s[hash_key]
                for s in state['dossier']['sources'] for key, hash_key in
                (('file', 'sha256'), ('original_file', 'original_sha256')) if s.get(key))
            return dict(status=state['status'] if intact else 'stale',
                        artifact_integrity='passed' if intact else 'failed',
                        review_template=state['review_template'])
        else:
            raise ValueError('Unknown synthesis command.')
    export(root, state)
    write(root, '.harness-research/synthesis.json', json.dumps(state))
    return dict(status=state['status'], review_template=state['review_template'])


def export(root, state):
    facts = dict(copy.deepcopy(state['dossier']), owner=OWNER, digest=state['digest'],
                 status=state['status'], review=state['review'])
    names = ['facts.json', 'report.md', 'brief.md', 'evidence.md']
    for source in facts['sources']:
        for key, snapshot in (('file', 'snapshot'), ('original_file', 'original_snapshot')):
            if source.get(key):
                # Published captures are shared bundle evidence, distinct from the
                # deliberately local-only working sources/ tree.
                name = 'captures/' + source['id'] + '-' + key
                write(root / 'research', name, inside(root, source[key]).read_bytes())
                source[snapshot] = 'research/' + name
                names.append(name)
    def prose(sections):
        return '\n'.join('# ' + s['title'] + '\n' + '\n'.join(b['text'] for b in s['blocks']) for s in sections) + '\n'
    write(root, 'research/report.md', prose(facts['sections']))
    write(root, 'research/brief.md', prose(facts['brief']))
    write(root, 'research/evidence.md', '\n'.join(f['statement'] for f in facts['facts']))
    write(root, 'research/facts.json', json.dumps(facts))
    manifest = {k: facts[k] for k in ('owner', 'schema', 'digest', 'status')}
    manifest['artifacts'] = [dict(file=n, sha256=digest((root / 'research' / n).read_bytes())) for n in sorted(set(names))]
    write(root, 'research/output.json', json.dumps(manifest))


if __name__ == '__main__':
    try:
        result = command(sys.argv[1:])
        print(result if isinstance(result, str) else json.dumps(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
