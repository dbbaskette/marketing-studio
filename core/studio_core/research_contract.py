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
import tempfile

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


# The task's own fields. The caller owns them, so generated prose cannot change them.
TASK_FIELDS = ('topic', 'audience', 'purpose', 'scope', 'source_mode')


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
        rounds = 0
        for phase in ('author', 'review') * ROUNDS:
            if phase == 'author':
                rounds += 1
                worker = 'author-' + secrets.token_hex(12)
                guide = '\n\n'.join((self.runtime / 'references' / name).read_text()
                                      for name in ('investigate.md', 'synthesize.md', 'studio-handoff.md'))
                payload = {'task': task, 'worker': worker,
                           'return': 'A complete schema-2 dossier as JSON, including authored brief sections. '
                                     'Use only saved source file paths supplied by the tools: copy each '
                                     "source's file and origin exactly from the capture the tools showed, "
                                     'and never invent paths such as research/sources/. '
                                     'Dossier format: sources, facts, findings, sections and brief are arrays; '
                                     'sections and brief hold {id, title, blocks: [{text, kind, refs}]}. '
                                     'Set every fact author to this worker ID. Do not write finished studio content.'}
                previous = case / '.harness-research/synthesis.json'
                if previous.is_file():
                    state = json.loads(previous.read_text())
                    payload['previous_dossier'] = state.get('dossier')
                    payload['previous_review'] = state.get('review')
                result, captures = invoke(phase, guide, payload, sources, task['source_mode'] != 'selected')
                dossier = json.loads(result)
                # The caller owns intent and permissions. Generated prose cannot broaden them.
                for key in TASK_FIELDS:
                    dossier[key] = task[key]
                if any(f.get('author') != worker for f in dossier.get('facts', [])):
                    raise ValueError('Research facts must identify their actual author invocation.')
                allowed = {s['file']: s for s in captures}
                for source in dossier.get('sources', []):
                    captured = allowed.get(source.get('file'))
                    if captured is None:
                        raise ValueError(f"Research cited {source.get('file')!r}, a source that the studio did not capture.")
                    permission = captured.get('permission') or ('selected' if captured.get('offered', True) else 'public')
                    if source.get('permission') != permission:
                        raise ValueError('Research changed a source permission.')
                    if source.get('origin') != captured.get('origin', captured.get('url')):
                        raise ValueError('Research changed a captured source origin.')
                    if captured.get('original') and source.get('original_file') not in (
                            None, captured['original']):
                        raise ValueError('Research named an original that the studio did not capture.')
                    for key, path_key in (('file', 'path'), ('original', 'original_path')):
                        name, path = captured.get(key), captured.get(path_key)
                        if name and path:
                            write(case, name, Path(path).read_bytes())
                    # The studio says which sources have an original of their own: one it
                    # did not offer, as a previous draft's may name, is not claimed.
                    if captured.get('original') and permission == 'selected':
                        source['original_file'] = captured['original']
                    else:
                        source.pop('original_file', None)
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
                # A check that could not read an original it must attest to refuses whatever
                # the author corrects: stop now, and do not count this round as a correction.
                try:
                    cause = unreadable_originals(json.loads(result), dossier)
                except (TypeError, ValueError):
                    cause = []
                if cause:
                    raise CheckCouldNotFinish(objections(case), rounds - 1, cause)
        verified = self.command(case, 'verify')
        if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
            raise ReviewRefused(objections(case), ROUNDS, grouped(case))
        facts, manifest = read_bundle(case / 'research')
        return facts, manifest


ROUNDS = 3


