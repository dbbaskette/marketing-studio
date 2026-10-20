"""Schema-2 Harness Research integration. The helper owns research semantics and exports.

Studios supply bounded, separate author/reviewer invocations. Existing schema-1
runs never enter this adapter. No provider, installation or shared setting is
changed here.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

OWNER = 'harness-research-synthesis'
# Where the Harness Research installer keeps `current` and versions/<version>-<digest>.
SHARED = (Path('Library/Application Support/Harness Research'), Path('.local/share/harness-research'))
CASE = Path('.studio-research')
ARTIFACTS = {'report.md', 'brief.md', 'evidence.md', 'facts.json'}
# Harness Research 1.0.1 and newer exit 1 for a needs-revision review and for stale
# evidence while still printing the result. Callers judge that result's status.
RESULTS = {('synthesis', 'review'), ('synthesis', 'verify'), ('synthesis', 'status')}


def answered(args, code, out):
    """True when a command that exited 1 still printed its JSON result."""
    if code != 1 or tuple(args[:2]) not in RESULTS:
        return False
    try:
        return isinstance(json.loads(out), dict)
    except (TypeError, ValueError):
        return False


def inside(root, name):
    if Path(root).is_symlink():
        raise ValueError('Research paths cannot traverse links.')
    root = Path(root).resolve()
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Research paths must remain inside their case folder.')
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Research paths cannot traverse links.')
    if root not in path.resolve().parents:
        raise ValueError('Research paths must remain inside their case folder.')
    return path


def write(root, name, value):
    path = inside(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending-' + secrets.token_hex(6))
    try:
        pending.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def snapshot(tool=None):
    """Select the installed capability once; an older helper retains the old adapter."""
    try:
        return capability(Path(tool.runtime) if tool else find_runtime())
    except (OSError, ValueError, AttributeError, KeyError):
        return None


def capability(runtime):
    """The schema, version and digest of the helper files a run depends on, or None for a
    helper without synthesis."""
    package = json.loads((runtime / 'package.json').read_text())
    if not (runtime / 'scripts/lib/synthesis-cli.mjs').is_file():
        return None
    relevant = sorted([runtime / 'package.json', *runtime.glob('scripts/**/*.mjs'),
                       *runtime.glob('references/*')])
    digest = hashlib.sha256()
    for path in relevant:
        if path.is_file():
            digest.update(str(path.relative_to(runtime)).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {'schema': 2, 'version': package['version'], 'digest': digest.hexdigest()}


def runtime_for(saved, runtime=None):
    """The helper with a run's saved capability: the current one, or a version the Harness
    Research installer retained in versions/<version>-<digest> after an update. None when
    neither is installed."""
    version = saved.get('version') if isinstance(saved, dict) else None
    if not isinstance(version, str) or not version:
        return None
    try:
        current = (Path(runtime) if runtime else find_runtime()).resolve()
    except (OSError, ValueError):
        current = None
    folders = [current.parent] if current and current.parent.name == 'versions' else []
    if not os.environ.get('HARNESS_RESEARCH_RUNTIME'):
        folders += [Path.home() / root / 'versions' for root in SHARED]
    candidates = [current] if current else []
    for folder in dict.fromkeys(folders):
        try:
            # A retained version is a real folder; a link could point anywhere.
            candidates += sorted(path for path in folder.iterdir()
                                 if path.name.startswith(version + '-')
                                 and not path.is_symlink() and path.is_dir())
        except OSError:
            continue
    for candidate in candidates:
        try:
            if capability(candidate) == saved:
                return candidate
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def matching(tool, saved):
    """`tool`, or a copy of it running the retained helper version `saved` describes. None
    when that version is no longer installed."""
    if not saved:
        return None
    if snapshot(tool) == saved:
        return tool
    runtime = runtime_for(saved, getattr(tool, 'runtime', None))
    if runtime is None:
        return None
    kept = copy.copy(tool)
    kept.runtime = runtime
    return kept


def find_runtime():
    override = os.environ.get('HARNESS_RESEARCH_RUNTIME')
    roots = [Path(override)] if override else [
        *(Path.home() / root / 'current' for root in SHARED),
        Path.home() / '.agents/skills/harness-research',
        Path.home() / '.claude/skills/harness-research',
    ]
    for root in roots:
        if (root / 'scripts/harness-research.mjs').is_file():
            return root.resolve()
    raise ValueError('Install the shared Harness Research 1.0 or newer before starting synthesis research.')


def read_bundle(root, complete=True):
    """Read-only consumer boundary: identity, every hash, review and exact digest."""
    root = Path(root)
    manifest = json.loads(inside(root, 'output.json').read_text())
    if manifest.get('owner') != OWNER or manifest.get('schema') != 2:
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
    if complete and (manifest.get('status') != 'complete' or not isinstance(review, dict)
                     or review.get('digest') != manifest.get('digest') or not review.get('accepted')):
        raise ValueError('Research is still a draft or needs independent review.')
    for source in facts.get('sources', []):
        for key in ('snapshot', 'original_snapshot'):
            if source.get(key):
                name = source[key]
                if not name.startswith('research/') or name[len('research/'):] not in names:
                    raise ValueError('The bundle is missing a pinned source capture.')
    return facts, manifest


def publish(case, destination):
    """Copy the helper's whole bundle, preserving relative evidence links."""
    output = Path(case) / 'research'
    facts, manifest = read_bundle(output)
    if any((Path(destination) / name).exists() for name in ARTIFACTS):
        if not (Path(destination) / 'output.json').is_file():
            raise ValueError('Existing research output has no owned manifest; preserve it.')
        read_bundle(destination, complete=False)
    for entry in manifest['artifacts']:
        write(destination, entry['file'], inside(output, entry['file']).read_bytes())
    write(destination, 'output.json', (output / 'output.json').read_bytes())
    read_bundle(destination)
    return facts, manifest


