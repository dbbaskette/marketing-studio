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
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import unicodedata

IDS_FOR_QUESTIONS = ('Planning questions have IDs. A finding that answers one has an ID '
                     "that begins with that question's ID and two hyphens, such as "
                     'instance-min--capacity. Keep each ID within 64 characters.')

# What every writer that receives research is told of it, once.
HANDOFF = ('The research is reviewed. Read its brief first: it says what matters for this piece. '
           'Use the facts and findings to check what you write. Their IDs, digests and verdicts '
           'are for checking and for provenance, notes and source lines: never put one in the '
           'words a reader reads.')
# Added to a research task's purpose when its goal compares options.
COMPARISON = ('The goal compares options: include a comparison with one criterion per row, and '
              'say where something is unknown rather than absent.')
COMPARING = re.compile(r'\b(?:compare|compares|comparing|comparison|versus|vs|alternatives)\b'
                       r'|\bchoose between\b|\bwhich is better\b')
NAMED_OR = re.compile(r'\b[A-Z][\w.+-]* or [A-Z][\w.+-]*')
# What the author is handed of Harness Research's references: its own stage references, not
# the one addressed to a studio.
AUTHOR_GUIDES = ('investigate.md', 'synthesize.md')
# Bringing research up to date: Harness Research's own section of synthesis-reuse.md, and
# what the author is asked to do.
REUSE = 'synthesis-reuse.md'
REFRESH_SECTION = '## Refresh selected evidence'
REFRESHED = ("Bring the evidence up to date: re-read each source with the studio's capture "
             'tool, so that each new capture is saved with the date it was read; then update '
             'what changed. The studio saves the dossier you hand back and arranges its '
             'independent review.')
# Said after the refresh section, which speaks of saving and arranging a review itself.
REFRESH_HERE = ("The studio's tools save every capture and the studio arranges the review: "
                'write no files yourself.')
CAPTURED = ("The studio's tools have saved every capture for you: that is the capture "
            '`investigate.md` asks for. Set each sources[].file to the exact Capture file '
            'path the tools returned. Write no files yourself.')
SOURCE_IDS = ('Use the saved tool IDs, such as s1, as sources[].id and repeat those exact '
              'IDs in facts[].citations[].source. A citation is {source, quote}: source '
              'names an entry in sources, not a file path or URL; quote is copied exactly '
              'from that source. Sections and brief refer to fact or finding IDs instead. '
              'Never invent a missing source. Source publication dates use source_date; '
              'read timestamps use accessed_at. Do not add a generic date field or invent dates.')


def compares(goal) -> bool:
    """Whether a goal compares options, by its words: compare, versus, vs, alternatives,
    choose between, which is better, or two named options joined by "or" ("Redis or
    Valkey"). A word list is predictable; it can be wrong both ways, and then costs one
    sentence."""
    if not isinstance(goal, str) or not goal.strip():
        return False
    return bool(COMPARING.search(goal.lower()) or NAMED_OR.search(goal))


def refresh_section(text: str) -> str:
    """The "Refresh selected evidence" section of synthesis-reuse.md, from its heading to the
    next of the same level, or nothing."""
    heading = re.search(r'^' + re.escape(REFRESH_SECTION) + r'\s*$', text, re.MULTILINE)
    at = heading.start() if heading else -1
    if at < 0:
        return ''
    found = re.search(r'^## ', text[at + len(REFRESH_SECTION):], re.MULTILINE)
    end = at + len(REFRESH_SECTION) + found.start() if found else -1
    return text[at:end if end >= 0 else len(text)].strip()


def purpose(kind: str, goal, priorities: str) -> str:
    """A research task's purpose, as every studio words it: what it informs, the goal, the
    studio's own priorities, and a comparison when the goal compares options."""
    said = f"Inform {kind}: {goal or 'explain the topic'}. {priorities}"
    return f'{said} {COMPARISON}' if compares(goal) else said


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
                snapshot_name(name, manifest)
    return facts, manifest


def publish(case, destination):
    """Copy the helper's whole bundle, preserving relative evidence links."""
    output = output_root(case)
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


def case_files(source):
    """Declared portable helper files for both output layouts, never an arbitrary directory."""
    source = working_case(source)
    output = output_root(source)
    prefix = '' if output == source else 'research/'
    facts, manifest = read_bundle(output)
    state = json.loads(inside(source, '.harness-research/synthesis.json').read_text())
    if state.get('owner') != OWNER or state.get('digest') != manifest['digest']:
        raise ValueError('Research state and bundle describe different revisions.')
    names = {'.harness-research/synthesis.json', prefix + 'output.json'}
    names.update(prefix + entry['file'] for entry in manifest['artifacts'])
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
    return publish(destination, Path(root) / 'research')


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

    def run(self, root, task, invoke, sources=(), readable=None):
        """One authored dossier followed by a separate checker. Refusals keep the draft.

        invoke(phase, guidance, payload, sources, fetch) returns JSON text plus only
        sources captured by the studio's confined tools. Worker IDs originate here,
        so the author cannot choose its reviewer identity.

        readable(cause) says whether the studio can serve the originals a check could not
        read: None when it can, so the next round is the check's to read them in, else the
        studio's own answer, and the research stops at once. Without it, the check's word
        stands and the research stops.
        """
        case = inside(root, str(CASE))
        case.mkdir(parents=True, exist_ok=True)
        rounds = 0
        for phase in ('author', 'review') * ROUNDS:
            if phase == 'author':
                rounds += 1
                worker = 'author-' + secrets.token_hex(12)
                guide = '\n\n'.join((self.runtime / 'references' / name).read_text()
                                      for name in AUTHOR_GUIDES)
                refreshing = task.get('refresh') is True
                if refreshing:   # its stage references, and the refresh section of reuse
                    reuse = self.runtime / 'references' / REUSE
                    section = refresh_section(reuse.read_text()) if reuse.is_file() else ''
                    guide += '\n\n' + section + '\n\n' + REFRESH_HERE if section else ''
                payload = {'task': task, 'worker': worker,
                           'return': 'A complete schema-2 dossier as JSON, including authored brief sections. '
                                     + CAPTURED + ' Copy each source\'s origin exactly as the capture showed it. '
                                     'Dossier format: sources, facts, findings, sections and brief are arrays; '
                                     'sections and brief hold {id, title, blocks: [{text, kind, refs}]}. '
                                     'Set every fact author to this worker ID. Do not write finished studio content. '
                                     + SOURCE_IDS}
                if any(isinstance(q, dict) and q.get('id') for q in task.get('planning_questions') or ()):
                    payload['return'] += ' ' + IDS_FOR_QUESTIONS
                if refreshing:
                    payload['return'] += ' ' + REFRESHED
                # Every source the author is given, with each field it must return (#303).
                outline = source_outline(sources, self.runtime)
                if outline:
                    payload['source_outline'] = outline
                    payload['return'] += ' ' + OUTLINED
                shaped = synthesis_outline(self.runtime, required=('sections',))
                if shaped:
                    payload['synthesis_outline'] = shaped
                    payload['return'] += ' ' + SYNTHESIZED
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
                dossier, problems = source_metadata(dossier, self.runtime)
                if problems:
                    raise ValueError(' '.join(problems))
                dossier, problems, _ = citation_sources(dossier, captures)
                if problems:
                    raise ValueError(' '.join(problems))
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
                checked = review_outline(self.runtime)
                if checked:
                    payload['review_outline'] = checked
                    payload['return'] += ' ' + REVIEWED
                result, _ = invoke(phase, guide, payload, sources, False)
                write(case, 'review.json', result)
                status = self.command(case, 'review', 'review.json', worker)
                if status.get('status') == 'complete':
                    break
                # A check that could not read an original it must attest to refuses whatever
                # the author corrects. When the studio cannot serve that original either, stop
                # now and do not count this round as a correction; when it can, the check
                # failed, not the studio, and the next round is its to read it in.
                try:
                    cause = unreadable_originals(json.loads(result), dossier)
                except (TypeError, ValueError):
                    cause = []
                said = (readable(cause) if readable else '') if cause else None
                if cause and said is not None:
                    raise CheckCouldNotFinish(objections(case), rounds - 1, cause, said or None)
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
    """The independent check could not read the original of a source the studio offered,
    that is all it objected to, and the studio cannot serve that original either. No
    correction can change that: it is the studio's problem, not the research's. `cause`
    holds each such source as {'source', 'title', 'file', 'original', 'access_error'};
    `said` is the studio's own answer, when it was asked; `rounds` counts only the rounds of
    correction before it, so this one is not counted."""

    def __init__(self, objections, rounds, cause, said=None):
        self.objections = list(objections)
        self.rounds = rounds
        self.cause = list(cause)
        self.said = said
        first = self.cause[0] if self.cause else {}
        named = f'the original of "{first.get("title") or first.get("source") or "a source"}"'
        why = said or first.get('access_error')
        if why:
            named += f' ({shortened(why).rstrip(".")}.)'
        more = len(self.cause) - 1
        if more:
            named += f' and of {more} more source' + ('' if more == 1 else 's')
        ValueError.__init__(self, (
            f'The research check could not read {named}. That is a studio problem, not a '
            'research problem: nothing was found wrong with the report, but the check could '
            'not finish. Nothing to correct until the original is readable.'))