class ReviewRefused(ValueError):
    """The independent check still objected after every round of correction. The message
    says what it objected to; `objections` holds every objection for the studio's review,
    and `groups`, when given, the same objections counted by cause (see `grouped`)."""

    def __init__(self, objections, rounds, groups=None):
        self.objections = list(objections)
        self.rounds = rounds
        self.groups = list(groups or ())
        count = len(self.objections)
        said = ('The independent check of the research still needs changes after '
                f'{rounds} rounds of correction')
        if self.groups:
            total = sum(group['count'] for group in self.groups)
            said += (f': {total} objection' + ('' if total == 1 else 's')
                     + f' in {len(self.groups)} group' + ('' if len(self.groups) == 1 else 's')
                     + ': ' + ', '.join(f"{group['title']} ({group['note']})"
                                        for group in self.groups) + '.')
        elif count:
            said += f': {count} objection' + ('' if count == 1 else 's') + ', such as '
            said += ' '.join(shortened(note) for note in self.objections[:2])
        else:
            said += ', and did not say what: read the saved check.'
        super().__init__(said + ' The draft report and the check’s notes are saved for correction.')


class CheckCouldNotFinish(ReviewRefused):
    """The independent check could not read the original of a source it must attest to,
    and that is all it objected to. No correction can change that: it is the studio's
    problem, not the research's. `cause` holds each such source as {'source', 'title',
    'file', 'original', 'access_error'}; `rounds` counts only the rounds of correction
    before it, so this one is not counted."""

    def __init__(self, objections, rounds, cause):
        self.objections = list(objections)
        self.rounds = rounds
        self.cause = list(cause)
        first = self.cause[0] if self.cause else {}
        named = f'the original of "{first.get("title") or first.get("source") or "a source"}"'
        if first.get('access_error'):
            named += f' ({shortened(first["access_error"]).rstrip(".")}.)'
        more = len(self.cause) - 1
        if more:
            named += f' and of {more} more source' + ('' if more == 1 else 's')
        ValueError.__init__(self, (
            f'The research check could not read {named}. That is a studio problem, not a '
            'research problem: the report is not wrong, the check could not finish. Nothing '
            'to correct until the original is readable.'))


def unreadable_originals(review, dossier):
    """The sources a review says it could not read, when every verdict it did not support
    rests on one of them; else []. A verdict rests on the sources its fact cites, its
    finding's facts cite, or its passage's facts and findings cite. Each is {'source',
    'title', 'file', 'original', 'access_error'}."""
    if not isinstance(review, dict) or not isinstance(dossier, dict):
        return []
    unread = {item.get('source'): item.get('access_error') or 'it gave no reason'
              for item in review.get('originals') or ()
              if isinstance(item, dict) and item.get('read_original') is False}
    if not unread:
        return []
    cited = {fact.get('id'): {citation.get('source') for citation in fact.get('citations') or ()
                              if isinstance(citation, dict)}
             for fact in dossier.get('facts') or () if isinstance(fact, dict)}
    found = {finding.get('id'): set().union(*(cited.get(ident, set()) for ident in
                                            (finding.get('support') or []) + (finding.get('counter') or [])))
             for finding in dossier.get('findings') or () if isinstance(finding, dict)}
    rests = {**cited, **found}
    passages = {}
    for prefix, sections in (('', dossier.get('sections')), ('brief:', dossier.get('brief'))):
        for section in sections or ():
            for number, block in enumerate(section.get('blocks') or ()):
                passages[f"{prefix}{section.get('id')}:{number}"] = block.get('refs') or []
    for number, comparison in enumerate(dossier.get('comparisons') or ()):
        for row_number, row in enumerate(comparison.get('rows') or ()):
            for cell_number, cell in enumerate(row.get('cells') or ()):
                passages[f'comparison:{number}:{row_number}:{cell_number}'] = cell.get('refs') or []
    for group in ('facts', 'findings', 'prose'):
        for item in review.get(group) or ():
            if not isinstance(item, dict) or item.get('verdict') in (None, 'supported', 'pending'):
                continue
            ident = item.get('id')
            sources = (set().union(*(rests.get(ref, set()) for ref in passages.get(ident, ())))
                       if group == 'prose' else rests.get(ident, set()))
            if not sources & unread.keys():
                return []
    named = {source.get('id'): source for source in dossier.get('sources') or ()
             if isinstance(source, dict)}
    return [{'source': ident, 'title': (named.get(ident) or {}).get('title') or ident,
             'file': (named.get(ident) or {}).get('file'),
             'original': (named.get(ident) or {}).get('original_file'), 'access_error': said}
            for ident, said in unread.items()]