def adopt_case(source, root):
    """Explicit handoff of the helper's owned state and captures, never arbitrary files."""
    if any((Path(root) / '.harness-research' / name).exists()
           for name in ('research.json', 'research-run.json')):
        raise ValueError('Existing legacy research keeps its original workflow. Use a fresh project.')
    if Path(source).is_symlink():
        raise ValueError('Research paths cannot traverse links.')
    source = Path(source).resolve()
    facts, manifest = read_bundle(source / 'research')
    state_path = inside(source, '.harness-research/synthesis.json')
    state = json.loads(state_path.read_text())
    if state.get('owner') != OWNER or state.get('digest') != manifest['digest']:
        raise ValueError('Research state and bundle describe different revisions.')
    destination = inside(root, str(CASE))
    if source == destination:
        for capture in facts['sources']:
            for key, digest_key in (('file', 'sha256'), ('original_file', 'original_sha256')):
                if capture.get(key) and hashlib.sha256(inside(source, capture[key]).read_bytes()).hexdigest() != capture[digest_key]:
                    raise ValueError('A working research source changed. Review it again before handoff.')
    if source != destination:
        previous = inside(destination, '.harness-research/synthesis.json')
        if previous.is_file() and previous.read_bytes() != state_path.read_bytes():
            old = json.loads(previous.read_text())
            write(destination, '.harness-research/synthesis-history/import-' +
                  hashlib.sha256(previous.read_bytes()).hexdigest() + '.json', json.dumps(old))
        for capture in facts['sources']:
            for key, digest_key in (('file', 'sha256'), ('original_file', 'original_sha256')):
                if capture.get(key):
                    content = inside(source, capture[key]).read_bytes()
                    if hashlib.sha256(content).hexdigest() != capture[digest_key]:
                        raise ValueError('A working research source changed. Review it again before handoff.')
                    write(destination, capture[key], content)
        publish(source, destination / 'research')
        write(destination, '.harness-research/synthesis.json', state_path.read_bytes())
    publish(destination, Path(root) / 'research')
    return facts, manifest


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