def unreadable_originals(review, dossier):
    """The sources with an original of their own that a review says it could not read,
    when they are all it objected to; else []. That is: every verdict it did not support
    rests only on such sources, and its assessment asks for no revision. A verdict rests on
    the sources its fact cites, its finding's facts cite, or its passage's facts and
    findings cite. A source with no original (its capture is the document) is never the
    cause: the check has only to read its capture. Each is {'source', 'title', 'file',
    'original', 'access_error'}."""
    if not isinstance(review, dict) or not isinstance(dossier, dict):
        return []
    named = {source.get('id'): source for source in dossier.get('sources') or ()
             if isinstance(source, dict)}
    unread = {item.get('source'): item.get('access_error') or 'it gave no reason'
              for item in review.get('originals') or ()
              if isinstance(item, dict) and item.get('read_original') is False
              and (named.get(item.get('source')) or {}).get('original_file')}
    if not unread:
        return []
    assessment = review.get('assessment') or {}
    if isinstance(assessment, dict) and 'needs-revision' in (assessment.get('coverage'),
                                                            assessment.get('usefulness')):
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
            if not sources or not sources <= unread.keys():
                return []
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


# What the pinned helper bounds that its schema does not state: the length of each text it
# reads, which Harness Research's text() caps at 4000 characters unless named here.
TEXT_LIMIT = 4000
LIMITS = {'statement': 10000, 'quote': 30000}
# Fields the studio knows and checks against its own captures: an investigator copies them.
HOST_FIELDS = ('id', 'file', 'origin', 'permission', 'original_file')
# Optional fields Harness Research checks whenever they are present, and only then.
WHEN_PRESENT = {'source': ('source_date', 'accessed_at', 'version'), 'citation': ('locator',)}
# What a field an investigator fills in means, in the studio's words. A field the pinned
# schema adds later is still listed, as required or optional, without them.
MEANING = {
    'title': "The source's own title. The outline gives one for each source the studio offered: "
             'keep it unless the source names itself otherwise.',
    'publisher': 'Who published the source, as the source itself shows it: an organisation, team '
                 'or author.',
    'context': 'full when the capture holds the whole source, or all of it that matters here; '
               'partial when part of it is missing or cut short.',
    'context_note': 'Say specifically what part of the source is missing.',
    'source_date': "The source's own publication or revision date, copied as the source states "
                   'it. Leave it out when the source states none: never guess a date.',
    'accessed_at': 'When the source was read, only when a tool told you. Leave it out otherwise: '
                   'never guess a date.',
    'version': 'A version the source itself names, such as a release number. Leave it out when it '
               'names none.',
}
UNREADABLE = 'The pinned Harness Research source metadata contract could not be read.'
UNFINISHED = ('The pinned Harness Research collection check could not finish. This submission was '
              'not accepted; do not treat report validation as collection approval.')
# Said once, after everything a refused evidence packet needs corrected.
TAIL = ('Correct all of these and resubmit within this job. Facts contain only id, statement, '
        'author and citations; citations contain source, quote and optional locator. Do not '
        'remove a kind label to turn an inference into a fact; retain unsupported or inferred '
        'material as a gap for synthesis. Captured evidence is unchanged.')
OUTLINED = ('source_outline lists every source the studio gave you. Build each source you return '
            'from its entry: copy id, file, origin and permission exactly, keep its title, and add '
            'the fields source_outline.fill_in names; use no other fields. A source you save '
            'during this job is built the same way from what saving it returned (its ID, Capture '
            'file and Origin), with permission public. Copy every quote character for character '
            'from the capture it cites.')
# What JavaScript's trim() removes: Harness Research refuses text that is only these.
JS_SPACE = frozenset('\t\n\v\f\r\ufeff\u2028\u2029')


def pinned(runtime):
    """The definitions of the pinned Harness Research synthesis schema."""
    return json.loads((Path(runtime) / 'references/synthesis.schema.json').read_text())['$defs']


def conditions(definition):
    """{field: [(other field, value), ...]}: what a schema definition requires only when another
    field has a value, from its allOf if/then rules."""
    found = {}
    for rule in definition.get('allOf') or ():
        if not isinstance(rule, dict):
            continue
        tests = (rule.get('if') or {}).get('properties') or {}
        for field in (rule.get('then') or {}).get('required') or ():
            for other, test in tests.items():
                if isinstance(test, dict) and 'const' in test:
                    found.setdefault(field, []).append((other, test['const']))
    return found


def permission_of(capture):
    """A capture's permission, as the studio's checks read it."""
    return capture.get('permission') or ('selected' if capture.get('offered', True) else 'public')


