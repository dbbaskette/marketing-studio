"""Schema-2 Harness Research integration. The helper owns research semantics and exports.

Studios supply bounded, separate author/reviewer invocations. Existing schema-1
runs never enter this adapter. No provider, installation or shared setting is
changed here.
"""
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess   # callers and tests reach it through this module (research_contract.subprocess)
import tempfile

if __name__ == '__main__':
    # A direct file invocation starts with studio_core itself on the import path.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Moved into focused modules beside this one; every name stays importable from here, and
# the names callers and tests replace are read from here at call time.
from studio_core.research_paths import (
    inside, write)
from studio_core.research_runtime import (
    SHARED, RESULTS, answered, HELPER_SECONDS, HELPER_TICK, HELPER_STOPPED, run_helper,
    capability, stable, stable_place, find_runtime)
from studio_core.research_bundle import (
    OWNER, CASE, ARTIFACTS, working_case, output_root, snapshot_name, read_bundle, publish,
    case_files, adopt_case, copy_case)
from studio_core.research_review import (
    ReviewRefused, CheckCouldNotFinish, unreadable_originals, shortened, objections, NOUNS,
    grouped, took)
from studio_core.research_schema import (
    TASK_FIELDS, LIMITS_VERIFIED_WITH, TEXT_LIMIT, LIMITS, HOST_FIELDS, WHEN_PRESENT,
    MEANING, UNREADABLE, OUTLINED, GIVEN, KEPT, JS_SPACE, _SCHEMAS, _SCHEMAS_HELD, _schema,
    pinned, conditions, permission_of, js_blank, source_outline, js_length, wrong_text,
    identifier, SYNTHESIS_RULES, SYNTHESIZED, REVIEW_RULES, REVIEWED, ID_PATTERN,
    pinned_schema, described, fields, synthesis_outline, review_outline)
from studio_core.research_checks import (
    capture_texts, clipped, packet_problems, source_metadata, repeated, within, distinct,
    block_problems, refs_problems, synthesis_problems, review_problems, citation_sources,
    uncaptured)
from studio_core.research_handback import (
    UNFINISHED, TAIL, SYNTHESIS_TAIL, tailed, check_json, aside, collection_preflight,
    refused)
from studio_core.research_jobs import (
    ROUNDS, LEGACY_JOBS, job_name, job_round, doing_words, last_rounds)


IDS_FOR_QUESTIONS = ('Planning questions have IDs. A finding that answers one has an ID '
                     "that begins with that question's ID and two hyphens, such as "
                     'instance-min--capacity. Keep each ID within 64 characters.')

# What every writer that receives research is told of it, once.
HANDOFF = ('Read the research brief first: it says what matters for this piece and how it was reviewed. '
           'Creator-approved research may contain flagged material: preserve its selected warnings and all source '
           'qualifications, never present it as independently verified, and never reuse excluded claims. Do not add verification warnings to content the creator included without a warning. '
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


NOT_INSTALLED = ('Harness Research is not installed on this computer, so research cannot continue. '
                 'Install it, then try again. Saved research is kept.')


def snapshot(tool=None):
    """Select the installed capability once; an older helper retains the old adapter."""
    try:
        return capability(Path(tool.runtime) if tool else find_runtime())
    except (OSError, ValueError, AttributeError, KeyError):
        return None


def runtime_for(saved=None, runtime=None):
    """The installed helper, which every run uses whichever version it started on: its
    stable address, never a version folder an update removes. None when no Harness Research
    with synthesis is installed. `saved` is accepted and not compared."""
    try:
        found = Path(runtime) if runtime else find_runtime()
        return found if capability(found) is not None else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def matching(tool, saved=None):
    """`tool`, the installed helper, for a run started on any version of it. None only when
    no Harness Research with synthesis is installed. `saved` is accepted and not compared."""
    return tool if snapshot(tool) is not None else None


class Workflow:
    def __init__(self, runtime=None, call=None):
        self.runtime = Path(runtime) if runtime else find_runtime()
        self.call = call
        # The research run's Stop, when one is set: a helper command this runs itself (with
        # no `call`) and that is running when it comes is ended (`run_helper`).
        self.cancelled = None

    def command(self, case, action, file=None, worker=None, *, reuse_context=None):
        args = ['synthesis', action, '--project', str(case)]
        if file:
            args += ['--file', file, '--worker', worker]
        if reuse_context is not None:
            if action != 'save': raise ValueError('Reuse context is only valid for synthesis save.')
            args += ['--reuse-unchanged', '--context', str(reuse_context)]
        if self.call:
            return self.call(*args)
        node = shutil.which('node')
        if not node:
            raise ValueError('Harness Research needs the bundled Node.js runtime.')
        result = run_helper([node, str(self.runtime / 'scripts/harness-research.mjs'), *args],
                            HELPER_SECONDS, self.cancelled)
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
                dossier, status, sources = self._author(case, task, invoke, sources, rounds)
            elif self._review(case, task, invoke, sources, dossier, status, rounds, readable):
                break
        verified = self.command(case, 'verify')
        if verified.get('status') != 'complete' or verified.get('artifact_integrity') == 'failed':
            raise ReviewRefused(objections(case), ROUNDS, grouped(case))
        facts, manifest = read_bundle(case / 'research')
        return facts, manifest

    def _author(self, case, task, invoke, sources, rounds):
        """One round's authored dossier, saved by the helper: (the dossier, the helper's status,
        the sources the checker is offered, which are the exact captures saved in it)."""
        phase = 'author'
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
        outline = source_outline(sources, self.runtime, GIVEN if rounds == 1 else KEPT)
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
        return dossier, status, sources

    def _review(self, case, task, invoke, sources, dossier, status, rounds, readable):
        """One round's independent check of the saved dossier: True when the helper calls the
        research complete, False when the author is to correct it."""
        phase = 'review'
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
            return True
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
        return False


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
    # Every run uses the installed helper, whichever version it started on, and its record
    # says so from now on.
    from studio_core.research_transport import move_to_installed
    move_to_installed(engine, root, engine._load(root), product)
    tool = matching(engine.research())
    if tool is None:
        raise WorkspaceError(NOT_INSTALLED)
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
        ended = 'kept' if accepted and outcome.reason != 'stopped' else 'failed'
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