def shortened(note, limit=160):
    line = ' '.join(str(note).split())
    return line if len(line) <= limit else line[:limit - 1].rstrip() + '…'


def objections(case):
    """What the last saved review objected to, one sentence each: every verdict that is
    not supported, with its note, then an assessment that asks for revision."""
    path = case / 'review.json'
    try:
        review = json.loads(path.read_text()) if path.is_file() else {}
    except ValueError:
        return []
    if not isinstance(review, dict):
        return []
    found = []
    for group in ('facts', 'findings', 'prose'):
        for item in review.get(group) or ():
            if isinstance(item, dict) and item.get('verdict') not in (None, 'supported'):
                note = ' '.join(str(item.get('note') or '').split())
                found.append(f"{item.get('id')} ({item.get('verdict')}): {note or 'no note'}")
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict):
        asked = [name for name in ('coverage', 'usefulness') if assessment.get(name) == 'needs-revision']
        if asked:
            note = ' '.join(str(assessment.get('note') or '').split())
            found.append(' and '.join(asked).capitalize() + ' need' + ('s' if len(asked) == 1 else '')
                         + ' revision: ' + (note or 'no note'))
    return found[:40]


NOUNS = {'facts': ('fact', 'facts'), 'findings': ('finding', 'findings'),
         'prose': ('passage of the report or brief', 'passages of the report or brief')}


def grouped(case):
    """What the last saved review objected to, by cause: one group for each kind of item
    (facts, findings, passages) and verdict, then one for an assessment that asks for
    revision. Each group is {'title', 'count', 'note', 'items'}: 'title' such as "12 facts
    the check calls narrow", 'note' the first item's, and 'items' every one, as `objections`
    words them."""
    path = Path(case) / 'review.json'
    try:
        review = json.loads(path.read_text()) if path.is_file() else {}
    except ValueError:
        return []
    if not isinstance(review, dict):
        return []
    groups = []
    for kind in ('facts', 'findings', 'prose'):
        found = {}
        for item in review.get(kind) or ():
            if isinstance(item, dict) and item.get('verdict') not in (None, 'supported', 'pending'):
                note = ' '.join(str(item.get('note') or '').split()) or 'no note'
                found.setdefault(str(item['verdict']), []).append(f"{item.get('id')}: {note}")
        for verdict in sorted(found, key=lambda name: (name != 'unsupported', name)):
            items = found[verdict]
            noun = NOUNS[kind][len(items) != 1]
            said = 'unsupported' if verdict == 'unsupported' else f'the check calls {verdict}'
            groups.append({'title': f'{len(items)} {noun} {said}', 'count': len(items),
                           'note': shortened(items[0], 100), 'items': items})
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict):
        asked = [name for name in ('coverage', 'usefulness') if assessment.get(name) == 'needs-revision']
        if asked:
            note = ' '.join(str(assessment.get('note') or '').split()) or 'no note'
            groups.append({'title': ' and '.join(asked) + (' needs' if len(asked) == 1 else ' need')
                           + ' revision', 'count': 1, 'note': shortened(note, 100), 'items': [note]})
    return groups


def took(seconds, dollars):
    """What some work took, in words: "48 minutes and $9.80". Empty when nothing was
    recorded."""
    said = []
    seconds = round(seconds or 0)
    if seconds >= 90 * 60:
        hours, minutes = divmod(round(seconds / 60), 60)
        said.append(f"{hours} hour{'' if hours == 1 else 's'}"
                    + (f" {minutes} minute{'' if minutes == 1 else 's'}" if minutes else ''))
    elif seconds >= 60:
        minutes = round(seconds / 60)
        said.append(f"{minutes} minute{'' if minutes == 1 else 's'}")
    elif seconds >= 1:
        said.append(f"{seconds} second{'' if seconds == 1 else 's'}")
    if dollars is not None:
        said.append(f'${dollars:,.2f}')
    return ' and '.join(said)