def source_outline(sources, runtime):
    """Every source a job is given, as the investigator should return it: the fields the studio
    knows, filled in, and the fields it must add, each said from the pinned schema so the list
    cannot drift from Harness Research. Sources are numbered s1, s2 … in the order given, as the
    studio's tools number them. None when the pinned schema cannot be read."""
    try:
        definition = pinned(runtime)['source']
        rules = definition['properties']
        fields = list(rules)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    required, when = set(definition.get('required') or ()), conditions(definition)
    entries = []
    for number, source in enumerate(sources, start=1):
        known = {'id': f's{number}', 'file': source.get('file'),
                 'origin': source.get('origin', source.get('url')),
                 'permission': permission_of(source), 'title': source.get('title')}
        entries.append({key: known[key] for key in [*fields, *known]
                        if key in known and known[key] and key in rules})
    fill = {}
    for field in fields:
        if field in HOST_FIELDS:
            continue
        rule = rules[field] if isinstance(rules[field], dict) else {}
        said = ('Required.' if field in required else
                ' '.join(f'Required when {other} is {value}.' for other, value in when[field])
                if field in when else 'Optional.')
        if isinstance(rule.get('enum'), list):
            said += ' One of ' + ', '.join(map(str, rule['enum'])) + '.'
        if field in MEANING:
            said += ' ' + MEANING[field]
        fill[field] = said
    note = OUTLINED + f' Each text field holds 1 to {TEXT_LIMIT:,} characters.'
    if 'original_file' in rules:
        note += ' The studio sets original_file; leave it out.'
    return {'note': note, 'fields': fields, 'fill_in': fill, 'sources': entries}


def js_length(value):
    """A text's length as JavaScript counts it, in UTF-16 code units."""
    return len(value.encode('utf-16-le', 'surrogatepass')) // 2


def wrong_text(value, limit=TEXT_LIMIT):
    """Why Harness Research's text() would refuse a value, or None when it would accept it."""
    if not isinstance(value, str):
        return 'is missing' if value is None else 'must be text'
    if all(c in JS_SPACE or unicodedata.category(c) == 'Zs' for c in value):
        return 'is empty'
    if js_length(value) > limit:
        return f'is longer than {limit:,} characters'
    return None


def identifier(value, rule):
    """Whether a value matches the pattern a schema rule gives an ID, as the helper checks it."""
    pattern = (rule or {}).get('pattern') if isinstance(rule, dict) else None
    if not pattern:
        return True
    try:
        return isinstance(value, str) and re.fullmatch(pattern.removeprefix('^').removesuffix('$'),
                                                       value) is not None
    except re.error:
        return True


def capture_texts(sources, captures, folder):
    """{source ID: the capture text Harness Research will read for it}, for each source whose
    file this job saved: the exact bytes the helper's case is given, decoded as it decodes them."""
    saved = {entry['file']: entry for entry in captures if entry.get('file')}
    texts = {}
    for source in sources:
        file = source.get('file') if isinstance(source, dict) else None
        entry = saved.get(file) if isinstance(file, str) else None
        if not entry or not folder or not entry.get('local') or not isinstance(source.get('id'), str):
            continue
        try:
            text = (Path(folder) / entry['local']).read_bytes().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            continue   # The helper says why it cannot read it.
        texts.setdefault(source['id'], text.removeprefix('\ufeff'))
    return texts


def clipped(quote, limit=80):
    line = ' '.join(str(quote).split())
    return line if len(line) <= limit else line[:limit - 1].rstrip() + '…'


def packet_problems(value, texts, runtime, worker=None, mode=None):
    """What the pinned helper's common evidence rules would refuse, every one at once, as
    (problems, flawed source indexes, flawed fact indexes).

    These are the studio's equivalents of the rules Harness Research stops at the first of:
    each source's required and conditional fields, its choices and its text bounds; each fact's
    ID, statement, author and citations; and each quote, which must appear exactly in the
    capture it cites. The fields, choices and conditions come from the pinned schema; a rule
    the studio does not know here is still the helper's, which runs once these pass. Nothing
    is refused here that the helper would accept. File, origin, permission and citation IDs are
    checked against the job's own captures by uncaptured and citation_sources.
    """
    try:
        definitions = pinned(runtime)
        source_rule, fact_rule = definitions['source'], definitions['fact']
        source_fields = source_rule['properties']
        fact_fields = fact_rule['properties']
    except (OSError, ValueError, KeyError, TypeError):
        return [], set(), set()
    citation_rule = (fact_fields.get('citations') or {}).get('items') or {}
    citation_fields = citation_rule.get('properties') or {}
    required, when = set(source_rule.get('required') or ()), conditions(source_rule)
    problems, flawed_sources, flawed_facts = [], set(), set()
    rows = value.get('sources') if isinstance(value.get('sources'), list) else []
    ids = [row.get('id') for row in rows if isinstance(row, dict)]
    for index, source in enumerate(rows):
        if not isinstance(source, dict):
            continue
        name = source['id'] if isinstance(source.get('id'), str) and source['id'] else f'number {index + 1}'
        said = []
        if 'id' in source_fields and not identifier(source.get('id'), source_fields['id']):
            said.append('id must be lowercase letters, digits and hyphens (at most 64), such as s1')
        elif ids.count(source.get('id')) > 1:
            said.append('another source has the same id')
        for field, rule in source_fields.items():
            rule = rule if isinstance(rule, dict) else {}
            if field in HOST_FIELDS:
                continue
            present = field in source
            needed = field in required or any(source.get(other) == wanted
                                              for other, wanted in when.get(field, ()))
            if isinstance(rule.get('enum'), list):
                if needed and source.get(field) not in rule['enum']:
                    said.append(f'{field} must be one of ' + ', '.join(map(str, rule['enum']))
                                + (f', not {clipped(source[field], 40)!r}' if present else ''))
            elif rule.get('type') == 'string' and (needed or present and field in WHEN_PRESENT['source']):
                wrong = 'is missing' if not present else wrong_text(source[field])
                if wrong:
                    said.append(f'{field} {wrong}' + (
                        ': leave it out when unknown, and never guess a date' if field in ('source_date', 'accessed_at')
                        else ': give who published it, as the source itself shows it' if field == 'publisher'
                        else ': say what part of the source is missing' if field == 'context_note' else ''))
        if said:
            flawed_sources.add(index)
            problems.append(f'Source {name}: ' + '; '.join(said) + '.')
    known = {row['id'] for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)}
    facts = value.get('facts') if isinstance(value.get('facts'), list) else []
    fact_ids = [fact.get('id') for fact in facts if isinstance(fact, dict)]
    authored = False
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            flawed_facts.add(index)
            problems.append(f'Fact number {index + 1}: return each fact as an object.')
            continue
        name = fact['id'] if isinstance(fact.get('id'), str) and fact['id'] else f'number {index + 1}'
        said = []
        unknown = sorted(set(fact) - set(fact_fields)) if mode == 'evidence' else []
        if unknown:
            said.append('unknown field(s) ' + ', '.join(unknown))
        if 'id' in fact_fields and not identifier(fact.get('id'), fact_fields['id']):
            said.append('id must be lowercase letters, digits and hyphens (at most 64)')
        elif fact_ids.count(fact.get('id')) > 1:
            said.append('another fact has the same id')
        elif isinstance(fact.get('id'), str) and fact['id'] in known:
            said.append('its id is also a source id; give it its own')
        if 'statement' in fact_fields:
            wrong = wrong_text(fact.get('statement'), LIMITS['statement'])
            if wrong:
                said.append(f'statement {wrong}')
        if worker and fact.get('author') != worker:
            authored = True
            flawed_facts.add(index)
        citations = fact.get('citations')
        if not isinstance(citations, list):
            said.append('citations must be an array')
            citations = []
        elif not citations and 'citations' in fact_fields:
            said.append('it needs at least one citation with an exact quote')
        for number, citation in enumerate(citations, start=1):
            if not isinstance(citation, dict):
                said.append(f'citation {number} must be an object')
                continue
            unknown = sorted(set(citation) - set(citation_fields)) if mode == 'evidence' and citation_fields else []
            if unknown:
                said.append(f'citation {number} has unknown field(s) ' + ', '.join(unknown))
            ref = citation.get('source')
            if not isinstance(ref, str) or ref not in known:
                flawed_facts.add(index)   # citation_sources says which IDs it may use
                continue
            quote = citation.get('quote')
            wrong = wrong_text(quote, LIMITS['quote']) if 'quote' in citation_fields else None
            if wrong:
                said.append(f'citation {number} quote {wrong}')
            for field in WHEN_PRESENT['citation']:
                if field in citation and field in citation_fields and wrong_text(citation[field]):
                    said.append(f'citation {number} {field} {wrong_text(citation[field])}: '
                                'leave it out when there is none')
            if not wrong and isinstance(quote, str) and ref in texts and quote not in texts[ref]:
                from studio_core.shared_runner.worker_tools import place
                found = place(texts[ref], quote)
                said.append(f'the quote {clipped(quote)!r} is not in source {ref} exactly' + (
                    f'; the capture has it as {found[1]!r}: copy that' if found and len(found[1]) <= 400
                    else '; it differs from the capture in spacing or punctuation: copy it from '
                         'the capture as it stands' if found else
                    '; quote only words the capture holds, or cite another source'))
        if said:
            flawed_facts.add(index)
            problems.append(f'Fact {name}: ' + '; '.join(said) + '.')
    if authored:
        problems.append(f'Set every fact author to {worker}.')
    return problems, flawed_sources, flawed_facts


