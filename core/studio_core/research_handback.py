"""Checking a research hand-back while its job can still correct it: every studio check,
then the pinned helper itself on a disposable case.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import copy
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

from studio_core.research_checks import (
    capture_texts, citation_sources, packet_problems, review_problems, source_metadata,
    synthesis_problems, uncaptured)
from studio_core.research_paths import inside, write
from studio_core.research_schema import TASK_FIELDS, UNREADABLE


def _contract():
    """studio_core.research_contract, read when called. Callers and tests replace names on it
    (refused, collection_preflight), and a call made from here reaches what they put there."""
    from studio_core import research_contract
    return research_contract


UNFINISHED = ('The pinned Harness Research collection check could not finish. This submission was '
              'not accepted; do not treat report validation as collection approval.')
# Said once, after everything a refused evidence packet needs corrected: a paragraph of its
# own after the list (see tailed), not one of its items.
TAIL = ('Correct all of these and resubmit within this job. Facts contain only id, statement, '
        'author and citations; citations contain source, quote and optional locator. Do not '
        'remove a kind label to turn an inference into a fact; retain unsupported or inferred '
        'material as a gap for synthesis. Captured evidence is unchanged.')


# Said once, after everything a refused synthesis needs corrected.
SYNTHESIS_TAIL = ('Correct all of these and hand the whole synthesis back within this job. The '
                  'registered evidence is kept unchanged.')


def tailed(problems, tail):
    """Problems with a closing paragraph of guidance after the last, said once: a list shows
    it after its items, not as one of them."""
    return problems[:-1] + [problems[-1] + '\n\n' + tail] if problems else problems


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
    composed = mode in ('compose', 'compose-section', 'compose-final')
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
                    # Check the rest as well: the sources and facts, when they are arrays, and the
                    # gaps when they are not what was wrong.
                    rest = {key: value[key] for key in ('schema', 'sources', 'facts', 'gaps') if key in value}
                    try:
                        value = preparation(rest, spec)
                    except ValueError as again:
                        if str(again) not in problems:
                            problems.append(str(again))
                        rest.pop('gaps', None)
                        value = preparation(rest, spec)
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
                if not composed:
                    texts = capture_texts(value['sources'], captures, spec.get('folder'))
                    found, flawed_sources, flawed_facts = packet_problems(
                        value, texts, spec['runtime'], spec.get('worker'), mode)
                    problems += found
                if mode != 'evidence':   # A synthesis, or a whole dossier: its prose too.
                    problems += synthesis_problems(value, spec['runtime'], shaped=composed)
                if not problems:
                    problems += _contract().refused(value, spec)
                elif mode == 'evidence':
                    problems += aside(value, spec, captures, flawed_sources, flawed_facts)
            if mode == 'evidence' and any(problem != UNFINISHED for problem in problems):
                problems = tailed(problems, TAIL)
            elif composed and problems:
                problems = tailed(problems, SYNTHESIS_TAIL)
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
    return _contract().refused({**value, 'sources': sources, 'facts': facts}, spec)


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
    # One capture for every source when the helper takes them together, as the research
    # run does (research_session.Workflow.capture_sources); one each from an older helper.
    if dossier['sources'] and registered.get('batch_capture'):
        command('capture', {**identity, 'sources': dossier['sources']})
    else:
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
    if spec.get('research_mode') in ('compose', 'compose-section', 'compose-final'):
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
                _contract().collection_preflight(case, dossier, spec)
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