class Workflow:
    def __init__(self, runtime=None, call=None):
        self.runtime = Path(runtime) if runtime else find_runtime()
        self.call = call

    def command(self, case, action, file=None, worker=None):
        args = ['synthesis', action, '--project', str(case)]
        if file:
            args += ['--file', file, '--worker', worker]
        if self.call:
            return self.call(*args)
        node = shutil.which('node')
        if not node:
            raise ValueError('Harness Research needs the bundled Node.js runtime.')
        result = subprocess.run([node, str(self.runtime / 'scripts/harness-research.mjs'), *args],
                                capture_output=True, text=True, timeout=120,
                                stdin=subprocess.DEVNULL)
        if result.returncode and not answered(args, result.returncode, result.stdout):
            raise ValueError((result.stderr.strip().splitlines() or ['Harness Research failed.'])[-1])
        return json.loads(result.stdout)

    def run(self, root, task, invoke, sources=()):
        """One authored dossier followed by a separate checker. Refusals keep the draft.

        invoke(phase, guidance, payload, sources, fetch) returns JSON text plus only
        sources captured by the studio's confined tools. Worker IDs originate here,
        so the author cannot choose its reviewer identity.
        """
        case = inside(root, str(CASE))
        case.mkdir(parents=True, exist_ok=True)
        for phase in ('author', 'review') * 3:
            if phase == 'author':
                worker = 'author-' + secrets.token_hex(12)
                guide = '\n\n'.join((self.runtime / 'references' / name).read_text()
                                      for name in ('investigate.md', 'synthesize.md', 'studio-handoff.md'))
                payload = {'task': task, 'worker': worker,
                           'return': 'A complete schema-2 dossier as JSON, including authored brief sections. '
                                     'Use only saved source file paths supplied by the tools. '
                                     'Set every fact author to this worker ID. Do not write finished studio content.'}
                previous = case / '.harness-research/synthesis.json'
                if previous.is_file():
                    state = json.loads(previous.read_text())
                    payload['previous_dossier'] = state.get('dossier')
                    payload['previous_review'] = state.get('review')
                result, captures = invoke(phase, guide, payload, sources, task['source_mode'] != 'selected')
                dossier = json.loads(result)
                # The caller owns intent and permissions. Generated prose cannot broaden them.
                for key in ('topic', 'audience', 'purpose', 'scope', 'source_mode'):
                    dossier[key] = task[key]
                if any(f.get('author') != worker for f in dossier.get('facts', [])):
                    raise ValueError('Research facts must identify their actual author invocation.')
                allowed = {s['file']: s for s in captures}
                for source in dossier.get('sources', []):
                    captured = allowed.get(source.get('file'))
                    if captured is None:
                        raise ValueError('Research cited a source that the studio did not capture.')
                    permission = captured.get('permission') or ('selected' if captured.get('offered', True) else 'public')
                    if source.get('permission') != permission:
                        raise ValueError('Research changed a source permission.')
                    if source.get('origin') != captured.get('origin', captured.get('url')):
                        raise ValueError('Research changed a captured source origin.')
                    if source.get('original_file') not in (None, captured.get('original')):
                        raise ValueError('Research named an original that the studio did not capture.')
                    for key, path_key in (('file', 'path'), ('original', 'original_path')):
                        name, path = captured.get(key), captured.get(path_key)
                        if name and path:
                            write(case, name, Path(path).read_bytes())
                    if captured.get('original') and permission == 'selected':
                        source['original_file'] = captured['original']
                write(case, 'dossier.json', json.dumps(dossier))
                status = self.command(case, 'save', 'dossier.json', worker)
                # Offer only the exact captures saved in this dossier to the checker.
                sources = [{'title': s['title'], 'origin': s['origin'], 'file': s['file'],
                            'text': inside(case, s['file']).read_text(),
                            'supplied': s['permission'] == 'selected', 'permission': s['permission'],
                            **({'original': s['original_file'],
                                'original_path': inside(case, s['original_file'])}
                               if s.get('original_file') else {})} for s in dossier['sources']]
            else:
                worker = 'reviewer-' + secrets.token_hex(12)
                guide = (self.runtime / 'references/review-synthesis.md').read_text()
                payload = {'task': task, 'worker': worker, 'dossier': dossier,
                           'review_template': status['review_template'],
                           'report': (case / 'research/report.md').read_text(),
                           'brief': (case / 'research/brief.md').read_text(),
                           'evidence': (case / 'research/evidence.md').read_text(),
                           'return': 'Independent review JSON for this exact digest. Inspect saved context and '
                                     'original sources. Record unavailable originals honestly. Never fabricate approval.'}
                result, _ = invoke(phase, guide, payload, sources, False)
                write(case, 'review.json', result)
                status = self.command(case, 'review', 'review.json', worker)
                if status.get('status') == 'complete':
                    break
        verified = self.command(case, 'verify')
        if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
            raise ValueError('Independent research review needs changes. The draft and review are saved for correction.')
        facts, manifest = read_bundle(case / 'research')
        return facts, manifest


