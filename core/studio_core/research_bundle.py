"""A research case and its reviewed bundle: reading, publishing, handing off and copying.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from studio_core.research_paths import inside, write


def _contract():
    """studio_core.research_contract, read when called. Callers and tests replace names on it
    (read_bundle, publish), and a call made from here reaches what they put there."""
    from studio_core import research_contract
    return research_contract


OWNER = 'harness-research-synthesis'
CASE = Path('.studio-research')
ARTIFACTS = {'report.md', 'brief.md', 'evidence.md', 'facts.json'}


def working_case(case):
    """Resolve only the host-owned, confined current topic pointer."""
    case = Path(case)
    pointer = case / 'current.json'
    if pointer.exists():
        if pointer.is_symlink():
            raise ValueError('Research location cannot be a link.')
        value = json.loads(pointer.read_text())
        if not re.fullmatch('[a-f0-9]{64}', str(value.get('basis', ''))):
            raise ValueError('The saved research location is invalid.')
        return inside(case, value['basis'] + '/topic')
    return case


def output_root(case):
    case = working_case(case)
    marker = case / '.harness-research/asset.json'
    if marker.is_file():
        if marker.is_symlink() or json.loads(marker.read_text()).get('owner') != 'harness-research-asset':
            raise ValueError('Unrecognized research topic asset.')
        return case
    return case / 'research'


def snapshot_name(name, manifest):
    """Return a manifest-relative capture path for either supported output layout."""
    names = {e['file'] for e in manifest['artifacts']}
    if name.startswith('research/') and name[len('research/'):] in names:
        return name[len('research/'):]
    if name.startswith('sources/revisions/') and name in names:
        return name
    raise ValueError('The bundle is missing a pinned source capture.')


def read_bundle(root, complete=True):
    """Read-only consumer boundary: identity, every hash, review and exact digest."""
    root = Path(root)
    manifest = json.loads(inside(root, 'output.json').read_text())
    from studio_core import research_decisions
    creator = manifest.get('owner') == research_decisions.OWNER
    if manifest.get('owner') not in (OWNER, research_decisions.OWNER) or manifest.get('schema') != 2:
        raise ValueError('This research bundle uses a different owner or format.')
    entries = manifest.get('artifacts')
    if not isinstance(entries, list):
        raise ValueError('The research bundle has no file manifest.')
    names = set()
    for entry in entries:
        name = entry['file']
        if name in names:
            raise ValueError('The research bundle repeats a file.')
        names.add(name)
        path = inside(root, name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Research evidence or output changed. Revise and review it again.')
    if not ARTIFACTS <= names:
        raise ValueError('The research bundle is incomplete.')
    facts = json.loads(inside(root, 'facts.json').read_text())
    if any(facts.get(key) != manifest.get(key) for key in ('owner', 'schema', 'digest', 'status')):
        raise ValueError('The research manifest and findings describe different revisions.')
    review = facts.get('review')
    if creator:
        if 'creator.json' not in names:
            raise ValueError('The creator decision receipt is missing.')
        research_decisions.validate(root, facts, manifest)
    if complete and not creator and (manifest.get('status') != 'complete' or not isinstance(review, dict)
                     or review.get('digest') != manifest.get('digest') or not review.get('accepted')):
        raise ValueError('Research is still a draft or needs independent review.')
    for source in facts.get('sources', []):
        for key in ('snapshot', 'original_snapshot'):
            if source.get(key):
                name = source[key]
                snapshot_name(name, manifest)
    return facts, manifest


def publish(case, destination):
    """Copy the helper's whole bundle, preserving relative evidence links."""
    output = output_root(case)
    facts, manifest = _contract().read_bundle(output)
    if any((Path(destination) / name).exists() for name in ARTIFACTS):
        if not (Path(destination) / 'output.json').is_file():
            raise ValueError('Existing research output has no owned manifest; preserve it.')
        _contract().read_bundle(destination, complete=False)
    for entry in manifest['artifacts']:
        write(destination, entry['file'], inside(output, entry['file']).read_bytes())
    write(destination, 'output.json', (output / 'output.json').read_bytes())
    _contract().read_bundle(destination)
    return facts, manifest