def source_metadata(value, runtime):
    """Match source metadata to the pinned helper before the collection boundary.

    The dossier saver permits extra metadata that the collection registry refuses.
    Preserve the common date spelling without guessing missing dates or resolving
    conflicts. Other unknown fields get feedback while the author can still correct
    its submission; evidence, permissions, captures and citations stay unchanged.
    """
    if not runtime:
        return value, []
    try:
        allowed = set(pinned(runtime)['source']['properties'])
    except (OSError, ValueError, KeyError, TypeError):
        return value, [UNREADABLE]
    result, problems = copy.deepcopy(value), []
    for source in result.get('sources') or []:
        if not isinstance(source, dict):
            problems.append('Return each source as an object.')
            continue
        name = source.get('id') or 'unnamed'
        if 'date' in source and 'source_date' in allowed:
            date = source['date']
            if isinstance(date, str) and date.strip() and ('source_date' not in source or source['source_date'] == date):
                source['source_date'] = source.pop('date')
            else:
                problems.append(f'Source {name}: date is empty, invalid or conflicts with source_date. '
                                'Use one supported source_date, or omit it when unknown; do not guess.')
        unknown = set(source) - allowed
        if unknown:
            problems.append(f'Source {name}: unknown source field(s): {", ".join(sorted(unknown))}. '
                            f'Use only the pinned fields: {", ".join(sorted(allowed))}. '
                            'Correct and resubmit within this job; keep captured evidence unchanged.')
    return result, problems


# The synthesis and review rules Harness Research enforces beyond its schema, in the studio's
# words, beside the shapes read from that schema. synthesis_problems and review_problems check
# each of them.
SYNTHESIS_RULES = (
    'A block of kind gap may have empty refs; every other block needs at least one ref. A '
    "finding's summary is never a gap.",
    "A finding's support, counter, and the refs of its summary, implications, conditions and gaps "
    'name fact IDs from the evidence; so do comparison cell refs. Report and brief block refs '
    'name fact or finding IDs. No refs list repeats an ID.',
    'Finding IDs are distinct from each other and from every source and fact ID. Section IDs are '
    'distinct within sections, and brief section IDs within the brief.',
    'Each comparison has at least two distinct subjects. Each row has a distinct criterion and '
    'exactly one cell per subject, naming it.',
    'Text holds at most 4,000 characters for a title, subject or criterion, 30,000 for a block '
    'and 10,000 for a comparison cell.',
)
SYNTHESIZED = ('synthesis_outline gives the exact shape of what you return, from the pinned '
               'Harness Research schema: build it from that outline and its rules, and check '
               'every reference against the evidence IDs before you hand it back.')
REVIEW_RULES = (
    'Start from review_template and keep its digest, each original\'s sha256 (and '
    'original_sha256 when it has one), and every fact, finding and prose ID, exactly once each.',
    'Give every item a verdict and a note that explains it, including supported ones: an empty '
    'note is refused.',
    'Set read_original true only when you read that source (and its original, when it has one); '
    'when false, give access_error: what the tool answered.',
)
REVIEWED = ('review_outline says what each field of the review takes, from the pinned Harness '
            'Research schema. A refusal lists everything to correct at once.')
# Said once, after everything a refused synthesis needs corrected.
SYNTHESIS_TAIL = ('Correct all of these and hand the whole synthesis back within this job. The '
                  'registered evidence is kept unchanged.')
LIMITS.update(block=30000, cell=10000, note=20000)
ID_PATTERN = '^[a-z0-9][a-z0-9-]{0,63}$'


def pinned_schema(runtime):
    """The whole pinned Harness Research synthesis schema."""
    return json.loads((Path(runtime) / 'references/synthesis.schema.json').read_text())


def described(rule):
    """What a schema rule asks for, in words, or a mapping of an inline object's fields."""
    if not isinstance(rule, dict):
        return 'any value'
    if '$ref' in rule:
        name = str(rule['$ref']).rsplit('/', 1)[-1]
        return f'a {name}, shaped as shapes.{name}'
    if 'const' in rule:
        return 'exactly ' + json.dumps(rule['const'])
    if isinstance(rule.get('enum'), list):
        return 'one of ' + ', '.join(map(str, rule['enum']))
    kind = rule.get('type')
    if kind == 'string':
        pattern = rule.get('pattern')
        if pattern == ID_PATTERN:
            return 'an ID: lowercase letters, digits and hyphens, at most 64'
        if pattern == '^[a-f0-9]{64}$':
            return 'a SHA-256 digest, copied exactly'
        return 'nonempty text' if rule.get('minLength') else 'text'
    if kind == 'boolean':
        return 'true or false'
    if kind == 'array':
        least = rule.get('minItems')
        items = described(rule.get('items'))
        said = 'an array' + (f' of at least {least}' if least else '')
        if isinstance(items, dict):
            return {'is': said + ' objects, each:' if least else said + ' of objects, each:',
                    'each': items}
        return said + ', each ' + items + (', with no repeats' if rule.get('uniqueItems') else '')
    if kind == 'object' and isinstance(rule.get('properties'), dict):
        return fields(rule)
    return 'any value'


def fields(definition):
    """{field: what it takes}, for each field of a schema definition, required ones first said."""
    required, when = set(definition.get('required') or ()), conditions(definition)
    shaped = {}
    for name, rule in (definition.get('properties') or {}).items():
        said = described(rule)
        said = said[:1].upper() + said[1:] if isinstance(said, str) else said
        lead = ('Required.' if name in required else
                ' '.join(f'Required when {other} is {json.dumps(value)}.' for other, value in when[name])
                if name in when else 'Optional.')
        shaped[name] = {'is': lead + ' ' + said['is'][:1].upper() + said['is'][1:], 'each': said['each']} \
            if isinstance(said, dict) and 'each' in said else \
            {'is': lead + ' An object:', 'fields': said} if isinstance(said, dict) else lead + ' ' + said
    return shaped