def check_json(text, spec):
    problems = []
    try:
        value = json.loads(text)
        if not isinstance(value, dict) or value.get('schema') != 2:
            problems.append('Return a schema-2 JSON object.')
    except (TypeError, ValueError):
        problems.append('Return valid JSON, without Markdown fences.')
    return problems, [{'check': 'research.json', 'status': 'failed' if problems else 'passed',
                       'problems': problems}], [], text


def native(engine, root, run, task, sources, product):
    """Bridge the common workflow to each studio's existing confined worker transport."""
    from runner import worker_tools, documents, companion
    originals = {item['file']: item['original'] for item in documents.listed(root)
                 if item.get('file') and item.get('original')}
    sources = [{**source, **({'original': originals[source['file']],
                             'original_path': inside(root, originals[source['file']])}
                            if source.get('file') in originals else {})} for source in sources]
    if product == 'presentation':
        from runner.steps import Work
    else:
        from runner.pipeline import Work, Step
    from workspace import WorkspaceError
    # After an update the run keeps the helper version it started with, while it is retained.
    tool = matching(engine.research(), engine._load(root).get('research_contract'))
    if tool is None:
        raise WorkspaceError('This research run needs its saved Harness Research version. Restore it before continuing.')
    folders = []

    def invoke(phase, guidance, payload, offered, fetch):
        if run.stop.is_set() or not engine._may_go(root):
            raise companion.Stopped()
        name = 'research-' + phase
        doing = ('Investigating sources and writing the report' if phase == 'author'
                 else 'Independently checking the research and brief')
        work = Work(guidance + '\n\nUse only the studio tools; the parent runs helper commands. '
                    'Read list_inputs and sources; return the requested JSON using submit_artifact '
                    'under the name research-result. Keep public queries generic and nonconfidential.',
                    json.dumps(payload), 'research' if fetch else 'write',
                    {'inputs': {'research-task': json.dumps(payload)}, 'sources': offered,
                     'fetch': fetch, 'ask': False,
                     'artifacts': {'research-result': {'kind': 'research-json'}}}, 'research-result')
        if product == 'presentation':
            outcome, handed, started, folder = engine._job(root, run, name, doing, work, deck=False)
        else:
            step = Step(name, 'agent', doing, doing, 'research')
            outcome, handed, started, folder = engine._job(root, run, step, work)
        folders.append(folder)
        if outcome.reason == 'stopped':
            engine._stopped(root, name if product == 'presentation' else step, outcome, started)
            raise companion.Stopped()
        with engine.files:
            record = engine._load(root)
            accepted = handed['artifacts'].get('research-result')
            engine._tried(record, name, started, outcome.seconds,
                          'kept' if accepted and outcome.reason != 'stopped' else 'failed',
                          **engine._cost(outcome))
            engine._store(root, record)
            engine._commit(root, 'record independent research job: ' + phase)
        if not accepted or outcome.reason == 'stopped':
            raise WorkspaceError('Research did not finish its ' + phase + ' job. Saved work is kept.')
        return accepted['text'], handed['sources']

    try:
        return Workflow(tool.runtime, tool._json).run(root, task, invoke, sources)
    except ValueError as error:
        raise WorkspaceError(str(error)) from error
    finally:
        for folder in folders:
            shutil.rmtree(folder, ignore_errors=True)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Import a reviewed Harness Research case, preserving its evidence.')
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--project', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        _, manifest = adopt_case(args.case, args.project)
        print(json.dumps({'status': manifest['status'], 'digest': manifest['digest'], 'contract': snapshot(),
                          'report': str(args.project / 'research/report.md'),
                          'brief': str(args.project / 'research/brief.md')}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