def case_files(source):
    """Declared portable helper files for both output layouts, never an arbitrary directory."""
    source = working_case(source)
    output = output_root(source)
    prefix = '' if output == source else 'research/'
    facts, manifest = _contract().read_bundle(output)
    state = json.loads(inside(source, '.harness-research/synthesis.json').read_text())
    if state.get('owner') != OWNER or state.get('digest') != manifest['digest']:
        raise ValueError('Research state and bundle describe different revisions.')
    names = {'.harness-research/synthesis.json', prefix + 'output.json'}
    names.update(prefix + entry['file'] for entry in manifest['artifacts'])
    # A review assembled from review units (Harness Research 1.6.0, #378) is checked against
    # its plan record and each unit's receipt wherever the case goes.
    units = (state.get('review') or {}).get('units') if state.get('schema') == 4 else None
    if isinstance(units, dict):
        if not isinstance(units.get('plan'), str) or not isinstance(units.get('receipts'), list):
            raise ValueError('The assembled research review cannot be read; preserve it for inspection.')
        names.add('.harness-research/review-units-data/plan-' + units['plan'] + '.json')
        names.update(receipt['file'] for receipt in units['receipts']
                     if isinstance(receipt, dict) and isinstance(receipt.get('file'), str))
    for capture in facts['sources']:
        for key, digest_key in (('file', 'sha256'), ('original_file', 'original_sha256')):
            if capture.get(key):
                try:
                    content = inside(source, capture[key]).read_bytes()
                except OSError as error:
                    raise ValueError('A working research source is missing. Restore it before handoff.') from error
                if hashlib.sha256(content).hexdigest() != capture[digest_key]:
                    raise ValueError('A working research source changed. Review it again before handoff.')
                names.add(capture[key])
    if not prefix:
        names.update({'.harness-research/asset.json', 'topic.json', 'sources.json', 'asset-manifest.json'})
        asset = json.loads(inside(source, '.harness-research/asset.json').read_text())
        if asset.get('owner') != 'harness-research-asset':
            raise ValueError('This research topic has no owned asset marker.')
        names.update(item['file'] for item in asset['intake']['files'] if item.get('file'))
        names.update(entry[key] for entry in asset['inventory'] for key in ('original_file', 'capture_file') if entry.get(key))
    collection = source / '.harness-research/collection.json'
    if collection.exists():
        names.add('.harness-research/collection.json')
        value = json.loads(inside(source, '.harness-research/collection.json').read_text())
        if value.get('owner') != 'harness-research-collection':
            raise ValueError('This research has no owned collection marker.')
        if value.get('registry'): names.add(value['registry']['file'])
        for stream in value['workstreams']:
            for attempt in stream['attempts']:
                if attempt.get('packet'): names.add(attempt['packet']['file'])
                for receipt in attempt.get('receipts', []):
                    names.update(receipt[key] for key in ('snapshot', 'original_snapshot') if receipt.get(key))
                    names.update(receipt['source'][key] for key in ('file', 'original_file') if receipt['source'].get(key))
    if len(names) > 1000:
        raise ValueError('This research handoff has too many declared files.')
    files = {name: inside(source, name).read_bytes() for name in sorted(names)}
    return source, files


def adopt_case(source, root):
    """Explicit handoff of declared reviewed state and captures, preserving private history."""
    if any((Path(root) / '.harness-research' / name).exists()
           for name in ('research.json', 'research-run.json')):
        raise ValueError('Existing legacy research keeps its original workflow. Use a fresh project.')
    source, files = case_files(source)
    base = inside(root, str(CASE))
    if (source / '.harness-research/asset.json').exists():
        basis = hashlib.sha256(files['output.json']).hexdigest()
        destination = inside(base, basis + '/topic')
        write(base, '.gitignore', '*\n')
        for name, raw in files.items(): write(destination, name, raw)
        write(base, 'current.json', json.dumps({'schema': 1, 'basis': basis}))
    else:
        destination = base
        for name, raw in files.items(): write(destination, name, raw)
    return _contract().publish(destination, Path(root) / 'research')


def copy_case(source, destination):
    """Copy local pending state after checking every path before traversing it."""
    source = Path(source)
    inside(Path(destination).parent, Path(destination).name)
    if source.is_symlink():
        raise ValueError('Research state cannot be a linked folder.')
    for directory, dirs, files in os.walk(source, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            relative = str(path.relative_to(source))
            inside(source, relative)
            inside(destination, relative)
            if not path.is_file() and not path.is_dir():
                raise ValueError('Research state must contain ordinary files and folders.')
    shutil.copytree(source, destination, dirs_exist_ok=True)