def synthesis_outline(runtime, keys=('findings', 'sections', 'brief', 'comparisons'),
                      required=('findings', 'sections', 'brief')):
    """The exact shape of a synthesis: each part it returns, the shape of a finding, a section,
    a statement (a block) and a comparison, read from the pinned schema, and the rules
    Harness Research enforces beyond it. `required` names the parts the studio requires to be
    nonempty. None when the pinned schema cannot be read."""
    try:
        schema = pinned_schema(runtime)
        top, definitions = schema['properties'], schema['$defs']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    parts, needed = {}, set(schema.get('required') or ())
    for key in keys:
        if key in top:
            said = described(top[key])
            said = said if isinstance(said, str) else said.get('is', '')
            parts[key] = ('Required, with at least one item. ' if key in required else
                          'Required. ' if key in needed else 'Optional. ') + said[:1].upper() + said[1:]
    shapes = {name: fields(definitions[name]) for name in ('finding', 'section', 'statement', 'comparison')
              if isinstance(definitions.get(name), dict)}
    return {'note': SYNTHESIZED, 'return': parts, 'shapes': shapes, 'rules': list(SYNTHESIS_RULES)}


def review_outline(runtime):
    """What each field of an independent review takes, from the pinned schema, and the rules
    Harness Research enforces beyond it. None when the pinned schema cannot be read."""
    try:
        definition = pinned_schema(runtime)['$defs']['review']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {'note': REVIEWED, 'fields': fields(definition), 'rules': list(REVIEW_RULES)}


def distinct(values):
    """Whether values are all different, as JavaScript's Set counts strings."""
    texts = [value for value in values if isinstance(value, str)]
    return len(texts) == len(values) and len(set(texts)) == len(texts)


def block_problems(value, allowed, kinds, label):
    """Why Harness Research's block() would refuse a statement, as a list of words."""
    if not isinstance(value, dict):
        return [f'{label} must be an object with text, kind and refs']
    said = []
    wrong = wrong_text(value.get('text'), LIMITS['block'])
    if wrong:
        said.append(f'{label} text {wrong}')
    if kinds and value.get('kind') not in kinds:
        said.append(f'{label} kind must be one of ' + ', '.join(kinds))
    said += refs_problems(value.get('refs'), allowed, f'{label} refs', value.get('kind') != 'gap')
    return said


def refs_problems(refs, allowed, label, required=True):
    """Why Harness Research's refs() would refuse a list of references."""
    if not isinstance(refs, list):
        return [f'{label} must be an array']
    if required and not refs:
        return [f'{label} need at least one ID']
    unknown = [ref for ref in refs if not isinstance(ref, str) or ref not in allowed]
    if unknown or not distinct(refs):
        return [f'{label} ' + (f'name unknown ID(s): {", ".join(clipped(ref, 64) for ref in unknown[:5])}'
                               if unknown else 'repeat an ID')]
    return []


def synthesis_problems(value, runtime, shaped=False):
    """What the pinned helper's synthesis save would refuse in findings, sections, brief and
    comparisons, every one at once. The helper stops at the first; these are its rules
    (validateDossier), with the shapes and choices read from the pinned schema. `shaped` when
    the studio has already said which parts are missing or not arrays. Nothing when the pinned
    schema cannot be read."""
    try:
        definitions = pinned(runtime)
        finding_rule, section_rule = definitions['finding'], definitions['section']
        kinds = list((definitions['statement']['properties'].get('kind') or {}).get('enum') or [])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []
    finding_id = (finding_rule.get('properties') or {}).get('id')
    section_id = (section_rule.get('properties') or {}).get('id')
    problems = []
    rows = value.get('sources') if isinstance(value.get('sources'), list) else []
    facts = value.get('facts') if isinstance(value.get('facts'), list) else []
    source_ids = {row.get('id') for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)}
    fact_ids = {fact.get('id') for fact in facts if isinstance(fact, dict) and isinstance(fact.get('id'), str)}
    findings = value.get('findings')
    if not isinstance(findings, list):
        findings = []
        if not shaped:
            problems.append('findings must be an array.')
    named = [finding.get('id') if isinstance(finding, dict) else None for finding in findings]
    finding_ids = {ident for ident in named if isinstance(ident, str)}
    for index, finding in enumerate(findings):
        ident = named[index]
        name = ident if isinstance(ident, str) and ident else f'number {index + 1}'
        if not isinstance(finding, dict):
            problems.append(f'Finding {name}: return it as an object.')
            continue
        said = []
        if not identifier(ident, finding_id or {'pattern': ID_PATTERN}):
            said.append('id must be lowercase letters, digits and hyphens (at most 64)')
        elif named.count(ident) > 1:
            said.append('another finding has the same id')
        elif ident in source_ids or ident in fact_ids:
            said.append('its id is also a source or fact id; give it its own')
        wrong = wrong_text(finding.get('title'))
        if wrong:
            said.append(f'title {wrong}')
        said += block_problems(finding.get('summary'), fact_ids, kinds, 'summary')
        if isinstance(finding.get('summary'), dict) and finding['summary'].get('kind') == 'gap':
            said.append('its summary is a gap: a summary needs evidence; put unknowns in gaps')
        said += refs_problems(finding.get('support'), fact_ids, 'support')
        said += refs_problems(finding.get('counter'), fact_ids, 'counter', False)
        for group in ('implications', 'conditions', 'gaps'):
            blocks = finding.get(group)
            if not isinstance(blocks, list):
                said.append(f'{group} must be an array (it may be empty)')
                continue
            for number, block in enumerate(blocks, start=1):
                said += block_problems(block, fact_ids, kinds, f'{group} {number}')
        if said:
            problems.append(f'Finding {name}: ' + '; '.join(said) + '.')
    evidence = fact_ids | finding_ids
    parts = [('Report', 'sections', value.get('sections'), True)]
    if 'brief' in value:
        parts.append(('Brief', 'brief', value.get('brief'), True))
    for label, key, sections, needed in parts:
        if not isinstance(sections, list):
            if not shaped:
                problems.append(f'{key} must be an array.')
            continue
        if not sections:
            if not shaped:
                problems.append('At least one report section is required.' if key == 'sections'
                                else 'The brief needs at least one section.')
            continue
        ids = [section.get('id') if isinstance(section, dict) else None for section in sections]
        for index, section in enumerate(sections):
            ident = ids[index]
            name = f'{label} section ' + (ident if isinstance(ident, str) and ident else f'number {index + 1}')
            if not isinstance(section, dict):
                problems.append(f'{name}: return it as an object.')
                continue
            said = []
            if not identifier(ident, section_id or {'pattern': ID_PATTERN}):
                said.append('id must be lowercase letters, digits and hyphens (at most 64)')
            elif ids.count(ident) > 1:
                said.append(f'another {label.lower()} section has the same id')
            wrong = wrong_text(section.get('title'))
            if wrong:
                said.append(f'title {wrong}')
            blocks = section.get('blocks')
            if not isinstance(blocks, list) or not blocks:
                said.append('blocks must be a nonempty array')
            else:
                for number, block in enumerate(blocks, start=1):
                    said += block_problems(block, evidence, kinds, f'block {number}')
            if said:
                problems.append(f'{name}: ' + '; '.join(said) + '.')
    raw = value.get('comparisons')
    comparisons = [] if raw is None or raw is False or raw == '' or (
        isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw == 0) else raw
    if not isinstance(comparisons, list):
        problems.append('comparisons must be an array, or left out.')
        comparisons = []
    for index, comparison in enumerate(comparisons, start=1):
        name = f'Comparison {index}'
        if not isinstance(comparison, dict):
            problems.append(f'{name}: return it as an object.')
            continue
        said = []
        wrong = wrong_text(comparison.get('title'))
        if wrong:
            said.append(f'title {wrong}')
        subjects = comparison.get('subjects')
        if not isinstance(subjects, list):
            said.append('subjects must be an array')
            subjects = None
        elif len(subjects) < 2 or not distinct(subjects) or any(wrong_text(s) for s in subjects):
            said.append('subjects must be at least two distinct, nonempty names')
        rows_ = comparison.get('rows')
        if not isinstance(rows_, list):
            said.append('rows must be an array')
            rows_ = []
        criteria = []
        for number, row in enumerate(rows_, start=1):
            if not isinstance(row, dict):
                said.append(f'row {number} must be an object')
                continue
            criterion = row.get('criterion')
            wrong = wrong_text(criterion)
            if wrong:
                said.append(f'row {number} criterion {wrong}')
            elif criterion in criteria:
                said.append(f'row {number} repeats the criterion {clipped(criterion, 60)!r}')
            criteria.append(criterion)
            cells = row.get('cells')
            if not isinstance(cells, list):
                said.append(f'row {number} cells must be an array')
                continue
            named_cells = [cell.get('subject') if isinstance(cell, dict) else None for cell in cells]
            if subjects is not None and (len(cells) != len(subjects) or not distinct(named_cells)
                                         or any(subject not in subjects for subject in named_cells)):
                said.append(f'row {number} needs exactly one cell per subject, naming it')
            for place_, cell in enumerate(cells, start=1):
                if not isinstance(cell, dict):
                    said.append(f'row {number} cell {place_} must be an object')
                    continue
                wrong = wrong_text(cell.get('text'), LIMITS['cell'])
                if wrong:
                    said.append(f'row {number} cell {place_} text {wrong}')
                said += refs_problems(cell.get('refs'), fact_ids, f'row {number} cell {place_} refs')
        if said:
            problems.append(f'{name}: ' + '; '.join(said) + '.')
    return problems