def check_json(text, spec):
    problems = []
    try:
        value = json.loads(text)
        if not isinstance(value, dict) or value.get('schema') != 2:
            problems.append('Return a schema-2 JSON object.')
        elif 'captures' in spec and isinstance(value.get('sources'), list):
            problems += uncaptured(value['sources'], spec['captures'])
            if not problems and spec.get('runtime'):
                problems += refused(value, spec)
    except (TypeError, ValueError):
        problems.append('Return valid JSON, without Markdown fences.')
    return problems, [{'check': 'research.json', 'status': 'failed' if problems else 'passed',
                       'problems': problems}], [], text


def uncaptured(sources, captures):
    """Why sources a dossier cites differ from what its job saved. The parent refuses the same
    after the job; saying it while the author can still correct it keeps the research step."""
    saved = {entry['file']: entry for entry in captures if entry.get('file')}
    listed = ', '.join(sorted(saved)[:40]) or 'none yet'
    problems = []
    for source in sources:
        name = source.get('file') if isinstance(source, dict) else None
        entry = saved.get(name)
        if entry is None:
            problems.append(f'Source file {name!r} is not one this job saved. Save a page with '
                            'save_source first, then copy its "Capture file" exactly. Saved '
                            f'files: {listed}.')
            continue
        origin = entry.get('origin', entry.get('url'))
        if source.get('origin') != origin:
            problems.append(f'Source {name}: copy its origin exactly as {origin!r}.')
        permission = entry.get('permission') or ('selected' if entry.get('offered', True) else 'public')
        if source.get('permission') != permission:
            problems.append(f'Source {name}: its permission is {permission!r}.')
    return problems


