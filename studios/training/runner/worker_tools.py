"""The tools a worker is given, and the server that offers them to an agent.

What a caller needs to know
---------------------------
A worker has no shell and no files. It can only call these tools, and what it hands back is
checked here before anything is kept. Each job has a folder that only the runner writes to:

    job.json      what the job may read and must hand back, written by prepare()
    inputs/       the job's inputs, one file each
    sources/      saved sources: index.json, a text snapshot of each, and its original
    accepted/     what the worker handed back and the checks let through
    shown/        a deck's job: the pictures of its last preview, one a slide, by number
    state.json    how often each thing was handed back, and why the last one was refused
    tools.log     every call, one JSON object a line

    prepare(folder, inputs=, artifacts=, finding=, sources=, fetch=, ask=, research=, ...)
                           set a job up
    command(folder)        the command an agent starts the server with
    WorkerTools(folder)    the same tools in this process; every tool answers (ok, text)
    collect(folder)        what was handed back, for the engine to keep

- `artifacts` maps each draft the job hands back to {'kind': ...}. The kind chooses the
  validator (VALIDATORS), and each validator is the core's own check. A 'blueprint' also
  takes 'level' and 'findings' (finding ID to verdict). A 'research-plan' takes 'scope' and
  'sources': the worker supplies the topic and the questions, and the runner fills in the
  rest, so what is kept is the whole plan. A 'document' takes 'blueprint', its blueprint's
  text. A 'brief' takes 'brief_kind' and 'findings'. A 'scenario' takes 'label', its name
  in the core without a level, and 'mode', the mode the practice plan gives it. A 'yoodli'
  takes 'label', 'profile' (the Yoodli profile, parsed), 'scenario' (its scenario's text)
  and 'objectives' (the blueprint's objective IDs); the length each field states is put in
  for the worker, so nobody counts characters by eye.
- A check that cannot run for want of one of these is recorded as unavailable, for the gate.
  It is not held against the worker.
- `finding` is the ID of the one research question the job answers. An accepted finding is in
  the shape `harness-research record` takes, with each quote's place worked out here.
- `sources` are documents offered before the job starts: {'title', 'origin', 'text', 'file',
  'supplied'}, where `file` is the snapshot's path in the training and `supplied` is the
  document's ID in the research plan, if it has one.
- Saved sources are named after their content, under sources/, so the engine can copy a
  job's sources into a training's own sources/ and a finding's `file` stays true.
- `fetch` lets the job save pages. Only public http and https addresses are fetched: every
  address a name has must be public, each redirect is checked again, and the connection
  goes to the address that was checked. Where a computer reaches the web through a proxy,
  the proxy connects instead; if that computer cannot look names up itself, nothing is
  fetched.
- `research` is where the job's research may look, as the run pinned it: {'documents',
  'sites', 'web'} (see `studio_core.research_sites`). With your sites on and the public web
  off, a page is saved only from under one of the sites, and every hop is asked again, so a
  redirect off the sites is refused too; the refusal names the sites, and `collect` lists
  each refused address under `outside`. With the public web on, any public page may be
  saved. A job prepared without `research`, as older ones were, may save any public page.
  The private-address refusals above hold whatever is chosen. Every address is checked
  and sent without its fragment, so a '#' cannot hide a path from the checks, and at most
  MAX_SOURCES refused addresses are listed.
- A draft or a finding can be handed back SUBMISSIONS times. After that, treat the job as
  failed: `collect(folder)['problems']` says why the last one was refused.
- A question (`ask_person`) ends the job: every later call is refused. Pass `ask=False`
  for a job nobody can answer, such as one research question among many.
- A tool's answer may carry pictures. It is then a `Shown`: the same (ok, text) pair, with
  the PNG files to show after the text in `.pictures`. The server sends each as an image.
- A deck's jobs have tools of their own, and these and no others beside the inputs:
  an 'outline' (what each slide says) has `check_outline` and `submit_outline`, and
  `search_icons` when its design names icons by their library IDs; a 'section'
  (some slides, drawn) has `check_section`, `preview_section`, `search_icons` and
  `submit_section`, and `list_assets` and `request_asset` when its deck's slides tool keeps
  the deck's assets; a review, set up with `review=`, has `look_at_slide`,
  `submit_assessment` and `submit_coverage`. `look=` gives any job slides to look at.
- An 'outline' takes 'brand' (the exported brand contract's path) and 'blueprint' (its
  text). It is checked with the slides tool's own check and with `deck.rules`. With 'design'
  true, `check_outline` and `submit_outline` take the slides' design beside the outline: it
  is checked with `deck.design_rules`, and the proposal `deck.proposal` makes of the two is
  proposed to the slides tool in a project of the job's own, which is removed after. What
  is kept is then {'outline', 'design'}, the design being that proposal. With 'icons' true
  as well, that proposal is checked against the brand, each icon named by its library ID.
  No tool answers the tool's question about a design: that is the person's, on the page.
  A 'section'
  takes 'brand' and what `deck.fixed` returned, and how its previews are taken:
  'previews' (how many it has), 'renderer', 'lock' and 'kept'. It is checked with
  `deck.kept` and with the slides tool's compiler. What is handed in must be the version
  last previewed; a hand-in that is not costs nothing and is sent back. A deck drawn from
  its approved design adds 'design', the design project, and 'section': its sections are
  then compiled and previewed against that design, each intent written as it was approved
  unless the tool compares intents whatever the order of their keys (`canonical-digests`).
  One whose tool keeps the deck's assets adds 'assets': {'project', 'generated', 'icons'?},
  the design project and each generated candidate of its own generated-art slides, by asset
  ID, with its slide, and 'icons' 'asset' where a recorded icon is placed by its asset ID.
  Its composer may list what is recorded, record a brand icon by its library ID, and have
  the tool's own image provider make those candidates, GENERATIONS times at most. It can
  never add a file, or answer for the person.
- Previews are taken one at a time on this computer, whatever is drawn side by side:
  `render` waits for the file named by 'lock'. 'kept' names the file that remembers the one
  preview file a deck keeps in Google Drive, so that it is written again and no second
  one is made. `reviewed` renders a whole deck for its review against its design the same
  way, through that file where the tool can render a review through Drive.
- `review` is {'preview', 'deck', 'slides', 'objectives', 'recorded'}: the previewed deck's
  folder and hash, its slides as {'number', 'id', 'title', 'image'}, the blueprint's
  objective IDs, and where an accepted assessment is also kept. The slides tool takes one
  assessment for one render, so one that is already there stands.
- A review of a deck against its approved design adds 'judged' to `review`: {'output',
  'revision', 'binding', 'packets'}, the slides tool's review folder, the revision of it the
  reviewer answers, what an assessment of it is bound to, and each slide's packet as `review
  --slide` gave it. Such a reviewer hands in with `submit_judgements` instead of
  `submit_assessment`: every criterion of every slide, checked whole by `deck.judged`. The
  tool is then told the slides were looked at, and given the assessment; what it refuses goes
  back to the reviewer, and what it leaves unresolved is kept as the findings, with the
  direct-text slides it accepted.
- A section drawn again after such a review adds 'beyond': its composer may name, with
  `submit_section`, the slides it cannot put right without another concept or other words.
  They are kept for the runner, which takes them back to the person.
- `runtimes` is {'slides', 'brand'}: the folders of the slides tool and of the brand skill
  the engine itself uses, from each wrapper's `runtime`. The server runs apart from the
  runner, and makes its own wrappers of those same two. A job with no deck is given none.
- Nothing a deck's tool answers names a folder on this computer.
"""
from __future__ import annotations

# ruff: noqa: F821  names bound from studio_core.shared_runner are unseen by a linter;
# test_shared_runner_use checks the bound parts, and the suites call the rest.

import argparse  # noqa: F401  read by the shared parts
import base64  # noqa: F401  read by the shared parts
import functools  # noqa: F401  read by the shared parts
import hashlib  # noqa: F401  read by the shared parts
import html.parser
import http.client
import inspect  # noqa: F401  read by the shared parts
import ipaddress  # noqa: F401  read by the shared parts
import json
import os
import re
import secrets
import shutil
import socket  # noqa: F401  read by the shared parts
import ssl  # noqa: F401  read by the shared parts
import subprocess  # noqa: F401  read by the shared parts
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib  # noqa: F401  read by the shared parts
from contextlib import contextmanager
from pathlib import Path

if not __package__:  # started as the server, by its path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runner  # noqa: F401,E402  puts the core on the import path
import checks  # noqa: E402
import home  # noqa: E402
from workspace import BRIEF_KINDS, WorkspaceError  # noqa: E402
from studio_core import research_sites  # noqa: E402
from studio_core.research_contract import check_json as check_research_json  # noqa: E402

from runner import deck  # noqa: E402

from studio_core import modules  # noqa: E402
from studio_core.shared_runner import worker_tools as _shared  # noqa: E402
PRODUCT, ITEM, ITEMS = 'Training Studio', 'training', 'trainings'
modules.bind(globals(), _shared, _shared.NAMES)

GENERATIONS = 2         # pictures one composer may have made: each one costs money
BRIEF = (20, 4000)      # the shortest and longest brief for a picture, in characters
ASSET_ID = re.compile(r'^\w[\w.:-]{0,127}$', re.ASCII)
ICON_ID = re.compile(r'^[\w.-]{1,80}$', re.ASCII)


class Refusal(WorkspaceError):
    """A tool's "no", in a sentence the worker can act on."""


# --- text ------------------------------------------------------------------------------


class _Page(html.parser.HTMLParser):
    """The readable text of a web page, and its title."""
    SKIP = {'script', 'style', 'noscript', 'svg', 'head', 'template'}
    BREAK = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section',
             'article', 'pre', 'table', 'blockquote', 'dt', 'dd'}