def review_problems(review, template, runtime=None):
    """What the pinned helper's validateReview would refuse in an independent review, every
    one at once, checked against the review_template the reviewer was given. The helper stops
    at the first; these are all of its rules except the reviewer's identity and stale evidence,
    which the studio controls, with the choices read from the pinned schema."""
    try:
        definition = pinned_schema(runtime)['$defs']['review']['properties'] if runtime else {}
    except (OSError, ValueError, KeyError, TypeError):
        definition = {}

    def choices(group, field, fallback):
        rule = definition.get(group) or {}
        rule = (rule.get('items') or rule) if group != 'assessment' else rule
        found = ((rule.get('properties') or {}).get(field) or {}).get('enum')
        return list(found) if isinstance(found, list) else list(fallback)

    if not isinstance(review, dict):
        return ['Return the review as one JSON object, filled in from review_template.']
    problems = []
    if review.get('schema') != 2:
        problems.append('Set "schema": 2.')
    if review.get('digest') != template.get('digest'):
        problems.append(f"Set digest to {template.get('digest')!r}, exactly as review_template gives it.")
    expected = [item for item in template.get('originals') or () if isinstance(item, dict)]
    originals = review.get('originals')
    if not isinstance(originals, list):
        problems.append('originals must be an array, one entry for each source in review_template.')
    else:
        given = [item.get('source') if isinstance(item, dict) else None for item in originals]
        wanted = [item.get('source') for item in expected]
        if len(originals) != len(wanted) or not distinct(given) or set(given) != set(wanted):
            problems.append(f'originals must hold exactly one entry for each of the {len(wanted)} '
                            'source(s) in review_template: ' + ', '.join(map(str, wanted[:40])) + '.')
        for item in expected:
            found = next((entry for entry in originals if isinstance(entry, dict)
                          and entry.get('source') == item.get('source')), None)
            if found is None:
                continue
            name = item.get('source')
            if found.get('sha256') != item.get('sha256') or (
                    'original_sha256' in item and found.get('original_sha256') != item['original_sha256']):
                problems.append(f'Original {name}: copy sha256' + (' and original_sha256' if 'original_sha256' in item
                                                                    else '') + ' exactly from review_template.')
            if not isinstance(found.get('read_original'), bool):
                problems.append(f'Original {name}: set read_original to true or false.')
            elif found['read_original'] is False and wrong_text(found.get('access_error')):
                problems.append(f'Original {name}: read_original is false, so give access_error: what '
                                'the tool answered.')
    for group in ('facts', 'findings', 'prose'):
        items, wanted = review.get(group), [item.get('id') for item in template.get(group) or ()
                                            if isinstance(item, dict)]
        if not isinstance(items, list):
            problems.append(f'{group} must be an array, one entry for each in review_template.')
            continue
        given = [item.get('id') if isinstance(item, dict) else None for item in items]
        if len(items) != len(wanted) or not distinct(given) or set(given) != set(wanted):
            missing = [ident for ident in wanted if ident not in given]
            problems.append(f'{group} must hold exactly one entry for each of the {len(wanted)} in '
                            'review_template' + (', and is missing ' + ', '.join(map(str, missing[:10]))
                                                 if missing else '') + '.')
        verdicts = choices(group, 'verdict', ('supported', 'unsupported', 'narrow'))
        unjudged, unexplained = [], []
        for ident in wanted:
            found = next((item for item in items if isinstance(item, dict) and item.get('id') == ident), None)
            if found is None:
                continue
            if found.get('verdict') not in verdicts:
                unjudged.append(ident)
            if wrong_text(found.get('note'), LIMITS['note']):
                unexplained.append(ident)
        if unjudged:
            problems.append(f'{group}: set verdict to one of {", ".join(verdicts)} for '
                            f'{len(unjudged)} item(s), such as ' + ', '.join(map(str, unjudged[:5])) + '.')
        if unexplained:
            problems.append(f'{group}: give a note explaining the verdict for {len(unexplained)} '
                            'item(s), such as ' + ', '.join(map(str, unexplained[:5])) + '.')
    assessment = review.get('assessment') if isinstance(review.get('assessment'), dict) else {}
    for field, fallback in (('coverage', ('accurate', 'needs-revision')),
                            ('usefulness', ('adequate', 'needs-revision'))):
        allowed = choices('assessment', field, fallback)
        if assessment.get(field) not in allowed:
            problems.append(f'assessment.{field} must be one of {", ".join(allowed)}.')
    if wrong_text(assessment.get('note'), LIMITS['note']):
        problems.append('assessment.note must explain the assessment.')
    return problems