def refused(value, spec):
    """What the pinned helper says of a dossier, saved in a disposable case with this job's own
    captures and the task's own fields, as the parent will save it after the job. The author
    can still correct it then; afterwards a refusal would end the whole research step."""
    dossier = {**copy.deepcopy(value), **(spec.get('task') or {})}
    worker = spec.get('worker')
    if any(not isinstance(fact, dict) or fact.get('author') != worker
           for fact in dossier.get('facts') or []):
        return [f'Set every fact author to {worker}.']
    folder = Path(spec['folder'])
    saved = {entry['file']: entry for entry in spec['captures'] if entry.get('file')}
    with tempfile.TemporaryDirectory(prefix='research-check-') as temp:
        case = Path(temp)
        for source in dossier['sources']:
            entry = saved[source['file']]
            for name, local in ((entry.get('file'), entry.get('local')),
                                (entry.get('original'), entry.get('original'))):
                if name and local and (folder / local).is_file():
                    write(case, name, (folder / local).read_bytes())
            permission = entry.get('permission') or ('selected' if entry.get('offered', True) else 'public')
            if entry.get('original') and permission == 'selected':
                source['original_file'] = entry['original']
            else:
                source.pop('original_file', None)
        write(case, 'dossier.json', json.dumps(dossier))
        try:
            done = subprocess.run(
                [spec.get('node') or 'node', str(Path(spec['runtime']) / 'scripts/harness-research.mjs'),
                 'synthesis', 'save', '--project', str(case), '--file', 'dossier.json',
                 '--worker', str(worker)],
                capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return []  # The parent saves it again after the job and reports any failure there.
    if done.returncode:
        said = (done.stderr.strip().splitlines() or ['it gave no reason.'])[-1]
        return [f'Harness Research refused this dossier: {said} Correct it and hand the whole '
                'dossier back.']
    return []


# The names research jobs were recorded under before they were named for their round.
LEGACY_JOBS = ('research-author', 'research-review')


def job_name(phase, number):
    """What one research job is recorded as: `research:author-2`, `research:review-2`."""
    return f'research:{phase}-{number}'


def job_round(name):
    """(phase, round) of a research job's name, or None for another step's. A job recorded
    before rounds were named has round None."""
    if name in LEGACY_JOBS:
        return name.partition('-')[2], None
    head, _, rest = str(name).partition(':')
    phase, _, number = rest.rpartition('-')
    if head == 'research' and phase in ('author', 'review') and number.isdigit():
        return phase, int(number)
    return None


def doing_words(phase, number):
    """What a research job is doing, as the page says it while the job runs."""
    of = f'round {number} of {ROUNDS}'
    if phase == 'author':
        return (f'Investigating sources and writing the report ({of})' if number == 1
                else f'Correcting the research after its independent check ({of})')
    return (f'Independently checking the research ({of})' if number == 1
            else f'Independently checking the corrected research ({of})')


def last_rounds(attempts_by_name):
    """What the last try at the research took: {'rounds', 'jobs', 'seconds', 'dollars'}
    from the recorded tries of its jobs, given as {name: [attempt, ...]}. The last try
    begins with its last first round; jobs recorded before rounds were named all count.
    None when no research job is recorded."""
    tried = [(job_round(name), attempt) for name, attempts in attempts_by_name.items()
             if job_round(name) for attempt in attempts]
    if not tried:
        return None
    starts = [attempt.get('started_at') or '' for (phase, number), attempt in tried
              if phase == 'author' and number == 1]
    since = max(starts) if starts else ''
    these = [(found, attempt) for found, attempt in tried
             if (attempt.get('started_at') or '') >= since]
    dollars = [attempt['dollars'] for _, attempt in these if attempt.get('dollars') is not None]
    return {'rounds': max([number or 0 for (_, number), _ in these] or [0]),
            'jobs': len(these),
            'seconds': round(sum(attempt.get('seconds') or 0 for _, attempt in these), 1),
            'dollars': round(sum(dollars), 4) if dollars else None}


def native(engine, root, run, task, sources, product):
    """Bridge the common workflow to each studio's existing confined worker transport."""
    from runner import worker_tools, documents, companion
    # Only an original that is another document than its capture (a PDF, a Word file, a web
    # page) is offered: a Markdown or text document is its capture.
    kept = getattr(engine, 'documents', None) or documents   # the engine's own, where it has one
    originals = {item['file']: item['original'] for item in kept.listed(root)
                 if item.get('file') and item.get('original') and item.get('distinct', True)}
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
    # What every job of this try took, so the stop can say what the rounds cost.
    spent = {'jobs': 0, 'seconds': 0.0, 'dollars': None, 'tokens': None, 'rounds': 0}

    def invoke(phase, guidance, payload, offered, fetch):
        if run.stop.is_set() or not engine._may_go(root):
            raise companion.Stopped()
        if phase == 'author':
            spent['rounds'] += 1
        number = spent['rounds']
        # Named under the research step, with its round, so that the step's tries, time and
        # money count every job, and the page can say which round is in hand.
        name = job_name(phase, number)
        result = {'kind': 'research-json'}
        if phase == 'author':
            # The job saves the dossier with the same helper the parent will, so the author
            # learns of a refusal while it can still correct it.
            result.update(runtime=str(tool.runtime), node=shutil.which('node'),
                          worker=payload['worker'], task={key: task[key] for key in TASK_FIELDS})
        doing = doing_words(phase, number)
        told = ('' if phase == 'author' else
                ' list_inputs names the original of each supplied source that has one: read it '
                'with read_source(source_id, original=true), as well as its capture, before you '
                'attest read_original. If a tool cannot serve an original, set read_original to '
                'false and give the tool\'s answer as its access_error.')
        work = Work(guidance + '\n\nUse only the studio tools; the parent runs helper commands. '
                    'Read list_inputs and sources; return the requested JSON using submit_artifact '
                    'under the name research-result. Keep public queries generic and nonconfidential.'
                    + told,
                    json.dumps(payload), 'research' if fetch else 'write',
                    {'inputs': {'research-task': json.dumps(payload)}, 'sources': offered,
                     'fetch': fetch, 'ask': False,
                     'artifacts': {'research-result': result}}, 'research-result')
        if product == 'presentation':
            outcome, handed, started, folder = engine._job(root, run, name, doing, work, deck=False)
        else:
            step = Step(name, 'agent', doing, doing, 'research')
            outcome, handed, started, folder = engine._job(root, run, step, work)
        folders.append(folder)
        if outcome.reason == 'stopped':
            engine._stopped(root, name if product == 'presentation' else step, outcome, started)
            raise companion.Stopped()
        cost = engine._cost(outcome)
        spent['jobs'] += 1
        spent['seconds'] += outcome.seconds or 0
        for key in ('dollars', 'tokens'):
            if cost.get(key) is not None:
                spent[key] = (spent[key] or 0) + cost[key]
        with engine.files:
            record = engine._load(root)
            accepted = handed['artifacts'].get('research-result')
            engine._tried(record, name, started, outcome.seconds,
                          'kept' if accepted and outcome.reason != 'stopped' else 'failed',
                          **cost)
            engine._store(root, record)
            engine._commit(root, 'record independent research job: ' + phase)
        if not accepted or outcome.reason == 'stopped':
            raise WorkspaceError('Research did not finish its ' + phase + ' job. Saved work is kept.')
        return accepted['text'], handed['sources']

    try:
        return Workflow(tool.runtime, tool._json).run(root, task, invoke, sources)
    except ReviewRefused as refusal:
        # The studio stops at its research step and keeps the objections with the review,
        # saying what this try's rounds took.
        cost = took(spent['seconds'], spent['dollars'])
        jobs = spent['jobs']
        failure = WorkspaceError(str(refusal) + (
            f" This try's {jobs} research job{'' if jobs == 1 else 's'} took {cost}."
            if cost else ''))
        failure.objections, failure.rounds = refusal.objections, refusal.rounds
        failure.cause = getattr(refusal, 'cause', None)
        failure.groups = getattr(refusal, 'groups', None) or []
        failure.spent = dict(spent)
        raise failure from refusal
    except ValueError as error:
        raise WorkspaceError(str(error)) from error
    finally:
        for folder in folders:
            shutil.rmtree(folder, ignore_errors=True)


def dry_read(engine, root, cause):
    """Whether the studio can now serve each original a check could not read: None once
    it can, else the tools' own answer. Each original is read as a check reads it, from a
    job folder of its own, and nothing else is done. A source the studio no longer offers an
    original for needs nothing read."""
    from runner import worker_tools, documents
    kept = getattr(engine, 'documents', None) or documents
    listed = {item['file']: item for item in kept.listed(root) if item.get('file')}
    for item in cause or ():
        entry = listed.get((item or {}).get('file'))
        if not entry or not entry.get('original') or not entry.get('distinct', True):
            continue
        with tempfile.TemporaryDirectory(prefix='research-dry-read-') as temp:
            folder = Path(temp) / 'job'
            try:
                worker_tools.prepare(folder, sources=[{
                    'title': entry.get('title') or item.get('title') or entry['file'],
                    'origin': 'a dry read', 'file': entry['file'],
                    'text': (Path(root) / entry['file']).read_text(encoding='utf-8'),
                    'original': entry['original'],
                    'original_path': Path(root) / entry['original']}], fetch=False, ask=False)
                ok, said = worker_tools.WorkerTools(folder).read_source('s1', original=True)
            except (OSError, ValueError) as failure:
                ok, said = False, str(failure)
        if not ok:
            return said
    return None


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