modules.bind(globals(), _shared, methods={'_Page': _shared.METHODS['_Page']})


# --- fetching --------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects come back as answers, so each new address is checked before it is used."""


modules.bind(globals(), _shared, methods={'_NoRedirect': _shared.METHODS['_NoRedirect']})


QUESTIONS = 30


def check_research_plan(plan, most=QUESTIONS):
    return checks.check_research_plan(plan, most=most)


# --- validators ------------------------------------------------------------------------


def as_kept(text: str) -> str:
    """A draft as it is kept: ending in one line end."""
    return text.rstrip('\n') + '\n'


def check_blueprint(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A blueprint, against the core's own lint. A check that could not run is recorded
    for the gate, not held against the worker."""
    report = checks.lint_blueprint(text, spec.get('findings'), spec.get('level'))
    return held(report['checks']), report['checks'], report['warnings'], as_kept(text)


def _untouched(text, spec, codec):
    protected = spec.get('untouched') or {}
    if not protected:
        return []
    try:
        sections = {s['heading']: s['text'] for s in codec.split(text)['sections']}
    except ValueError:
        sections = {}
    return [f'Section "{heading}" is not touched by the plan change. Copy it exactly.'
            for heading, original in protected.items()
            if sections.get(heading) != original]


def _check_update(text, spec, codec, kind):
    """Validate a whole update against the same boundaries as section submissions."""
    from runner import draft_jobs
    from studio_core.drafting import basis
    context = spec.get('update_check')
    if not context:
        return [], [], text
    before = context['material']
    try:
        old, new = codec.split(before), codec.split(text)
        if [s['heading'] for s in old['sections']] != [s['heading'] for s in new['sections']]:
            raise ValueError('Keep the section headings and their order exactly.')
        problems = []
        protected = spec.get('untouched') or {}
        for old_part, new_part in zip(old['sections'], new['sections']):
            if old_part['heading'] in protected and any(
                    old_part.get(key) != new_part.get(key) for key in ('covers', 'findings')):
                problems.append(f'Section "{old_part["heading"]}" is not touched by the plan change. Copy it exactly.')
        for part in new['sections']:
            codec.vet(part['id'], part['text'])
            if not part.get('locked'):
                basis.no_heading(part['text'], codec)
        original_source = next((s for s in old['sections'] if s.get('locked')), None)
        source = next((s for s in new['sections'] if s.get('locked')), None)
        if (original_source is None) != (source is None) or (source and source['text'] != original_source['text']):
            problems.append(draft_jobs.SOURCES)
        allowed = set(checks._sources(before)[1]) | {f['number'] for f in context['references']}
        unknown = {int(n) for n in checks.REFERENCE.findall(checks._sources(text)[0])} - allowed
        problems += [f'Cite only the references you were given: [{n}] is not one of them.'
                     for n in sorted(unknown)]
        for part in new['sections']:
            if not part.get('locked'):
                draft_jobs.append_sources(new, context['references'], part['text'], kind)
        kept = codec.join(new)
        old_words = [old.get('opening', '')] + [s['text'] for s in old['sections'] if not s.get('locked')]
        new_words = [new.get('opening', '')] + [s['text'] for s in new['sections'] if not s.get('locked')]
        added = [paragraph for value, prior in zip(new_words, old_words)
                 for paragraph in re.split(r'\n\s*\n', value)
                 if paragraph.strip() and paragraph not in prior]
        outcome = checks.citations(kept, kind, added=added, names=context.get('names') or ())
        problems += [p for p in held([outcome]) if not p.startswith('Sources entry ')]
        return problems, [outcome], kept
    except ValueError as error:
        return [str(error)], [], text


def check_document(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A learner guide, against the core's coverage check and the blueprint it teaches.
    Without the blueprint the check cannot run, which is recorded for the gate."""
    if isinstance(spec.get('blueprint'), str):
        outcome = checks.document_coverage(checks.parse_blueprint(spec['blueprint']), text)
    else:
        outcome = checks.result('document.coverage', [], unavailable=(
            'The blueprint was not given, so coverage could not be checked.'))
    from runner import drafts
    problems, extra, kept = _check_update(text, spec, drafts.GuideCodec(), 'document')
    return held([outcome]) + _untouched(text, spec, drafts.GuideCodec()) + problems, [outcome, *extra], [], as_kept(kept)


def check_brief(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A brief, against the core's own check of its sections and the findings they name.
    Without the findings the second cannot run, which is recorded for the gate."""
    outcomes = checks.check_brief(text, spec.get('brief_kind') or BRIEF_KINDS[0],
                                  spec.get('findings'))
    from runner import drafts
    problems, extra, kept = _check_update(text, spec, drafts.BriefCodec(), 'brief')
    return held(outcomes) + _untouched(text, spec, drafts.BriefCodec()) + problems, [*outcomes, *extra], [], as_kept(kept)


def check_part(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """Splice a worker's words into the full material before running its checks."""
    from runner import draft_jobs, drafts
    from studio_core.drafting import basis
    heading = spec['heading']
    problems = []
    if any(checks.SOURCES_HEADING.match(line) for line in text.splitlines()):
        problems.append(draft_jobs.SOURCES)
    first = text.strip().split('\n', 1)[0]
    kind = spec['name'].partition('@')[0]
    if kind == 'brief' and first.startswith('## ') and first != '## ' + heading:
        problems.append(f"Keep this section's heading exactly: {heading}.")
    cleaned = text.strip() if spec.get('selection') else basis.clean(text, heading)
    allowed = set(checks._sources(spec['material'])[1]) | {f['number'] for f in spec['findings']}
    problems += [f'Cite only the references you were given: [{n}] is not one of them.'
                 for n in sorted({int(n) for n in checks.REFERENCE.findall(cleaned)} - allowed)]
    try:
        codec = drafts.codec_of(spec['name'])
        basis.no_heading(cleaned, codec)
        codec.vet(spec['part'], cleaned)
        whole, added_text = draft_jobs.spliced(spec, cleaned)
    except ValueError as error:
        return [*problems, str(error)], [], [], text
    checked_spec = {**spec, 'findings': spec.get('finding_statuses')}
    _, outcomes, warnings, _ = (check_brief if kind == 'brief' else check_document)(whole, checked_spec)
    # Dropping a reference is allowed. Unused Sources are reported on the card, while
    # unknown references and unsupported new claims are handed back for correction.
    added = [p for p in re.split(r'\n\s*\n', added_text) if p.strip() and p not in spec['before']]
    cited = checks.citations(whole, kind, added=added, names=spec.get('names') or ())
    outcomes.append(cited)
    problems += [p for p in held(outcomes) if not p.startswith('Sources entry ')]
    return problems, outcomes, warnings, as_kept(cleaned)


def check_scenario(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A practice scenario, against the core's own check of its shape. A mode other than
    the practice plan's is noted for the reviewer: the scenario file decides."""
    outcome = checks.check_scenario(text, spec.get('label') or 'scenario:main')
    stated, planned = checks.parse_scenario(text)['mode'], spec.get('mode')
    warnings = [] if not planned or stated == planned else [
        f'The practice plan lists this scenario as {planned}; the file says {stated}. The '
        'scenario file decides.']
    return held([outcome]), [outcome], warnings, as_kept(text)


def counted(text: str) -> str:
    """A Yoodli scenario with the real length of each field put where the file states one,
    as in "666 of 10,000 characters". The limit beside it is left as the worker wrote it."""
    fields, _ = checks.fenced_fields(text)
    lines, path, inside = [], [], False
    for line in text.splitlines():
        if line.startswith('```'):
            inside = not inside
        elif not inside:
            head = checks.HEADING.match(line)
            if head:
                path = path[:len(head.group(1)) - 2] + [head.group(2)]
            elif tuple(path) in fields:
                size = f'{len(fields[tuple(path)]):,}'
                line = checks.STATED_COUNT.sub(
                    lambda stated: size + stated.group(0)[len(stated.group(1)):], line, count=1)
        lines.append(line)
    return '\n'.join(lines) + '\n'


def check_yoodli(text: str, spec: dict) -> tuple[list[str], list[dict], list[str], str]:
    """A Yoodli scenario, against the core's own check with the Yoodli profile: its fields,
    its goals, each count against its limit, and that every success criterion has a goal.
    What cannot be checked for want of the profile, the scenario or the objectives is
    recorded for the gate."""
    label, profile = spec.get('label') or 'yoodli:main', spec.get('profile')
    if not isinstance(profile, dict) or not isinstance(profile.get('limits'), dict):
        outcomes = [checks.result(f'{label}.{part}', [], unavailable=(
            'The Yoodli profile was not given, so this could not be checked.'))
            for part in ('fields', 'limits', 'mapping')]
        return [], outcomes, [], as_kept(text)
    text = counted(text)
    scenario = (checks.parse_scenario(spec['scenario'])
                if isinstance(spec.get('scenario'), str) else None)
    objectives = set(spec['objectives']) if isinstance(spec.get('objectives'), list) else None
    outcomes = checks.check_yoodli(text, profile, scenario, objectives, label)
    return held(outcomes), outcomes, [], as_kept(text)


def check_outline(text: str, spec: dict, slides,
                  scratch: Path) -> tuple[list[str], list[dict], list[str], str]:
    """An outline: what each slide of a deck says. The slides tool checks its shape and
    its own limits, and the runner's own rules are checked on top, with the tool's budget
    of words counted against everything a slide shows. With 'design', the outline comes with
    its design as {'outline', 'design'}, and the proposal made from the two is checked too."""
    try:
        outline, kept = as_json(text, 'outline')
    except Refusal as refusal:
        return [str(refusal)], [], [], text
    if spec.get('design'):
        given = outline if isinstance(outline, dict) else {}
        outline, kept = given.get('outline'), as_json(given.get('outline') or {}, 'outline')[1]
        design = given.get('design')
    budget = spec.get('budget')
    # The tool checks the outline without the short labels a point gives its diagram.
    known, shown = frozenset(), outline
    try:
        known = slides.knows() if hasattr(slides, 'knows') else frozenset()
        shown = deck.for_tool(outline, known)
        told = kept if shown == outline else json.dumps(
            shown, indent=2, ensure_ascii=False) + '\n'
        report = slides.outline_check(_draft(scratch, 'outline', told), spec['brand'])
    except WorkspaceError as refusal:
        found = said_no(refusal)
    else:
        budget = report.get('wordBudget') or budget
        found = [f"{finding.get('slide')}: {finding.get('detail') or finding.get('code')}"
                 for finding in report.get('findings') or ()]
    frozen = spec.get('frozen') or {}
    actual = deck.slides_of(outline)
    for number, slide in enumerate(deck.slides_of(spec.get('previous') or {}), 1):
        ident = slide.get('id')
        if ident in frozen and (number > len(actual) or actual[number - 1] != frozen[ident]):
            found.append(f'Slide {number} is not one to word again. Copy it exactly.')
    if frozen and not spec.get('previous'):
        for number, slide in enumerate(actual, 1):
            ident = slide.get('id')
            if ident in frozen and slide != frozen[ident]:
                found.append(f'Slide {number} is not one to word again. Copy it exactly.')
    outcomes = [checks.result('outline.tool', found),
                checks.result('outline.rules', deck.rules(outline, spec.get('blueprint') or '',
                                                          budget, spec.get('known') or (),
                                                          spec.get('delivery') or deck.DELIVERY))]
    if not spec.get('design'):
        return held(outcomes), outcomes, [], kept
    problems, proposed = check_design(outline, design, slides, scratch,
                                      spec['brand'] if spec.get('icons') else None)
    outcomes.append(checks.result('outline.design', problems))
    kept = json.dumps({'outline': json.loads(kept), 'design': proposed}, indent=2,
                      ensure_ascii=False) + '\n'
    return held(outcomes), outcomes, [], kept


def check_design(outline, design, slides, scratch: Path,
                 brand=None) -> tuple[list[str], dict | None]:
    """The design handed in with an outline: the runner's own rules, then the proposal made
    from the two, proposed to the slides tool in a project of its own that is thrown away,
    with `brand` when its icons are named by their library IDs, to be checked against it.
    Returns what to put right and the proposal. Nothing the tool keeps outlives the check."""
    if not deck.slides_of(outline):
        return ['The design is checked once the outline has its slides.'], None
    problems = deck.design_rules(outline, design)
    if problems:
        return problems, None
    proposed = deck.proposal(outline, design)
    project = scratch / f'design-{secrets.token_hex(4)}'
    _write(project / 'proposal.json', json.dumps(proposed, ensure_ascii=False))
    try:
        slides.design_propose(project, project / 'proposal.json',
                              brand=Path(brand) if brand else None)
    except WorkspaceError as refusal:
        found = getattr(refusal, 'found', None)
        if not found:
            return said_no(refusal), proposed
        return [_problem(problem) for problem in found], proposed
    finally:
        shutil.rmtree(project, ignore_errors=True)
    return [], proposed


def _problem(problem: dict) -> str:
    """One problem the slides tool found in a design, as the worker is told it: the slide,
    what is wrong, and the way out the tool offers when it has one."""
    slide, detail = problem.get('slide'), str(problem.get('detail') or problem.get('code'))
    line = detail if not slide or detail.startswith(f'{slide}:') else f'{slide}: {detail}'
    fallback = problem.get('fallback') or {}
    if fallback.get('proposal'):
        line += '' if line.endswith(('.', '?', '!')) else '.'
        line += (f" Instead, you may propose this, which the person approves like the rest: "
                 f"{fallback['proposal']}.")
    return line


def against(how: dict) -> dict:
    """What compile and preview are given to check slides against the approved design:
    nothing for a deck without one."""
    if not how.get('design'):
        return {}
    return {'design': Path(how['design']), 'section': bool(how.get('section'))}


def outlined(spec: dict) -> dict:
    """What compile is given of the approved outline a section is drawn from, so that a
    tool that can finds a point's sentence split across shapes: nothing without one."""
    return {'outline': Path(spec['outline'])} if spec.get('outline') else {}


def check_section(text: str, spec: dict, slides,
                  scratch: Path) -> tuple[list[str], list[dict], list[str], str]:
    """A section: some slides of a deck, drawn. What was fixed before its composer started
    must be as it was, with every approved word kept, and the slides tool must compile it."""
    try:
        section, kept = as_json(text, 'section')
    except Refusal as refusal:
        return [str(refusal)], [], [], text
    ours, found = deck.kept(section, spec), []
    # Checked against the approved design, as one section of it. A tool that compares an
    # intent whatever the order of its keys takes it as written; an older one, in the order
    # it was approved in.
    if spec.get('design') and not slides.has('canonical-digests'):
        section = deck.as_approved(section, spec)
        kept = json.dumps(section, indent=2, ensure_ascii=False) + '\n'
    if isinstance(section, dict):
        try:
            slides.compile(_draft(scratch, 'section', kept), spec['brand'], **against(spec),
                           **outlined(spec))
        except WorkspaceError as refusal:
            found = said_no(refusal)
    outcomes = [checks.result('section.rules', ours), checks.result('section.compile', found)]
    return held(outcomes), outcomes, [], kept


def check_slide_words(text: str, spec: dict) -> tuple:
    """A replacement passage; the complete slide is checked by its normal word chain."""
    problems = []
    if not text.strip() or len(text) > spec['limit']:
        problems.append('Return a nonempty passage within the slide field length.')
    if '\x00' in text:
        problems.append('Return plain text.')
    return problems, [], [], text.strip()


def check_finishing(text, spec):
    from runner import draft_finish
    return draft_finish.check_result(text, spec)


VALIDATORS = {'finishing': check_finishing, 'research-plan': check_plan, 'blueprint': check_blueprint,
              'document': check_document, 'brief': check_brief, 'scenario': check_scenario,
              'yoodli': check_yoodli, 'outline': check_outline, 'section': check_section,
              'part': check_part, 'slide-words': check_slide_words}
VALIDATORS['research-json'] = check_research_json


# --- pictures, and the renderer ----------------------------------------------------------

class Shown(tuple):
    """A tool's answer that carries pictures: the same (ok, text) pair every tool gives,
    with the PNG files to show after the text in `pictures`."""

    def __new__(cls, ok: bool, text: str, pictures=()):
        made = super().__new__(cls, (ok, text))
        made.pictures = tuple(Path(picture) for picture in pictures)
        return made


@contextmanager
def turn(lock: Path, slots: int = 1, wait: float = RENDER_WAIT):
    """Hold one of a computer's `slots` turns at the renderer: the file `lock` for the first,
    and `lock.1`, `lock.2`... beside it for the others, the first free taken. Whoever else
    wants one waits here, in this process or another. A turn left behind by a process that
    has ended is taken."""
    lock, until = Path(lock), time.monotonic() + wait
    lock.parent.mkdir(parents=True, exist_ok=True)
    names = [lock, *(lock.with_name(f'{lock.name}.{number}') for number in range(1, slots))]
    taken = None
    while taken is None:
        for name in names:
            try:
                handle = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    holder = name.read_text(encoding='utf-8').strip()
                except OSError:
                    continue  # let go of between the two looks
                if holder.isdigit() and not home.alive(int(holder)):
                    name.unlink(missing_ok=True)
                continue
            os.write(handle, f'{os.getpid()}'.encode())
            os.close(handle)
            taken = name
            break
        else:
            if time.monotonic() > until:
                raise Refusal('Another preview has been rendering for a long time, so this '
                              'one was not taken. Try it again.')
            time.sleep(0.05)
    try:
        yield
    finally:
        taken.unlink(missing_ok=True)


def render(slides, compiled: Path, folder: Path, how: dict) -> dict:
    """Preview compiled slides, when it is this preview's turn. `how` is {'renderer',
    'lock', 'kept', 'named'}: 'kept' names the file that remembers a deck's one preview
    file in Google Drive, which is written again each time, and 'named' is what to
    remember of it beside its ID and address. A preview that fails after it made that
    file says so in its refusal's `left`, as {'fileId', 'url'}, and the file is remembered
    all the same. Returns what the slides tool returned."""
    with turn(turn_file(how, slides), slots(how, slides)):
        return _in_drive(how, lambda known: slides.preview(
            compiled, folder, how['renderer'], file_id=known, **against(how)))


def _in_drive(how: dict, made) -> dict:
    """What `made(file_id)` renders, with the deck's one file in Google Drive remembered:
    the one it was given, written again, or the one it made. A render that failed after it
    made that file says so in its refusal's `left`, and the file is remembered all the
    same."""
    kept = Path(how['kept']) if how.get('kept') else None
    known = home.read_json(kept, {}) if kept else {}
    known = known if isinstance(known, dict) else {}

    def remember(ident, url, receipt=None) -> None:
        if kept and ident and (ident != known.get('id') or receipt != known.get('pool')):
            home.write_json(kept, {**(how.get('named') or {}), 'id': ident, 'url': url,
                                   **({'pool': receipt} if receipt else {})})

    try:
        found = made(known.get('id'))
    except WorkspaceError as refusal:  # a render that failed may have made its file
        left = getattr(refusal, 'left', None) or {}
        remember(left.get('fileId'), left.get('url'))
        raise
    # A preview in the slides tool's pool is one of its own few reusable decks: its link is
    # kept with the receipt that says which preview it holds, and once a newer preview has
    # replaced it, the link is forgotten rather than shown with someone else's slides.
    pool = found.get('pool') if isinstance(found.get('pool'), dict) else {}
    if found.get('remoteReplaced'):
        if kept:
            kept.unlink(missing_ok=True)
        return found
    remember(found.get('fileId'), found.get('url'), pool.get('receipt'))
    return found


def reviewed(slides, compiled: Path, output: Path, design: Path, how: dict) -> dict:
    """Have the slides tool render a whole deck compiled against its approved design, for
    its review against that design, when it is this computer's turn at the renderer. Where
    previews go through Google Drive and the tool can render a review there, it does, into
    the deck's one file in Drive; otherwise with LibreOffice. Returns what the tool did."""
    with one_at_a_time(Path(how['lock'])):
        if how.get('renderer') != 'drive' or not slides.has('review-google-renderer'):
            return slides.review_prepare(compiled, output, design)
        return _in_drive(how, lambda known: slides.review_prepare(
            compiled, output, design, renderer='drive', file_id=known))


# --- a job's folder --------------------------------------------------------------------

def prepare(folder: Path, inputs: dict[str, str] | None = None,
            artifacts: dict[str, dict] | None = None, finding: str | None = None,
            sources=(), fetch: bool = False, ask: bool = True, review: dict | None = None,
            look=None, runtimes: dict | None = None, research: dict | None = None) -> Path:
    """Set a job's folder up: what the worker may read, and what it must hand back.
    `research` is where its research may look; None for any public page."""
    folder = Path(folder)
    if (folder / 'job.json').exists():
        raise WorkspaceError(f'{folder} already holds a job. Give each job, and each new '
                             'attempt at one, a folder of its own.')
    if research is not None:
        if not isinstance(research, dict) or set(research) - {'documents', 'sites', 'web'} \
                or any(not isinstance(research.get(key, False), bool)
                       for key in ('documents', 'web')):
            raise WorkspaceError('Say where research may look as documents, sites and web.')
        try:
            research = research_sites.effective(
                {**research, 'sites': research_sites.sites(research.get('sites') or [])})
        except ValueError as error:
            raise WorkspaceError(str(error)) from None
    for name, spec in (artifacts or {}).items():
        if not isinstance(spec, dict) or spec.get('kind') not in VALIDATORS:
            raise WorkspaceError(f'{name} needs a kind that can be checked: one of '
                                 + ', '.join(VALIDATORS) + '.')
        if spec.get('scope') not in (None, *SCOPES):
            raise WorkspaceError(f"{name}: the scope is one of {', '.join(SCOPES)}.")
        if spec.get('brief_kind') not in (None, *BRIEF_KINDS):
            raise WorkspaceError(f"{name}: the kind of brief is one of "
                                 f"{', '.join(BRIEF_KINDS)}.")
        if spec['kind'] in DRAWN and not spec.get('brand'):
            raise WorkspaceError(f'{name} needs the brand it is checked against.')
    if review is not None and not all(review.get(key) for key in (
            'preview', 'deck', 'slides', 'recorded')):
        raise WorkspaceError('A review needs the preview it is of, its deck, its slides '
                             'and where its assessment is kept.')
    if finding is not None and not QUESTION_ID.match(finding):
        raise WorkspaceError(f'"{finding}" is not a research question ID.')
    listed = []
    for number, (name, text) in enumerate((inputs or {}).items(), start=1):
        _write(folder / 'inputs' / f'{number}.txt', text)
        listed.append({'name': name, 'file': f'inputs/{number}.txt', 'chars': len(text)})
    index = [_offered(folder, number, source)
             for number, source in enumerate(sources, start=1)]
    home.write_json(folder / 'sources' / 'index.json', index)
    home.write_json(folder / 'job.json', {
        'schema': SCHEMA, 'inputs': listed, 'artifacts': artifacts or {}, 'finding': finding,
        'fetch': bool(fetch), 'ask': bool(ask), 'review': review,
        'look': list(look or (review or {}).get('slides') or ()),
        'runtimes': dict(runtimes or {}), 'prepared_at': home.now(),
        **({'research': research} if research is not None else {})})
    return folder


def command(folder: Path) -> list[str]:
    """The command that starts the tools server for one job. It runs apart from whatever
    Python settings the agent's environment carries."""
    return [sys.executable, '-I', str(Path(__file__).resolve()), '--job',
            str(Path(folder).resolve())]


def collect(folder: Path) -> dict:
    """What a job handed back and the checks let through, read from its folder.

    `artifacts` maps each accepted draft to its kind, text, checks and warnings. `sources`
    lists every source with `path`, where its snapshot is in the job's folder, and `file`,
    where a finding says it is in the training. `problems` holds why the last hand-back of
    anything not accepted was refused. `outside` lists each address a page was refused
    at for being outside the sites this research may use. For a deck's jobs, `shown` is the last preview a
    composer took, as {'previews', 'slides'} with each slide's picture at `path`;
    `assessment` and `coverage` are what a reviewer handed in, and `beyond` the slides a
    composer drawing again named as needing more than drawing, as {'slide', 'why'}.
    """
    folder = Path(folder)
    _job(folder)
    kept = folder / 'accepted'
    artifacts = {}
    for name, entry in home.read_json(kept / 'artifacts.json', {}).items():
        path = folder / entry['file']
        artifacts[name] = {**entry, 'path': path, 'text': path.read_text(encoding='utf-8')}
    review, asked = kept / 'review.md', home.read_json(kept / 'question.json', None)
    sources = []
    for entry in home.read_json(folder / 'sources' / 'index.json', []):
        original = entry.get('original')
        sources.append({**entry, 'path': folder / entry['local'],
                        'original_path': folder / original if original else None})
    state = home.read_json(folder / 'state.json', {})
    shown = None if not state.get('shown') else {
        'previews': state.get('previews', 0),
        'slides': [{**slide, 'path': folder / 'shown' / f"{slide['number']}.png"}
                   for slide in state['shown']]}
    return {'artifacts': artifacts, 'shown': shown,
            'assessment': home.read_json(kept / 'assessment.json', None),
            'coverage': home.read_json(kept / 'coverage.json', None),
            'beyond': home.read_json(kept / 'beyond.json', []),
            'review': review.read_text(encoding='utf-8') if review.is_file() else None,
            'finding': home.read_json(kept / 'finding.json', None),
            'question': asked.get('question') if isinstance(asked, dict) else None,
            'sources': sources,
            'outside': list(state.get('outside') or ()),
            'problems': {name: found for name, found
                         in state.get('problems', {}).items() if found}}


# --- the tools -------------------------------------------------------------------------


class WorkerTools:
    """One job's tools. `opener`, `resolver` and `pdf` are replaceable, so tests never
    touch the network or need a PDF reader."""

    # --- bookkeeping ---


    def offered(self) -> list[dict]:
        """The tools this job has a use for, as an agent is told about them."""
        job, names = self.job, ['list_inputs', 'read_input']
        kinds = {spec['kind'] for spec in job['artifacts'].values()}
        if 'outline' in kinds:
            names += ['check_outline', 'submit_outline', 'submit_review']
            if any(spec.get('icons') for spec in job['artifacts'].values()):
                names.append('search_icons')
        elif 'part' in kinds:
            names += ['submit_part']
        elif 'section' in kinds:
            names += ['check_section', 'preview_section', 'search_icons', 'submit_section']
            if any(spec.get('assets') for spec in job['artifacts'].values()):
                names += ['list_assets', 'request_asset']
        elif job['artifacts']:
            names += ['submit_artifact', 'submit_review']
        if job.get('look'):
            names.append('look_at_slide')
        if job.get('review'):
            names += ['submit_judgements' if job['review'].get('judged')
                      else 'submit_assessment', 'submit_coverage']
        if job['fetch']:
            names.append('save_source')
        if job['fetch'] or self._index():
            names += ['read_source', 'search_source']
        if job['finding']:
            names.append('submit_finding')
        if job['ask']:
            names.append('ask_person')
        return [entry for entry in TOOLS if entry['name'] in names]

    # --- inputs ---

    @tool
    def list_inputs(self):
        """What the job was given to read."""
        lines = []
        for entry in self.job['inputs']:
            count = len(parts(self._input(entry)))
            lines.append(f"- {entry['name']}: {entry['chars']:,} characters"
                         + (f', in {count} parts' if count > 1 else ''))
        saved = [f"- {entry['id']}: \"{entry['title']}\", {entry['chars']:,} characters; capture: {entry['file']}; origin: {entry['url']}"
                 + self._original_named(entry) for entry in self._index()]
        if not lines and not saved:
            return True, 'This job has no inputs. Everything you need is in your task.'
        text = 'Inputs, read with read_input:\n' + '\n'.join(lines) if lines else ''
        if saved:
            text += ('\n\n' if text else '') + ('Saved sources, read with read_source and '
                                               'search_source:\n' + '\n'.join(saved))
        return True, text

    @tool
    def read_input(self, name, part=1):
        """One input, or one part of a long one."""
        wanted = str(name).strip()
        entry = next((item for item in self.job['inputs'] if item['name'] == wanted), None)
        if entry is None:
            known = ', '.join(item['name'] for item in self.job['inputs']) or 'none'
            raise Refusal(f'There is no input called "{wanted}". This job\'s inputs: '
                          f'{known}.')
        pieces, number = parts(self._input(entry)), whole(part, 'part')
        if not 1 <= number <= len(pieces):
            raise Refusal(f'"{wanted}" has {len(pieces)} part(s); there is no part '
                          f'{number}.')
        if len(pieces) == 1:
            return True, pieces[0]
        rest = (f'; ask for part {number + 1} for more' if number < len(pieces)
                else '; this is the last part')
        return True, f'[{wanted}: part {number} of {len(pieces)}{rest}]\n\n{pieces[number - 1]}'

    # --- drafts ---

    @tool
    def submit_artifact(self, name, text):
        """Hand back a draft. It is checked; what is wrong with it comes back to fix."""
        wanted = self.job['artifacts']
        if not wanted:
            raise Refusal('This job has no draft to hand back.')
        name = str(name).strip()
        if name not in wanted:
            raise Refusal(f'This job hands back {", ".join(wanted)}, not "{name}". Use '
                          'that name.')
        if not isinstance(text, str) or not text.strip():
            raise Refusal('The text is empty. Hand back the whole draft.')
        if wanted[name]['kind'] == 'part':
            raise Refusal('Hand a part in with submit_part.')
        if wanted[name]['kind'] == 'section':
            raise Refusal('Hand a section in with submit_section.')
        return self._hand_in(name, text)

    @tool
    def submit_part(self, text):
        """Hand back one part or selected passage, checked in its complete material."""
        name, _ = self._spec('part')
        if not isinstance(text, str) or not text.strip():
            raise Refusal('The text is empty. Hand back the requested words.')
        return self._hand_in(name, text)

    def _validate(self, spec: dict, text: str) -> tuple[list[str], list[dict], list[str], str]:
        """Check one draft with its kind's validator. What the slides tool says is given
        to the worker without the name of any folder here."""
        if spec['kind'] not in DRAWN:
            if spec['kind'] == 'research-json':
                # A dossier may cite only what this job saved; the author can correct it here.
                spec = {**spec, 'captures': self._index(), 'folder': str(self.folder)}
            return VALIDATORS[spec['kind']](text, spec)
        problems, ran, warnings, kept = VALIDATORS[spec['kind']](
            text, spec, self.slides(), self.folder / 'drafts')
        for outcome in ran:
            outcome['problems'] = [self._plainly(problem) for problem in outcome['problems']]
        return [self._plainly(problem) for problem in problems], ran, warnings, kept

    def _plainly(self, text: str) -> str:
        """What a tool said, without the name of a folder on this computer."""
        held = next((spec.get('assets') for spec in self.job['artifacts'].values()
                     if spec.get('assets')), None)
        if held:
            text = text.replace(str(Path(held['project']).resolve()), 'the deck') \
                .replace(str(held['project']), 'the deck')
        for folder in (self.folder / 'drafts', self.folder):
            text = text.replace(f'{folder.resolve()}{os.sep}', '').replace(str(folder), '.')
        return text.replace(str(Path.home()), '~')

    @tool
    def submit_review(self, text):
        """The worker's own notes on its draft, shown at the gate as its judgment."""
        if not self.job['artifacts']:
            raise Refusal('This job has no draft, so there is nothing to write notes on.')
        if not home.read_json(self.folder / 'accepted' / 'artifacts.json', {}):
            raise Refusal('Hand the draft back first. Write your notes once it has been '
                          'accepted.')
        if not isinstance(text, str) or not text.strip():
            raise Refusal('Your notes are empty.')
        if len(text) > NOTES:
            raise Refusal(f'Your notes are {len(text):,} characters. Keep them under '
                          f'{NOTES:,}.')
        _write(self.folder / 'accepted' / 'review.md', text.strip() + '\n')
        return True, ('Your notes were kept. The person who reviews the draft will see them '
                      'as your judgment.')

    # --- a deck: what it says ---

    def _outlined(self, outline, design) -> str:
        """An outline as it is checked: alone, or with its design when the job asks for
        one, as {'outline', 'design'}."""
        _, spec = self._spec('outline')
        if not spec.get('design'):
            if design is not None:
                raise Refusal('This outline is handed in without a design. Send the outline '
                              'alone.')
            return as_json(outline, 'outline')[1]
        if design is None:
            raise Refusal('Hand the outline in with its design: one entry for every slide, as '
                          'your guidance says.')
        return json.dumps({'outline': as_json(outline, 'outline')[0],
                           'design': as_json(design, 'design')[0]},
                          indent=2, ensure_ascii=False) + '\n'

    @tool
    def check_outline(self, outline, design=None):
        """Check a draft of the outline, with its design when the job asks for one. Nothing
        is kept."""
        return self._tried('outline', self._outlined(outline, design))

    @tool
    def submit_outline(self, outline, design=None):
        """Hand the outline in, with its design when the job asks for one. It is checked the
        same way and kept when nothing is left to put right."""
        name, _ = self._spec('outline')
        return self._hand_in(name, self._outlined(outline, design))

    # --- a deck: how it is drawn ---

    @tool
    def check_section(self, section):
        """Compile a draft of the section without rendering it. Free."""
        return self._tried('section', section)

    @tool
    def preview_section(self, section):
        """Render a draft of the section and return a picture of every slide."""
        _, spec = self._spec('section')
        most, state = spec.get('previews') or deck.PREVIEWS, self._state()
        used = state.get('previews', 0)
        if used >= most:
            raise Refusal(f'You have used all {most} previews. Hand in the version you last '
                          'previewed, with submit_section.')
        drawn, text = as_json(section, 'section')
        problems, _, _, kept = self._validate(spec, text)
        if problems:
            return False, ('Nothing was rendered, and this did not use up a preview. Put '
                           'these right first:\n- ' + '\n- '.join(problems))
        build = self.folder / 'builds' / f'{used + 1}-{secrets.token_hex(3)}'
        taken = self.folder / 'previews' / build.name
        for new in (build, taken):   # the slides tool makes a folder, and not what holds it
            new.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.slides().compile(_draft(self.folder / 'drafts', 'preview', kept),
                                  spec['brand'], folder=build, **against(spec),
                                  **outlined(spec))
            found = render(self.slides(), build, taken, spec)
            slides = pictures(found, taken, self.folder / 'shown')
        except WorkspaceError as refusal:
            lines = [self._plainly(line) for line in said_no(refusal)]
            return False, ('The slides compile but could not be rendered, and this did not '
                           'use up a preview:\n- ' + '\n- '.join(lines))
        finally:  # a build and a render hold a deck of several megabytes each
            shutil.rmtree(build, ignore_errors=True)
            shutil.rmtree(taken, ignore_errors=True)
        home.write_json(self.folder / 'state.json', {
            **self._state(), 'previews': used + 1, 'previewed': self._digest(drawn),
            'shown': [{key: slide[key] for key in ('number', 'id', 'title')}
                      for slide in slides]})
        lines = [f'Preview {used + 1} of {most}.']
        for slide in slides:
            seen = '; '.join(f"{finding.get('severity')} {finding.get('code')}: "
                             f"{finding.get('detail')}" for finding in slide['findings'])
            lines.append(f"- Slide {slide['number']}, `{slide['id']}`. The renderer found: "
                         + (self._plainly(seen) if seen else 'nothing'))
        lines.append('The pictures follow in slide order. What the renderer found is a '
                     'prompt to look, not approval: a slide with no finding is not '
                     'thereby a good one.')
        return Shown(True, '\n'.join(lines),
                     [self.folder / 'shown' / f"{slide['number']}.png" for slide in slides])

    @tool
    def search_icons(self, words, limit=5):
        """Search the brand's icons by a word or two."""
        drawn = [spec for spec in self.job['artifacts'].values() if spec['kind'] == 'section'
                 or spec['kind'] == 'outline' and spec.get('icons')]
        if not drawn:
            raise Refusal('This job has no section to work on.')
        words = ' '.join(str(words).split())
        if not words or len(words) > 80:
            raise Refusal('Search with one or two plain words.')
        found = self.brand().icons(words, min(max(1, whole(limit, 'limit')), ICONS))
        # One that is a picture cannot be placed by the slides tool, so it is not offered.
        found = [icon for icon in found if isinstance(icon, dict)
                 and icon.get('native', True) is not False]
        if not found:
            return True, (f'No icon matches "{words}". Every word has to match: try one '
                          'plain noun.')
        use = 'the icon of an icon node' if drawn[0]['kind'] == 'section' else \
            'the `ref` of an icon candidate, with "refType": "library-id"'
        return True, (f'Icons for "{words}". Use an ID as {use}:\n'
                      + '\n'.join(f"- {icon.get('id')}: {icon.get('name')}"
                                  + (f" ({icon['category']})" if icon.get('category') else '')
                                  for icon in found))

    def _assets(self) -> tuple[dict, dict]:
        """The section's particulars, and what it may do with the deck's assets."""
        _, spec = self._spec('section')
        if not spec.get('assets'):
            raise Refusal("This deck's slides tool keeps no record of its assets.")
        return spec, spec['assets']

    @tool
    def list_assets(self):
        """What the deck's asset manifest records, and how each is placed."""
        spec, held = self._assets()
        found = self.slides().asset_status(Path(held['project'])).get('assets') or []
        lines = []
        for entry in found:
            ident, kind = entry.get('assetId'), entry.get('kind')
            if kind == 'icon':
                lines.append(f"- `{ident}`: the icon `{entry.get('ref')}`"
                             + (f" ({entry['alt']})" if entry.get('alt') else '')
                             + ('. Place it as an icon node by its asset ID.'
                                if held.get('icons') == 'asset' else
                                '. Place it as an icon node with that icon ID.'))
                continue
            line = (f"- `{ident}`: a {kind} picture of {entry.get('alt') or 'what it shows'}"
                    f". Source: {entry.get('source')}."
                    + (f" Use it only so: {entry['restrictions']}."
                       if entry.get('restrictions') else ''))
            line += (' Place it by its asset ID.' if entry.get('state') == 'ok' else
                     ' Its file is not as it was recorded, so it cannot be placed: say so '
                     'when you hand in.')
            lines.append(line)
        made = {entry.get('assetId') for entry in found}
        lines += [f"- `{ident}`: generated art for `{slide}`, not made yet. Ask for it with "
                  'request_asset.' for ident, slide in held['generated'].items()
                  if ident not in made]
        if not lines:
            return True, 'Nothing is recorded for this deck yet.'
        return True, 'Recorded for this deck:\n' + '\n'.join(lines)

    @tool
    def request_asset(self, asset, icon=None, slide=None, prompt=None, alt=None):
        """Record a brand icon by its library ID, or have the slides tool make the generated
        art of one of this section's slides drawn as generated art."""
        spec, held = self._assets()
        asset = str(asset or '').strip()
        if not ASSET_ID.match(asset):
            raise Refusal('Name the asset by an ID of letters, digits, _ . : or -.')
        alt = ' '.join(str(alt).split())[:300] if alt else None
        project = Path(held['project'])
        if (icon is None) == (prompt is None):
            raise Refusal('Ask for one thing: an icon by its library ID, or generated art '
                          'with a brief.')
        if icon is not None:
            icon = str(icon).strip()
            if not ICON_ID.match(icon):
                raise Refusal('An icon is named by the ID search_icons gives.')
            try:
                made = self.slides().asset_icon(project, icon, asset, alt, Path(spec['brand']))
            except WorkspaceError as refusal:
                return False, self._unmade(refusal)
            return True, (f"`{asset}` is the icon `{made.get('ref')}`"
                          + (f" ({made['alt']})" if made.get('alt') else '')
                          + (f'. Place it as an icon node by its asset ID: {{"type": "icon", '
                             f'"id": "<your ID>", "asset": "{asset}"}}.'
                             if held.get('icons') == 'asset' else
                             '. Place it as an icon node with that icon ID.'))
        if asset not in held['generated']:
            listed = ', '.join(f'`{ident}`' for ident in held['generated']) or 'none'
            raise Refusal('Only the generated art the approved design names for your own '
                          f'slides can be made. Yours: {listed}.')
        wanted = held['generated'][asset]
        if slide is not None and str(slide) != wanted:
            raise Refusal(f'`{asset}` is the generated art of `{wanted}`, not of `{slide}`.')
        brief = ' '.join(str(prompt).split())
        if not BRIEF[0] <= len(brief) <= BRIEF[1]:
            raise Refusal(f'Write the brief for the picture in {BRIEF[0]} to {BRIEF[1]} '
                          'characters.')
        state = self._state()
        if state.get('generated', 0) >= GENERATIONS:
            raise Refusal(f'You have asked for {GENERATIONS} pictures, which is the most a '
                          'section may. Draw the rest, and say what is missing when you hand '
                          'in.')
        home.write_json(self.folder / 'state.json',
                        {**state, 'generated': state.get('generated', 0) + 1})
        try:
            self.slides().generate_image(project, asset, brief,
                                         f"assets/generated/{asset.replace(':', '_')}.png",
                                         wanted, alt)
        except WorkspaceError as refusal:
            return False, self._unmade(refusal)
        return True, (f'`{asset}` is made and recorded. Place it by its asset ID on '
                      f'`{wanted}`, and preview the section to look at it.')

    def _unmade(self, refusal: WorkspaceError) -> str:
        """Why the slides tool did not record an asset, as its composer is told it: each
        problem, the provider it concerns, and what the tool says to do."""
        found = getattr(refusal, 'found', None) or []
        if not found:
            return 'Not recorded:\n- ' + '\n- '.join(self._plainly(line)
                                                     for line in said_no(refusal))
        lines = []
        for problem in found:
            line = self._plainly(str(problem.get('detail') or problem.get('code')))
            if problem.get('provider'):
                line += f" The image provider ({problem['provider']}) is not ready."
            if problem.get('next') and problem.get('next') not in line:
                line += f" {self._plainly(str(problem['next']))}"
            lines.append(line)
        return ('Not recorded:\n- ' + '\n- '.join(lines) + '\n\nDraw the rest of the slide, '
                'and say what is missing when you hand in. The person is told too.')

    @tool
    def submit_section(self, section, changed='', bothers='', beyond=None):
        """Hand the section in. It must be the version last previewed."""
        name, spec = self._spec('section')
        drawn, text = as_json(section, 'section')
        named = self._beyond(spec, beyond)
        state = self._state()
        left = (spec.get('previews') or deck.PREVIEWS) - state.get('previews', 0)
        if state.get('previewed') != self._digest(drawn):
            if not state.get('previewed'):
                raise Refusal('Preview the section first: what you hand in is what you '
                              'last looked at.')
            raise Refusal('This is not the version you last previewed, and it was not '
                          'counted as a hand-in. Hand in exactly that version'
                          + (f', or preview this one first: you have {left} '
                             f'preview{"" if left == 1 else "s"} left.' if left > 0
                             else '. You have no previews left.'))
        accepted = self._hand_in(name, text)
        if accepted[0]:
            notes = [f'{label}: {said.strip()}' for label, said in (
                ('What I changed after looking', changed), ('What still bothers me', bothers))
                if isinstance(said, str) and said.strip()]
            if notes:
                _write(self.folder / 'accepted' / 'review.md',
                       '\n'.join(notes)[:NOTES] + '\n')
            if named:
                home.write_json(self.folder / 'accepted' / 'beyond.json', named)
        return accepted

    @staticmethod
    def _beyond(spec: dict, beyond) -> list[dict]:
        """The slides a composer drawing again after a review against the design says it
        cannot put right by drawing, each with why. Only such a composer may name any."""
        if beyond in (None, '', []):
            return []
        if not spec.get('beyond'):
            raise Refusal('`beyond` is for a section drawn again after a review against its '
                          'design. Leave it out.')
        given = as_json(beyond, 'list of slides')[0]
        ids = [slide['id'] for slide in spec['slides']]
        if not isinstance(given, list) or not all(
                isinstance(entry, dict) and entry.get('slide') in ids
                and isinstance(entry.get('why'), str) and len(entry['why'].strip()) >= deck.NOTE
                for entry in given):
            raise Refusal('`beyond` lists the slides of your section that only another visual '
                          'concept or other words would put right, each as {"slide", "why"}, '
                          'the slide one of: ' + ', '.join(ids) + '. Nothing was handed in.')
        return [{'slide': entry['slide'], 'why': entry['why'].strip()[:NOTES]}
                for entry in given]

    # --- a deck: what a reviewer sees ---

    @tool
    def look_at_slide(self, number):
        """One slide as it was rendered, at full size."""
        slides = self.job.get('look') or []
        if not slides:
            raise Refusal('This job has no rendered slides to look at.')
        wanted = whole(number, 'number')
        slide = next((slide for slide in slides if slide['number'] == wanted), None)
        if slide is None:
            raise Refusal('The slides you can look at are numbered '
                          + ', '.join(str(slide['number']) for slide in slides) + '.')
        picture(slide['image'])
        state = self._state()
        home.write_json(self.folder / 'state.json', {
            **state, 'looked': sorted({*state.get('looked', []), wanted})})
        return Shown(True, f"Slide {wanted}, `{slide['id']}`: \"{slide['title']}\".",
                     [slide['image']])

    @tool
    def submit_assessment(self, findings, weakest=None):
        """Hand in every "no" of the review. It is recorded against this exact render."""
        review = self._review()
        if review.get('judged'):
            raise Refusal('This deck is reviewed against its design: hand in with '
                          'submit_judgements.')
        self._looked(review)
        given = as_json(findings if findings not in (None, '') else [], 'list of findings')[0]
        named = as_json(weakest if weakest not in (None, '') else [], 'list of slides')[0]
        if not isinstance(given, list) or not isinstance(named, list):
            raise Refusal('findings and weakest are each a list.')
        problems, kept = [], []
        for finding in given:
            found, why = deck.checked(finding, review['slides'],
                                      deck.round_questions(review))
            kept += [found] if found else []
            problems += [why] if why else []
        ids = [slide['id'] for slide in review['slides']]
        if len(named) > 3 or any(ident not in ids for ident in named):
            problems.append('weakest names up to three slides of this deck by ID, the '
                            'weakest first.')
        recorded, said = Path(review['recorded']), ''
        if not problems and recorded.is_file():
            kept, named = (home.read_json(recorded, {}).get(key) or []
                           for key in ('findings', 'weakest'))
            said = (' An assessment was already recorded for this render, and a render '
                    'takes only one, so that one stands.')
        elif not problems:
            problems = self._record(review, kept, named, recorded)
        left = self._count('assessment', problems)
        if problems:
            return self._refused(problems, left)
        home.write_json(self.folder / 'accepted' / 'assessment.json',
                        {'findings': kept, 'weakest': named})
        return True, (f'Recorded: {len(kept)} finding{"" if len(kept) == 1 else "s"}.{said} '
                      'Now say which slides address each objective, with submit_coverage.')

    def _looked(self, review: dict) -> None:
        """An assessment is handed in only once every slide was looked at."""
        self._allowed('assessment', 'The assessment')
        unseen = [str(slide['number']) for slide in review['slides']
                  if slide['number'] not in self._state().get('looked', [])]
        if unseen:
            raise Refusal('Look at every slide first. Not looked at yet: '
                          + ', '.join(unseen) + '.')

    @tool
    def submit_judgements(self, slides, weakest=None):
        """Hand in the review against the design: every criterion of every slide."""
        review = self._review()
        judged = review.get('judged')
        if not judged:
            raise Refusal('This review is handed in with submit_assessment.')
        self._looked(review)
        given = as_json(slides if slides not in (None, '') else [], 'list of slides')[0]
        named = as_json(weakest if weakest not in (None, '') else [], 'list of slides')[0]
        kept, problems = deck.judged(given, judged['packets'])
        ids = [slide['id'] for slide in review['slides']]
        if not isinstance(named, list) or len(named) > 3 or any(ident not in ids
                                                                for ident in named):
            problems.append('weakest names up to three slides of this deck by ID, the '
                            'weakest first.')
        recorded = Path(review['recorded'])
        if not problems:
            problems = self._judged(review, kept, named, recorded)
        left = self._count('assessment', problems)
        if problems:
            return self._refused(problems, left)
        made = home.read_json(recorded, {})
        home.write_json(self.folder / 'accepted' / 'assessment.json', made)
        count = len(made['findings'])
        return True, (f'Recorded: {count} judgement{"" if count == 1 else "s"} left unresolved. '
                      'Now say which slides address each objective, with submit_coverage.')

    def _judged(self, review: dict, kept: list, named: list, recorded: Path) -> list[str]:
        """Tell the slides tool every slide was looked at, and give it the assessment, against
        the review it answers. Returns what the tool refused."""
        judged = review['judged']
        packets = judged.get('all_packets') or judged['packets']
        all_slides = judged.get('all_slides') or review['slides']
        if judged.get('previous'):
            answers = {entry['slide']: entry for entry in judged['previous']}
            answers.update({entry['slide']: entry for entry in kept})
            combined = [answers.get(packet['slide']['slide']) for packet in packets]
            kept, problems = deck.judged(combined, packets)
            if problems:
                return problems
        output, revision = Path(judged['output']), judged['revision']
        try:
            self.slides().review_mark(output, revision,
                                      [slide['number'] for slide in all_slides],
                                      deck.MARKED)
            made = self.slides().review_assess(output, revision, deck.assessment(
                kept, packets, judged['binding'],
                sources=not self.slides().has('review-sources-from-slide')))
        except WorkspaceError as refusal:
            return [self._plainly(line) for line in said_no(refusal)]
        numbers = {slide['id']: slide['number'] for slide in review['slides']}
        direct = [{'slide': entry['slide'], 'number': numbers.get(entry['slide']),
                   'accepted': entry.get('accepted'), 'reason': entry.get('reason')}
                  for entry in ((made.get('designReview') or {}).get('categories') or {})
                  .get('direct-text') or () if entry.get('kind') == 'treatment']
        home.write_json(recorded, {
            'findings': deck.found(made.get('unresolved'), kept, all_slides),
            **({'judgements': kept} if judged.get('keep_judgements') else {}),
            'weakest': named, 'direct': direct,
            'complete': bool(made.get('creativeReviewComplete'))})
        return []

    def _record(self, review: dict, kept: list, named: list, recorded: Path) -> list[str]:
        """Record an assessment with the slides tool, against the render it is of. Returns
        what the tool refused in it."""
        assessment = {'deckSha256': review['deck'], 'reviewer': 'independent',
                      'weakest': named, 'findings': [
                          {key: finding[key] for key in ('slide', 'question', 'severity',
                                                         'note', 'fix')
                           if finding[key] is not None} for finding in kept]}
        path = _draft(self.folder / 'drafts', 'assessment',
                      json.dumps(assessment, indent=2, ensure_ascii=False) + '\n')
        try:
            self.slides().critique(Path(review['preview']), path)
        except WorkspaceError as refusal:
            return [self._plainly(line) for line in said_no(refusal)]
        home.write_json(recorded, {'findings': kept, 'weakest': named})
        return []

    @tool
    def submit_coverage(self, coverage, reasons=''):
        """Say which slides address each objective, from what the slides show."""
        review = self._review()
        self._allowed('coverage', 'The coverage')
        given = as_json(coverage, 'coverage')[0]
        wanted, most = list(review.get('objectives') or ()), len(review['slides'])
        allowed = {slide['number'] for slide in review['slides']}
        problems = []
        if not isinstance(given, dict) or sorted(given) != sorted(wanted):
            problems.append('Give every objective and nothing else: ' + ', '.join(wanted)
                            + '.')
        else:
            problems += [f'{objective}: a list of slide numbers from 1 to {most}, or an '
                         'empty list when no slide addresses it.'
                         for objective, numbers in given.items()
                         if not isinstance(numbers, list) or any(
                             type(number) is not int or number not in allowed
                             for number in numbers)]
        left = self._count('coverage', problems)
        if problems:
            return self._refused(problems, left)
        home.write_json(self.folder / 'accepted' / 'coverage.json', {
            'objectives': {objective: sorted(set(given[objective])) for objective in wanted},
            'reasons': str(reasons or '').strip()[:NOTES]})
        return True, 'Kept.'

    # --- sources ---

    @tool
    def save_source(self, url):
        """Fetch a public page or PDF, keep it, and return the start of its text."""
        if not self.job['fetch']:
            raise Refusal('This job cannot fetch pages. Work from what you were given.')
        url, index = str(url).strip(), self._index()
        sent = self._sendable(url)   # the same page, whatever fragment it is asked with
        known = next((item for item in index if url in (item['url'], item.get('asked'))
                      or sent == item['url']), None)
        if known:
            return True, self._shown(known, 'Already saved')
        if len(index) >= MAX_SOURCES:
            raise Refusal(f'This job has saved {MAX_SOURCES} sources, which is the most it '
                          'may. Work from those.')
        final, headers, data = self._fetch(url)
        entry = self._keep(url, final, headers, data, len(index) + 1)
        home.write_json(self.folder / 'sources' / 'index.json', [*index, entry])
        return True, self._shown(entry, 'Saved')

    def _checked(self, url: str, redirected_from: str | None = None) -> list[str]:
        """The public addresses a web address leads to. Refuses any other kind, and, where
        the job keeps to your sites, any address outside them: `redirected_from` is the
        address that led here, for a hop after the first."""
        try:
            target = urllib.parse.urlsplit(url)
            host, signed = target.hostname, target.username or target.password
        except ValueError:
            raise Refusal('That is not a web address.')
        if len(url) > ADDRESS:
            raise Refusal(f'That address is longer than {ADDRESS:,} characters, so it was not '
                          'fetched.')
        if target.scheme not in ('http', 'https') or not host:
            raise Refusal('Only http and https addresses can be saved.')
        if signed:
            raise Refusal('That address carries a name or password. Give it without them.')
        chosen = self.job.get('research')
        if chosen is not None:   # asked before the name is looked up: nothing is fetched
            said = research_sites.refused(url, chosen, redirected_from)
            if said:
                state = self._state()
                state['outside'] = list(dict.fromkeys(
                    [*state.get('outside', []), url]))[:MAX_SOURCES]
                home.write_json(self.folder / 'state.json', state)
                raise Refusal(said)
        try:
            addresses = self.resolver(host)
        except (OSError, UnicodeError) as failure:
            raise Refusal(f'Could not look up {host} ({failure}).')
        if not addresses or not all(public(address) for address in addresses):
            raise Refusal('That address is not on the public internet, so it was not '
                          'fetched.')
        return addresses

    def _fetch(self, url: str) -> tuple[str, dict, bytes]:
        """A page's final address, headers and body, with every hop on the way checked."""
        before = None
        for _ in range(MAX_HOPS + 1):
            # Asked, checked and sent without its fragment, so a '#' cannot hide a path
            # from the checks: parsers and urllib split at different '#'.
            url = self._sendable(url)
            status, headers, data = self._ask(url, self._checked(url, before))
            if status in REDIRECTS and headers.get('location'):
                before, url = url, urllib.parse.urljoin(url, headers['location'])
                continue
            if not 200 <= status < 300:
                said = http.client.responses.get(status, '')
                raise Refusal(f'The site answered {status} {said}'.rstrip()
                              + '. The page was not saved.')
            data = unpacked(data, headers.get('content-encoding', ''))
            if len(data) > MAX_BYTES:
                raise Refusal(f'That is larger than {MAX_BYTES // 1_000_000} MB, so it was '
                              'not saved. Look for a smaller page that says the same.')
            return url, headers, data
        raise Refusal('That address redirected too many times. It was not saved.')

    @staticmethod
    def _sendable(url: str) -> str:
        """An address as it is sent: without its fragment, which a browser never sends."""
        try:
            return research_sites.fetchable(url)
        except ValueError:
            raise Refusal('That is not a web address.')

    @tool
    def read_source(self, source_id, offset=0, length=WINDOW, original=False):
        """Part of a saved source, from a character offset. With `original`, part of the
        document it was taken from, after a line that names that file."""
        said = ''
        if flag(original):
            entry, text = self._original(source_id)
            said, _, text = text.partition('\n\n')
            said += '\n'
        else:
            entry, text = self._source(source_id)
        what = entry['id'] + (' original' if said else '')
        start = max(0, whole(offset, 'offset'))
        size = min(max(1, whole(length, 'length')), WINDOW)
        if start >= len(text):
            raise Refusal(f"{what} has {len(text):,} characters; there is nothing "
                          f'at {start:,}.')
        end = min(len(text), start + size)
        return True, (f"{said}[{what}: characters {start:,} to {end:,} of {len(text):,}]"
                      f'\n\n{text[start:end]}')

    @tool
    def search_source(self, source_id, query, original=False):
        """Where a word or phrase appears in a saved source, or with `original` in the
        document it was taken from."""
        if flag(original):
            entry, text = self._original(source_id)
            text = text.partition('\n\n')[2]
        else:
            entry, text = self._source(source_id)
        wanted = ' '.join(str(query).lower().split())
        if not wanted:
            raise Refusal('Say what to look for.')
        found, low, start = [], text.lower(), 0
        while len(found) < 8:
            at = low.find(wanted, start)
            if at < 0:
                break
            found.append(f'[offset {at}] …{text[max(0, at - 250):at + 450]}…')
            start = at + len(wanted)
        if not found:
            return True, f"No match in {entry['id']}. Try fewer or different words."
        return True, '\n\n'.join(found)

    # --- findings ---

    @tool
    def submit_finding(self, item, status, summary, limits='', evidence=None):
        """Hand back the finding for the job's question, with exact quotes."""
        wanted = self.job['finding']
        if not wanted:
            raise Refusal('This job does not answer a research question.')
        if str(item).strip() != wanted:
            raise Refusal(f'This job answers {wanted}, not "{item}".')
        self._allowed('finding', 'This finding')
        passages = self._passages(evidence)
        problems, kept = [], []
        if status not in STATUSES:
            problems.append('status must be one of: ' + ', '.join(STATUSES) + '.')
        if not isinstance(summary, str) or not summary.strip():
            problems.append('The summary is empty.')
        elif len(summary) > SUMMARY:
            problems.append(f'The summary is {len(summary):,} characters. Keep it under '
                            f'{SUMMARY:,}, and to what the quotes support.')
        limits = str(limits or '').strip() or 'none'
        if len(limits) > 4000:
            problems.append('The limits are too long. Keep them under 4,000 characters.')
        if status in ('supported', 'contradicted') and not passages:
            problems.append(f'A {status} finding needs at least one quoted passage.')
        if len(passages) > PASSAGES:
            problems.append(f'Give at most {PASSAGES} passages; choose the ones that carry '
                            'the point.')
        for number, passage in enumerate(passages[:PASSAGES], start=1):
            placed = self._placed(number, passage, problems)
            if placed:
                kept.append(placed)
        left = self._count('finding', problems)
        if problems:
            return self._refused(problems, left)
        home.write_json(self.folder / 'accepted' / 'finding.json', {
            'item': wanted, 'status': status, 'summary': summary.strip(), 'limits': limits,
            'evidence': kept})
        return True, (f'Accepted: the finding for {wanted}, with {len(kept)} quoted '
                      'passage(s).')

    # --- questions ---

    @tool
    def ask_person(self, question):
        """End the job with a question for the person."""
        if not self.job['ask']:
            raise Refusal('Nobody can answer questions in this job. Do what you can, and '
                          'say what is missing when you hand back.')
        if not isinstance(question, str) or not question.strip():
            raise Refusal('The question is empty.')
        if len(question) > QUESTION:
            raise Refusal(f'The question is {len(question):,} characters. Ask one thing, in '
                          f'under {QUESTION:,}.')
        home.write_json(self.folder / 'accepted' / 'question.json',
                        {'question': question.strip(), 'at': home.now()})
        home.write_json(self.folder / 'state.json', {**self._state(), 'ended': 'question'})
        return True, ('Your question was recorded, and this job is over. Stop now and call '
                      'no other tool. The answer will be there when the work is started '
                      'again.')


modules.bind(globals(), _shared, methods={'WorkerTools': _shared.METHODS['WorkerTools']})


# --- what an agent is told about the tools -----------------------------------------------


TOOLS = [
    _described('list_inputs', 'List what this job was given to read: its inputs by name, '
               'and any sources already saved.', {}, []),
    _described('read_input', 'Read one input by name. A long input comes in parts: ask for '
               'part 2, 3 and so on.', {'name': TEXT, 'part': NUMBER}, ['name']),
    _described('submit_artifact', 'Hand back a finished draft under the name your task '
               'gives. It is checked: if anything is wrong you are told what, to fix it '
               'and hand it back again.', {'name': TEXT, 'text': TEXT}, ['name', 'text']),
    _described('submit_part', 'Hand back only the requested section or passage. The whole material is checked.', {'text': TEXT}, ['text']),
    _described('submit_review', 'After your draft is accepted, give your own honest notes '
               'on it for the person who will review it: where it is weakest, what is '
               'missing, what to look at.', {'text': TEXT}, ['text']),
    _described('check_outline', 'Check a draft of the outline, and of its design when your '
               'task asks for one. Returns what to put right. Nothing is kept: use it until '
               'nothing is left to put right.', {'outline': TEXT, 'design': TEXT}, ['outline']),
    _described('submit_outline', 'Hand the outline in, whole, as JSON text, with its design '
               'when your task asks for one. They are checked the same way and kept only '
               'when nothing is left to put right.', {'outline': TEXT, 'design': TEXT},
               ['outline']),
    _described('check_section', 'Compile a draft of your section, whole, as JSON text, '
               'without rendering it. Returns every problem to put right. Free to use as '
               'often as you need.', {'section': TEXT}, ['section']),
    _described('preview_section', 'Compile and render your section and return a picture of '
               'every slide, with what the renderer found. Slow, and limited in number.',
               {'section': TEXT}, ['section']),
    _described('search_icons', "Search the brand's icons by one or two plain words. "
               'Returns the ID to use for each.', {'words': TEXT, 'limit': NUMBER},
               ['words']),
    _described('list_assets', "List the pictures and icons recorded for this deck: each "
               'one\'s asset ID, what it shows, and how it is placed.', {}, []),
    _described('request_asset', 'Record a brand icon under an asset ID, by the ID '
               'search_icons gives; or have generated art made for one of your slides drawn '
               'as generated art, from a brief you write. Costs money: ask once.',
               {'asset': TEXT, 'icon': TEXT, 'slide': TEXT, 'prompt': TEXT, 'alt': TEXT},
               ['asset']),
    _described('submit_section', 'Hand your section in. It must be exactly the version you '
               'last previewed. Say what you changed after looking at the pictures, and '
               'what still bothers you. Drawn again after a review against the design, name '
               'in beyond any slide that only another visual concept or other words would '
               'put right.',
               {'section': TEXT, 'changed': TEXT, 'bothers': TEXT,
                'beyond': {'type': 'array', 'items': {
                    'type': 'object', 'properties': {'slide': TEXT, 'why': TEXT},
                    'required': ['slide', 'why']}}}, ['section']),
    _described('look_at_slide', 'Look at one rendered slide at full size, by its number.',
               {'number': NUMBER}, ['number']),
    _described('submit_assessment', 'Hand in your review: one finding for each question '
               'you answered no. It is recorded against this exact render.',
               {'findings': {'type': 'array', 'items': {
                   'type': 'object', 'properties': {
                       'slide': TEXT, 'question': NUMBER,
                       'severity': {'type': 'string', 'enum': list(deck.SEVERITIES)},
                       'about': {'type': 'string', 'enum': list(deck.ABOUT)},
                       'note': TEXT, 'fix': TEXT},
                   'required': ['slide', 'question', 'severity', 'note']}},
                'weakest': {'type': 'array', 'items': TEXT}}, ['findings']),
    _described('submit_judgements', 'Hand in your review against the design: for every '
               'slide, an answer to each of its criteria. A judgement that is not a pass says '
               'how grave it is and what it is about. It is checked by the slides tool against '
               'this exact render.',
               {'slides': {'type': 'array', 'items': {
                   'type': 'object', 'properties': {
                       'slide': TEXT, 'checks': {'type': 'array', 'items': {
                           'type': 'object', 'properties': {
                               'criterion': TEXT,
                               'status': {'type': 'string', 'enum': list(deck.STATUSES)},
                               'reason': TEXT, 'objects': {'type': 'array', 'items': TEXT},
                               'severity': {'type': 'string', 'enum': list(deck.SEVERITIES)},
                               'about': {'type': 'string', 'enum': list(deck.JUDGED)},
                               'fix': TEXT},
                           'required': ['criterion', 'status', 'reason', 'objects']}}},
                   'required': ['slide', 'checks']}},
                'weakest': {'type': 'array', 'items': TEXT}}, ['slides']),
    _described('submit_coverage', 'Say which slides address each objective, from what the '
               'slides show: slide numbers for each objective, and an empty list where no '
               'slide addresses it.',
               {'coverage': {'type': 'object'}, 'reasons': TEXT}, ['coverage']),
    _described('save_source', 'Fetch a public web page or PDF, keep it, and return the '
               'start of its text. Only sources saved this way count as evidence.',
               {'url': TEXT}, ['url']),
    _described('read_source', 'Read part of a saved source, from a character offset. With '
               'original true, read the document a supplied source was taken from '
               '(list_inputs names each one), after a line giving its size and SHA-256.',
               {'source_id': TEXT, 'offset': NUMBER, 'length': NUMBER, 'original': FLAG},
               ['source_id']),
    _described('search_source', 'Find a word or phrase in a saved source. Each match comes '
               'with its offset and the text around it. With original true, search the '
               'document a supplied source was taken from.',
               {'source_id': TEXT, 'query': TEXT, 'original': FLAG}, ['source_id', 'query']),
    _described('submit_finding', 'Hand back the finding for your research question. Each '
               'quote must be copied exactly from a saved source; its place is worked out '
               'for you.',
               {'item': TEXT, 'status': {'type': 'string', 'enum': list(STATUSES)},
                'summary': TEXT, 'limits': TEXT,
                'evidence': {'type': 'array', 'items': {
                    'type': 'object', 'properties': {'source_id': TEXT, 'quote': TEXT},
                    'required': ['source_id', 'quote']}}},
               ['item', 'status', 'summary']),
    _described('ask_person', 'Ask the person one question you cannot work without an '
               'answer to. This ends your job: stop as soon as you have asked.',
               {'question': TEXT}, ['question']),
]
NAMES = tuple(entry['name'] for entry in TOOLS)


# --- the server ------------------------------------------------------------------------


if __name__ == '__main__':
    sys.exit(main())