def check_json(text, spec):
    """Check a research hand-back and say everything wrong with it at once.

    Every studio check runs, each listing all it finds, and then the studio's equivalents of
    the pinned helper's common evidence rules (packet_problems). The helper itself then runs
    as before when nothing was found, so it still decides; when something was found in an
    evidence packet, it runs on the part with nothing found, the flawed sources and facts set
    aside, so a problem only it knows is listed too. Returns (problems, checks, warnings, kept).
    """
    problems = []
    warnings = []
    kept = text
    matched = 0
    mode = spec.get('research_mode')
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            problems.append('Return a schema-2 JSON object.')
        elif isinstance(spec.get('review_template'), dict):
            # An independent review, checked against the template it was given (#303).
            problems += review_problems(value, spec['review_template'], spec.get('runtime'))
        elif isinstance(value.get('sources'), list) and any(not isinstance(source, dict) for source in value['sources']):
            problems.append('Return each source as an object.')
            if value.get('schema') != 2:
                problems.insert(0, 'Return a schema-2 JSON object: set "schema": 2.')
        elif mode or ('captures' in spec and isinstance(value.get('sources'), list)):
            if value.get('schema') != 2:
                problems.append('Return a schema-2 JSON object: set "schema": 2.')
            if mode == 'compose':
                from studio_core.research_session import COMPOSED, compose_shape, preparation
                shape = compose_shape(value)
                problems += shape
                if shape:   # Check the parts it did return as well.
                    value = {**copy.deepcopy(spec.get('evidence_base') or {}),
                             **{key: part for key, part in value.items() if key in COMPOSED}}
                    value.setdefault('sources', [])
                    value.setdefault('facts', [])
                else:
                    value = preparation(value, spec)
                kept = json.dumps(value)
            elif mode:
                from studio_core.research_session import preparation
                try:
                    value = preparation(value, spec)
                except ValueError as error:
                    problems.append(str(error))
                    if mode != 'evidence':
                        raise ValueError(' '.join(problems)) from None
                    # Check the rest as well: the sources and facts, when they are arrays.
                    value = preparation({key: value[key] for key in ('schema', 'sources', 'facts', 'gaps')
                                         if key in value}, spec)
                kept = json.dumps(value)
            captures = spec.get('captures', [])
            problems += uncaptured(value['sources'], captures)
            value, found, matched = citation_sources(value, captures)
            problems += found
            normalized, found = source_metadata(value, spec.get('runtime'))
            problems += [] if problems and found == [UNREADABLE] else found
            standardized = normalized != value
            if mode or matched or standardized:
                kept = json.dumps(normalized)
            value = normalized
            if spec.get('runtime'):
                flawed_sources, flawed_facts = set(), set()
                if mode != 'compose':
                    texts = capture_texts(value['sources'], captures, spec.get('folder'))
                    found, flawed_sources, flawed_facts = packet_problems(
                        value, texts, spec['runtime'], spec.get('worker'), mode)
                    problems += found
                if mode != 'evidence':   # A synthesis, or a whole dossier: its prose too.
                    problems += synthesis_problems(value, spec['runtime'], shaped=mode == 'compose')
                if not problems:
                    problems += refused(value, spec)
                elif mode == 'evidence':
                    problems += aside(value, spec, captures, flawed_sources, flawed_facts)
            if mode == 'evidence' and any(problem != UNFINISHED for problem in problems):
                problems.append(TAIL)
            elif mode == 'compose' and problems:
                problems.append(SYNTHESIS_TAIL)
            if not problems and standardized and not mode:
                warnings.append('Standardized source date metadata as source_date; dates and evidence are unchanged.')
            if not problems and matched and not mode:
                warnings.append(f'Matched {matched} citation source handle(s) to the same '
                                'captured source in the dossier. Claims and quotations are unchanged.')
        elif value.get('schema') != 2:
            problems.append('Return a schema-2 JSON object.')
    except (TypeError, json.JSONDecodeError):
        problems.append('Return valid JSON, without Markdown fences.')
    except ValueError as error:
        problems = [str(error)] if not problems else problems
    return problems, [{'check': 'research.json', 'status': 'failed' if problems else 'passed',
                       'problems': problems}], warnings, kept


def aside(value, spec, captures, flawed_sources, flawed_facts):
    """What the pinned helper refuses in an evidence packet with what the studio already found
    wrong set aside: each source with a problem, and each fact with one or citing such a
    source. What it refuses in that part is wrong in the whole too. Nothing when no source is
    left to check."""
    rows = value['sources']
    flawed = set(flawed_sources)
    for index, source in enumerate(rows):
        if uncaptured([source], captures) or source_metadata({'sources': [source]}, spec['runtime'])[1]:
            flawed.add(index)
    sources = [source for index, source in enumerate(rows) if index not in flawed]
    if not sources:
        return []
    ids = {source.get('id') for source in sources if isinstance(source.get('id'), str)}
    facts = [fact for index, fact in enumerate(value['facts'])
             if index not in flawed_facts and isinstance(fact, dict)
             and isinstance(fact.get('citations'), list)
             and all(isinstance(c, dict) and c.get('source') in ids for c in fact['citations'])]
    return refused({**value, 'sources': sources, 'facts': facts}, spec)


def citation_sources(value, captures):
    """Resolve only exact job handles to a unique, verified dossier source identity.

    The worker's s1 handle and its own source-a ID may describe the same saved file.
    This bridge changes IDs only, never quotations or evidence. Unknown, ambiguous,
    unsaved or mismatched sources must be corrected by the author; the pinned helper
    still validates every quote and the independent reviewer still checks support.
    """
    result = copy.deepcopy(value)
    rows = result.get('sources')
    sources = [s for s in rows if isinstance(s, dict)] if isinstance(rows, list) else []
    ids = {s['id'] for s in sources if isinstance(s.get('id'), str) and s['id']}
    known = ', '.join(repr(name[:64]) for name in sorted(ids)[:40]) or 'none'
    handles = {}
    for capture in captures:
        handle = capture.get('id')
        if isinstance(handle, str) and handle:
            handles.setdefault(handle, []).append(capture)
    problems, matched = [], 0
    facts = result.get('facts')
    for fact in facts if isinstance(facts, list) else []:
        if not isinstance(fact, dict) or not isinstance(fact.get('citations'), list):
            continue  # The helper diagnoses schema errors, rather than this ID bridge.
        for index, citation in enumerate(fact['citations']):
            if not isinstance(citation, dict):
                continue
            ref = citation.get('source')
            if isinstance(ref, str) and ref in ids:
                continue
            found = handles.get(ref, []) if isinstance(ref, str) else []
            candidates = []
            if len(found) == 1:
                capture = found[0]
                permission = capture.get('permission') or (
                    'selected' if capture.get('offered', True) else 'public')
                candidates = [s for s in sources if isinstance(s.get('id'), str)
                              and s['id'] in ids
                              and s.get('file') == capture.get('file')
                              and s.get('file')
                              and s.get('origin') == capture.get('origin', capture.get('url'))
                              and s.get('permission') == permission]
            if len(candidates) == 1:
                citation['source'] = candidates[0]['id']
                matched += 1
            elif len(problems) < 20:
                label = repr(str(fact.get('id', '?'))[:64])
                missing = repr(ref[:100]) if isinstance(ref, str) else repr(ref)[:100]
                problems.append(f'facts[{label}].citations[{index}].source {missing} does not '
                                f'identify one dossier source. Use sources[].id exactly. '
                                f'Available source IDs: {known}. Do not guess from a quote '
                                'or invent a source; correct the citation and resubmit the dossier.')
    return result, problems, matched


def uncaptured(sources, captures):
    """Why sources a dossier cites differ from what its job saved. The parent refuses the same
    after the job; saying it while the author can still correct it keeps the research step."""
    saved = {entry['file']: entry for entry in captures if entry.get('file')}
    listed = ', '.join(sorted(saved)[:40]) or 'none yet'
    problems = []
    for source in sources:
        name = source.get('file') if isinstance(source, dict) else None
        entry = saved.get(name) if isinstance(name, str) else None
        if entry is None:
            problems.append(f'Source file {name!r} is not one this job saved. Save a page with '
                            'save_source first, then copy its "Capture file" exactly. Saved '
                            f'files: {listed}.')
            continue
        origin = entry.get('origin', entry.get('url'))
        ident = source.get('id')
        label = f'{ident} ({name})' if isinstance(ident, str) and ident and ident != name else name
        if source.get('origin') != origin:
            problems.append(f'Source {label}: copy its origin exactly as {origin!r}.')
        permission = permission_of(entry)
        if source.get('permission') != permission:
            problems.append(f'Source {label}: its permission is {permission!r}.')
    return problems


def collection_preflight(case, dossier, spec):
    """Ask the pinned collection validator, not a second host-owned shape checker.

    Scratch registrations describe this local preflight only. They never become
    production invocation observations or accepted evidence checkpoints.
    """
    from studio_core.research_session import evidence_gaps

    worker, stream = spec['worker'], 'submission'
    script = Path(spec['runtime']) / 'scripts/harness-research.mjs'
    deadline = time.monotonic() + 120

    def command(action, value):
        file = '.harness-research/host-inputs/' + secrets.token_hex(12) + '.json'
        write(case, file, json.dumps(value))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired('collection preflight', 120)
        done = subprocess.run([spec.get('node') or 'node', str(script), 'collection', action,
                               '--project', str(case), '--file', file], capture_output=True,
                              text=True, timeout=remaining, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise ValueError((done.stderr.strip().splitlines() or ['Collection validation failed.'])[-1])
        return json.loads(done.stdout)

    supplied = []
    for source in dossier['sources']:
        if source['permission'] == 'selected':
            file = source.get('original_file') or source['file']
            supplied.append({'origin': source['origin'], 'file': file,
                             'sha256': hashlib.sha256(inside(case, file).read_bytes()).hexdigest()})
    command('init', {'schema': 1, **{k: dossier[k] for k in TASK_FIELDS},
                    'workstreams': [{'id': stream, 'questions': ['Validate this submitted evidence.']}],
                    'supplied_sources': supplied, 'max_investigators': 1,
                    'execution_mode': 'sequential'})
    registered = command('register', {'workstream': stream, 'investigator': worker,
                                     'invocation': 'local-preflight-' + secrets.token_hex(12)})
    identity = {'workstream': stream, 'investigator': worker,
                'attempt': registered['registration']['number']}
    for source in dossier['sources']:
        command('capture', {**identity, 'source': source})
    command('finish', {**identity, 'outcome': 'completed',
                       'note': 'Local submission preflight completed; not a production invocation observation.'})
    command('accept', {'schema': 1, 'request_digest': registered['request_digest'],
                      'generation': registered['generation'], **identity,
                      'sources': dossier['sources'], 'facts': dossier['facts'],
                      'limitations': [], 'gaps': evidence_gaps(dossier)})


def refused(value, spec):
    """What the pinned helper says of a dossier, saved in a disposable case with this job's own
    captures and the task's own fields, as the parent will save it after the job. The author
    can still correct it then; afterwards a refusal would end the whole research step."""
    dossier = {**copy.deepcopy(value), **(spec.get('task') or {})}
    worker = spec.get('worker')
    if spec.get('research_mode') == 'compose':
        from studio_core.research_session import check_frozen

        frozen = check_frozen(dossier, spec)
        if frozen is None or frozen:
            return frozen or ['Synthesis needs the registered investigator evidence.']
    elif any(not isinstance(fact, dict) or fact.get('author') != worker
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
        if spec.get('research_mode') == 'evidence':
            try:
                collection_preflight(case, dossier, spec)
            except (OSError, subprocess.TimeoutExpired):
                return [UNFINISHED]
            except (ValueError, KeyError) as error:
                # check_json says how to correct it, once, after everything it found.
                return [f'Harness Research refused this evidence packet: {error}']
            return []
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
    parallel = re.fullmatch(r'research:(investigate|synthesize)-(\d+)(?:-area[123])?', str(name))
    if parallel:
        return parallel[1], int(parallel[2])
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
    groups = [attempt for _, attempt in tried if attempt.get('research_attempt')]
    if groups:
        last = max(groups, key=lambda a: a.get('started_at') or '')['research_attempt']
        tried = [(found, attempt) for found, attempt in tried
                 if attempt.get('research_attempt') == last]
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
        elif isinstance(payload.get('review_template'), dict):
            # The review is checked against its template inside the job, as the helper will.
            result.update(runtime=str(tool.runtime), review_template=payload['review_template'])
        doing = doing_words(phase, number)
        told = ('' if phase == 'author' else
                ' list_inputs names the original of each supplied source that has one: read it '
                'with read_source(source_id, original=true), as well as its capture, before you '
                'attest read_original. A source with no original: read its capture and set '
                'read_original true. If a tool cannot serve an original, set read_original to '
                'false and give the tool\'s answer as its access_error.')
        work = Work(guidance + '\n\nUse only the studio tools; the parent runs helper commands. '
                    'Read list_inputs and sources; return the requested JSON using submit_artifact '
                    'under the name research-result. Keep public queries generic and nonconfidential.'
                    + (' Build each source you return from source_outline in the task. A refusal lists '
                       'everything to correct at once: correct all of it before you hand it back.'
                       if payload.get('source_outline') else '')
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
        accepted = handed['artifacts'].get('research-result')
        # A job that spent all it was given is not a failed try: the studio stops for money.
        ended = ('kept' if accepted and outcome.reason != 'stopped' else
                 'limit' if outcome.reason == 'limit' and getattr(outcome, 'budget', False)
                 else 'failed')
        with engine.files:
            record = engine._load(root)
            engine._tried(record, name, started, outcome.seconds, ended,
                          None if ended == 'kept' else outcome.detail or None, **cost)
            engine._store(root, record)
            engine._commit(root, 'record independent research job: ' + phase)
        if not accepted or outcome.reason == 'stopped':
            # What it handed back and the checks refused says more than how the agent ended.
            refused = [problem for found in handed['problems'].values() for problem in found]
            said = (('What it handed back did not pass the checks: ' + ' '.join(refused[:3])
                     + (' And more.' if len(refused) > 3 else '')) if refused else
                    ' '.join(str(outcome.detail or '').split())
                    or 'It ended without handing anything back.')
            failure = WorkspaceError(f'Research did not finish its {phase} job in round '
                                     f'{number} of {ROUNDS}' + (f': {said}' if said else '.')
                                     + ' Saved work is kept.')
            failure.outcome = outcome   # how the job ended, for the studio's stop
            raise failure
        return accepted['text'], handed['sources']

    try:
        return Workflow(tool.runtime, tool._json).run(
            root, task, invoke, sources, readable=lambda cause: dry_read(engine, root, cause))
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
