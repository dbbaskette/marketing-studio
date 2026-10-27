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
  validator (VALIDATORS). A 'research-plan' takes 'scope' and 'sources': the worker supplies
  the topic and the questions, and the runner fills in the rest, so what is kept is the
  whole plan. The scope is harness-research's: 'supplied-only', or 'public-web' for any
  research that saves pages, your sites among them; each question keeps its public_query
  only under 'public-web'.
- A later part of the runner adds a kind with `register(kind, check)`: `check(text, spec)`
  returns (problems, the checks that ran, warnings, the text to keep), and the draft is
  handed back with `submit_artifact`. The check must be a function a module under runner
  defines at its top level: job.json names it, and the server, which runs apart from the
  runner, imports it by that name and registers it there too. One registered with
  `drawn=True` is checked as `check(text, spec, slides, scratch)`, with the slides tool and
  a folder for drafts, and its spec names its 'brand'.
- A check that cannot run for want of what it needs is recorded as unavailable, for the
  gate. It is not held against the worker.
- `finding` is the ID of the one research question the job answers. An accepted finding is in
  the shape `harness-research record` takes, with each quote's place worked out here.
- `sources` are documents offered before the job starts: {'title', 'origin', 'text', 'file',
  'supplied'}, where `file` is the snapshot's path in the deck and `supplied` is the
  document's ID in the research plan, if it has one.
- Saved sources are named after their content, under sources/, so the engine can copy a
  job's sources into a deck's own sources/ and a finding's `file` stays true.
- `fetch` lets the job save pages. Only public http and https addresses are fetched: every
  address a name has must be public, each redirect is checked again, and the connection
  goes to the address that was checked. Where a computer reaches the web through a proxy,
  the proxy connects instead; if that computer cannot look names up itself, nothing is
  fetched.
- `research` is where the deck's research may look, as studio_core.research_sites keeps it:
  {'documents', 'sites', 'web'}, checked by prepare and kept in job.json. With your sites on
  and the public web off, every hop of a page, redirects included, must be https and under a
  listed site (`research_sites.refused`), or it is refused, before its name is looked up,
  with a sentence that names the sites; with the public web on any public page is saved.
  The private-address refusals stand either way. Each page refused for being outside the
  sites is kept in state.json, and `collect(folder)['outside']` lists them for the research
  stop. A job set up without `research`, as every older one was, fetches as before.
- A draft or a finding can be handed back SUBMISSIONS times. After that, treat the job as
  failed: `collect(folder)['problems']` says why the last one was refused.
- A question (`ask_person`) ends the job: every later call is refused. Pass `ask=False`
  for a job nobody can answer, such as one research question among many.
- A tool's answer may carry pictures. It is then a `Shown`: the same (ok, text) pair, with
  the PNG files to show after the text in `.pictures`. The server sends each as an image.
- A deck's jobs have tools of their own, and these and no others beside the inputs:
  an 'outline' (what each slide says) has `check_outline` and `submit_outline`; a 'section'
  (some slides, drawn) has `check_section`, `preview_section`, `search_icons` and
  `submit_section`; a review, set up with `review=`, has `look_at_slide` and
  `submit_assessment`. `look=` gives any job slides to look at.
- An 'outline' takes 'brand' (the exported brand contract's path) and 'rules': each a
  function `rule(outline: dict) -> list[str]`, a sentence for each problem. It is checked
  with the slides tool's own check and with each rule. A rule is kept in job.json by its
  module and name, so it must be a function a module defines at its top level, or a
  functools.partial of one whose arguments are JSON. A 'section' takes 'brand' and what
  `steps.build.fixed` returned, and how its previews are taken: 'previews' (how many it
  has), 'renderer', 'lock' and 'kept'. It is checked with `steps.build.kept` and with the
  slides tool's compiler. What is handed in must be the version last previewed; a hand-in
  that is not costs nothing and is sent back.
- Previews are taken one at a time on this computer, whatever is drawn side by side:
  `render` waits for the file named by 'lock'. 'kept' names the file that remembers the one
  preview file a deck keeps in Google Drive, so that it is written again and no second
  one is made.
- `review` is {'preview', 'deck', 'slides', 'recorded'}: the previewed deck's folder and
  hash, its slides as {'number', 'id', 'title', 'image'}, and where an accepted assessment
  is also kept. The slides tool takes one assessment for one render, so one that is already
  there stands.
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
import functools
import hashlib
import html.parser
import http.client
import importlib
import inspect  # noqa: F401  read by the shared parts
import ipaddress  # noqa: F401  read by the shared parts
import json
import os
import re  # noqa: F401  read by the shared parts
import secrets
import shutil
import socket  # noqa: F401  read by the shared parts
import ssl  # noqa: F401  read by the shared parts
import subprocess  # noqa: F401  read by the shared parts
import sys
import time
import types
import urllib.error
import urllib.parse
import urllib.request
import zlib  # noqa: F401  read by the shared parts
from contextlib import contextmanager
from pathlib import Path

if not __package__:  # started as the server, by its path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runner  # noqa: F401,E402  puts the core on the import path
import home  # noqa: E402
from workspace import WorkspaceError  # noqa: E402

from runner.steps import build  # noqa: E402
from studio_core import research_sites  # noqa: E402

from studio_core import modules  # noqa: E402
from studio_core.shared_runner import worker_tools as _shared  # noqa: E402
PRODUCT, ITEM, ITEMS = 'Presentation Studio', 'deck', 'decks'
modules.bind(globals(), _shared, _shared.NAMES)

HEADLINE = 25           # words in a finding's headline
HEADLINE_UNITS = 300    # harness-research's limit on a headline, in UTF-16 code units
QUESTIONS = 30          # questions harness-research takes in one plan


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


# --- validators ------------------------------------------------------------------------

def result(check: str, problems: list[str], unavailable: str | None = None) -> dict:
    """One check outcome: passed, failed, or unavailable with the reason."""
    if unavailable is not None:
        return {'check': check, 'status': 'unavailable', 'problems': [unavailable]}
    return {'check': check, 'status': 'failed' if problems else 'passed', 'problems': problems}


def check_research_plan(plan, most=QUESTIONS) -> dict:
    """Check a research plan is one harness-research will accept. `plan` is the parsed JSON."""
    name = 'research-plan.items'
    if not isinstance(plan, dict):
        return result(name, ['The plan must be a JSON object.'])
    problems = []
    if plan.get('purpose') != 'planning':
        problems.append('"purpose" must be "planning".')
    if plan.get('scope') not in SCOPES:
        problems.append('"scope" must be one of: ' + ', '.join(SCOPES))
    if 'input_files' in plan:
        problems.append('Leave out "input_files"; registering intake there makes '
                        'harness-research discard its findings when intake is edited.')
    items = plan.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= most:
        problems.append(f'"items" must hold 1 to {most} questions.')
        return result(name, problems)
    seen = set()
    for position, item in enumerate(items, start=1):
        identifier = item.get('id') if isinstance(item, dict) else None
        if not isinstance(identifier, str) or not QUESTION_ID.match(identifier):
            problems.append(f'Question {position} needs an "id" of lowercase letters, '
                            'digits and hyphens.')
        elif identifier in seen:
            problems.append(f'Question ID {identifier} is used more than once.')
        else:
            seen.add(identifier)
        question = item.get('question') if isinstance(item, dict) else None
        if not isinstance(question, str) or not question.strip():
            problems.append(f'Question {position} has no question text.')
    return result(name, problems)


def check_outline(text: str, spec: dict, slides,
                  scratch: Path) -> tuple[list[str], list[dict], list[str], str]:
    """An outline: what each slide of a deck says. The slides tool checks its shape and
    its own limits, and each of the spec's rules is checked on top."""
    try:
        outline, kept = as_json(text, 'outline')
    except Refusal as refusal:
        return [str(refusal)], [], [], text
    if isinstance(outline, dict) and spec.get('delivery') in ('live', 'reading') \
            and outline.get('delivery') != spec['delivery']:
        # Talk or handout was decided once, on the form: the outline is kept as it says.
        outline = {**outline, 'delivery': spec['delivery']}
        kept = json.dumps(outline, indent=2, ensure_ascii=False) + '\n'
    try:
        # The tool checks the outline without what it does not know: a point's `parts`
        # and a slide's `provenance`, on an older tool.
        known = slides.knows() if hasattr(slides, 'knows') else frozenset()
        shown = build.for_tool(outline, known)
        told = kept if shown == outline else json.dumps(
            shown, indent=2, ensure_ascii=False) + '\n'
        report = slides.outline_check(_draft(scratch, 'outline', told), spec['brand'])
    except WorkspaceError as refusal:
        found = said_no(refusal)
    else:
        found = [f"{finding.get('slide')}: {finding.get('detail') or finding.get('code')}"
                 for finding in report.get('findings') or ()]
    if not isinstance(outline, dict):
        ruled = ['The outline is one JSON object with its slides under "slides".']
    else:
        ruled = [str(problem) for rule in rules_of(spec) for problem in rule(outline) or ()]
    outcomes = [result('outline.tool', found), result('outline.rules', ruled)]
    return held(outcomes), outcomes, [], kept


def check_section(text: str, spec: dict, slides,
                  scratch: Path) -> tuple[list[str], list[dict], list[str], str]:
    """A section: some slides of a deck, drawn. What was fixed before its composer started
    must be as it was, with every approved word kept, and the slides tool must compile it."""
    try:
        section, kept = as_json(text, 'section')
    except Refusal as refusal:
        return [str(refusal)], [], [], text
    ours, found = build.kept(section, spec), []
    if spec.get('pictures') and Path(spec['pictures']).is_dir():   # named from the draft
        try:   # best effort: a picture that is missing is said by the compile
            shutil.copytree(spec['pictures'], Path(scratch) / build.PICTURES,
                            dirs_exist_ok=True)
        except (OSError, shutil.Error):
            pass
    if isinstance(section, dict):
        try:
            slides.compile(_draft(scratch, 'section', kept), spec['brand'], **outlined(spec))
        except WorkspaceError as refusal:
            found = said_no(refusal)
    outcomes = [result('section.rules', ours), result('section.compile', found)]
    return held(outcomes), outcomes, [], kept


def outlined(spec: dict) -> dict:
    """What compile is given of the approved outline a section is drawn from, so that a
    tool that can finds a point's sentence split across shapes: nothing without one. A deck
    with pictures the person gave adds its asset project, which resolves them."""
    return {**({'outline': Path(spec['outline'])} if spec.get('outline') else {}),
            **({'assets': Path(spec['asset_project'])} if spec.get('asset_project') else {})}


# --- the rules an outline is held to, kept by name ----------------------------------------

def reference(rule) -> dict:
    """A rule as job.json keeps it: {'call': 'module:name', 'args', 'kwargs'}. Only a
    function a module defines at its top level, or a functools.partial of one whose
    arguments are JSON, can be kept, since the server finds it again by name."""
    args, kwargs = (), {}
    if isinstance(rule, functools.partial):
        rule, args, kwargs = rule.func, rule.args, dict(rule.keywords)
    module, name = getattr(rule, '__module__', None), getattr(rule, '__qualname__', '')
    if not callable(rule) or not module or not name or '<' in name or '.' in name:
        raise WorkspaceError('A rule for an outline is a function a module defines at its '
                             'top level, or a functools.partial of one.')
    try:
        json.dumps([args, kwargs])
    except (TypeError, ValueError):
        raise WorkspaceError(f'The rule {name} is given something that cannot be kept as '
                             'JSON.') from None
    return {'call': f'{module}:{name}', 'args': list(args), 'kwargs': kwargs}


def rules_of(spec: dict) -> list:
    """The rules a spec names, as functions to call: each given as one, or as job.json
    keeps it."""
    found = []
    for rule in spec.get('rules') or ():
        if callable(rule):
            found.append(rule)
            continue
        module, _, name = str(rule.get('call')).partition(':')
        function = getattr(importlib.import_module(module), name)
        found.append(functools.partial(function, *rule.get('args') or (),
                                       **rule.get('kwargs') or {}))
    return found


from studio_core.research_contract import check_json as check_research_json

VALIDATORS = {'research-plan': check_plan, 'outline': check_outline,
              'section': check_section}
VALIDATORS['research-json'] = check_research_json
REGISTERED: dict[str, dict] = {}    # a kind added by register: {'call', 'extension'}


def _named(check) -> str | None:
    """'module:name' for a function a module under runner defines at its top level, which
    the server, a process of its own, can import again; None for anything else."""
    module, name = getattr(check, '__module__', None), getattr(check, '__qualname__', '')
    if not isinstance(check, types.FunctionType) or not isinstance(module, str) \
            or not module.startswith('runner.') or not name or '<' in name or '.' in name:
        return None
    try:
        found = getattr(importlib.import_module(module), name, None)
    except ImportError:
        return None
    return f'{module}:{name}' if found is check else None


def register(kind: str, check, extension: str = '.json', drawn: bool = False) -> None:
    """Add a kind of draft that is handed back with submit_artifact. `check(text, spec)`
    returns (problems, the checks that ran, warnings, the text to keep). It must be a
    function a module under runner defines at its top level: job.json names it, and the
    server, which runs apart, imports it by that name. A kind that is `drawn` is checked
    as `check(text, spec, slides, scratch)`, with the slides tool and a folder for drafts,
    and its spec names the brand it is checked against."""
    call = _named(check)
    if not isinstance(kind, str) or not kind or kind in DRAWN or call is None:
        raise WorkspaceError(f'"{kind}" cannot be registered as a kind of draft: its check '
                             'must be a function a module under runner defines at its top '
                             'level.')
    VALIDATORS[kind] = check
    EXTENSIONS[kind] = extension
    REGISTERED[kind] = {'call': call, 'extension': extension,
                        **({'drawn': True} if drawn else {})}


def drawn(kind: str) -> bool:
    """Whether a kind's check asks the slides tool."""
    return kind in DRAWN or bool((REGISTERED.get(kind) or {}).get('drawn'))


def validator(kind: str, registered: dict | None = None):
    """The check for a kind. One this process has not registered is registered here from
    the name job.json gives it. None when there is none."""
    named = (registered or {}).get(kind)
    if kind not in VALIDATORS and isinstance(named, dict):
        module, _, name = str(named.get('call')).partition(':')
        register(kind, getattr(importlib.import_module(module), name),
                 named.get('extension') or '.json', bool(named.get('drawn')))
    return VALIDATORS.get(kind)


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


def review_questions(review: dict) -> tuple[str, ...]:
    """The questions a review job was asked: the slides tool's own, kept with its round."""
    from studio_core import critic
    return critic.of_round(review)


def render(slides, compiled: Path, folder: Path, how: dict) -> dict:
    """Preview compiled slides, when it is this preview's turn. `how` is {'renderer',
    'lock', 'kept', 'named'}: 'kept' names the file that remembers a deck's one preview
    file in Google Drive, which is written again each time, and 'named' is what to
    remember of it beside its ID and address. A preview that fails after it made that
    file says so in its refusal's `left`, as {'fileId', 'url'}, and the file is remembered
    all the same. Returns what the slides tool returned."""
    kept = Path(how['kept']) if how.get('kept') else None
    with turn(turn_file(how, slides), slots(how, slides)):
        known = home.read_json(kept, {}) if kept else {}
        known = known if isinstance(known, dict) else {}
        def remember(ident, url, receipt=None) -> None:
            if kept and ident and (ident != known.get('id') or receipt != known.get('pool')):
                home.write_json(kept, {**(how.get('named') or {}), 'id': ident, 'url': url,
                                       **({'pool': receipt} if receipt else {})})

        from runner import build_progress
        progress = build_progress.Preview(how['progress'], folder) if how.get('progress') else None
        try:
            found = slides.preview(compiled, folder, how['renderer'], file_id=known.get('id'))
            if progress:
                progress.finish(found)
        except WorkspaceError as refusal:  # a preview that failed may have made its file
            if progress:
                progress.failed()
            if replaced(refusal) and kept:
                kept.unlink(missing_ok=True)   # its slides are someone else's by now
                raise
            left = getattr(refusal, 'left', None) or {}
            remember(left.get('fileId'), left.get('url'))
            raise
        except BaseException:
            if progress:
                progress.failed()
            raise
        # A preview in the slides tool's pool is one of its own few reusable decks: its link
        # is kept with the receipt that says which preview it holds, and once a newer
        # preview has replaced it, the link is forgotten rather than shown with someone
        # else's slides. The delivered deck is a file of its own and is not touched.
        if found.get('remoteReplaced'):
            if kept:
                kept.unlink(missing_ok=True)
            return found
        pool = found.get('pool') if isinstance(found.get('pool'), dict) else {}
        remember(found.get('fileId'), found.get('url'), pool.get('receipt'))
    return found


def replaced(refusal) -> bool:
    """Whether the slides tool refused because a newer preview took over the preview file."""
    return 'preview-replaced' in (getattr(refusal, 'codes', None) or ()) or any(
        'replaced by a newer one' in str(line) for line in getattr(refusal, 'problems', None)
        or ())


# --- a job's folder --------------------------------------------------------------------

def prepare(folder: Path, inputs: dict[str, str] | None = None,
            artifacts: dict[str, dict] | None = None, finding: str | None = None,
            sources=(), fetch: bool = False, ask: bool = True, review: dict | None = None,
            look=None, runtimes: dict | None = None, research: dict | None = None) -> Path:
    """Set a job's folder up: what the worker may read, and what it must hand back."""
    folder = Path(folder)
    if (folder / 'job.json').exists():
        raise WorkspaceError(f'{folder} already holds a job. Give each job, and each new '
                             'attempt at one, a folder of its own.')
    if research is not None:
        try:
            research = research_sites.choice(research)
        except ValueError as error:
            raise WorkspaceError(str(error)) from None
    artifacts = {name: dict(spec) if isinstance(spec, dict) else spec
                 for name, spec in (artifacts or {}).items()}
    for name, spec in artifacts.items():
        if not isinstance(spec, dict) or spec.get('kind') not in VALIDATORS:
            raise WorkspaceError(f'{name} needs a kind that can be checked: one of '
                                 + ', '.join(VALIDATORS) + '.')
        if spec.get('scope') not in (None, *SCOPES):
            raise WorkspaceError(f"{name}: the scope is one of {', '.join(SCOPES)}.")
        if drawn(spec['kind']) and not spec.get('brand'):
            raise WorkspaceError(f'{name} needs the brand it is checked against.')
        if spec.get('rules'):
            spec['rules'] = [rule if isinstance(rule, dict) else reference(rule)
                             for rule in spec['rules']]
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
        'schema': SCHEMA, 'inputs': listed, 'artifacts': artifacts, 'finding': finding,
        'checks': {spec['kind']: REGISTERED[spec['kind']] for spec in artifacts.values()
                   if spec['kind'] in REGISTERED},
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
    where a finding says it is in the deck. `problems` holds why the last hand-back of
    anything not accepted was refused. For a deck's jobs, `shown` is the last preview a
    composer took, as {'previews', 'slides'} with each slide's picture at `path`, and
    `assessment` what a reviewer handed in.
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
            'review': review.read_text(encoding='utf-8') if review.is_file() else None,
            'finding': home.read_json(kept / 'finding.json', None),
            'question': asked.get('question') if isinstance(asked, dict) else None,
            'sources': sources,
            'outside': list(state.get('outside') or []),
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
        elif 'section' in kinds:
            names += ['check_section', 'preview_section', 'search_icons', 'submit_section']
        elif job['artifacts']:
            names += ['submit_artifact', 'submit_review']
        if job.get('look'):
            names.append('look_at_slide')
        if job.get('review'):
            if job['review'].get('sheet'):
                names.append('look_at_deck')
            names.append('submit_assessment')
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
        if wanted[name]['kind'] == 'section':
            raise Refusal('Hand a section in with submit_section.')
        return self._hand_in(name, text)

    def _validate(self, spec: dict, text: str) -> tuple[list[str], list[dict], list[str], str]:
        """Check one draft with its kind's validator. What the slides tool says is given
        to the worker without the name of any folder here."""
        check = validator(spec['kind'], self.job.get('checks'))
        if check is None:
            raise Refusal(f"Nothing here can check a {spec['kind']}, so it was not kept.")
        if not drawn(spec['kind']):
            if spec['kind'] == 'research-json':
                # A dossier may cite only what this job saved; the author can correct it here.
                spec = {**spec, 'captures': self._index(), 'folder': str(self.folder)}
            return check(text, spec)
        problems, ran, warnings, kept = check(text, spec, self.slides(), self.folder / 'drafts')
        for outcome in ran:
            outcome['problems'] = [self._plainly(problem) for problem in outcome['problems']]
        return [self._plainly(problem) for problem in problems], ran, warnings, kept

    def _plainly(self, text: str) -> str:
        """What a tool said, without the name of a folder on this computer."""
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

    @tool
    def check_outline(self, outline):
        """Check a draft of the outline. Nothing is kept."""
        return self._tried('outline', as_json(outline, 'outline')[1])

    @tool
    def submit_outline(self, outline):
        """Hand the outline in. It is checked the same way and kept when nothing is left to
        put right."""
        name, _ = self._spec('outline')
        return self._hand_in(name, as_json(outline, 'outline')[1])

    # --- a deck: how it is drawn ---

    @tool
    def check_section(self, section):
        """Compile a draft of the section without rendering it. Free."""
        return self._tried('section', section)

    @tool
    def preview_section(self, section):
        """Render a draft of the section and return a picture of every slide."""
        _, spec = self._spec('section')
        most, state = spec.get('previews') or build.PREVIEWS, self._state()
        used = state.get('previews', 0)
        if used >= most:
            raise Refusal(f'You have used all {most} previews. Hand in the version you last '
                          'previewed, with submit_section.')
        drawn, text = as_json(section, 'section')
        problems, _, _, kept = self._validate(spec, text)
        if problems:
            return False, ('Nothing was rendered, and this did not use up a preview. Put '
                           'these right first:\n- ' + '\n- '.join(problems))
        built = self.folder / 'builds' / f'{used + 1}-{secrets.token_hex(3)}'
        taken = self.folder / 'previews' / built.name
        for new in (built, taken):   # the slides tool makes a folder, and not what holds it
            new.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.slides().compile(_draft(self.folder / 'drafts', 'preview', kept),
                                  spec['brand'], folder=built, **outlined(spec))
            found = render(self.slides(), built, taken, spec)
            slides = pictures(found, taken, self.folder / 'shown')
        except WorkspaceError as refusal:
            lines = [self._plainly(line) for line in said_no(refusal)]
            return False, ('The slides compile but could not be rendered, and this did not '
                           'use up a preview:\n- ' + '\n- '.join(lines))
        finally:  # a build and a render hold a deck of several megabytes each
            shutil.rmtree(built, ignore_errors=True)
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
        if spec.get('user_first'):
            return True, '\n'.join(lines[:-1]) + '\nRendered for the person. Submit this version without AI pixel review.'
        return Shown(True, '\n'.join(lines),
                     [self.folder / 'shown' / f"{slide['number']}.png" for slide in slides])

    @tool
    def search_icons(self, words, limit=5):
        """Search the brand's icons by a word or two."""
        self._spec('section')
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
        return True, (f'Icons for "{words}". Use an ID as the icon of an icon node:\n'
                      + '\n'.join(f"- {icon.get('id')}: {icon.get('name')}"
                                  + (f" ({icon['category']})" if icon.get('category') else '')
                                  for icon in found))

    @tool
    def submit_section(self, section, changed='', bothers=''):
        """Hand the section in. It must be the version last previewed."""
        name, spec = self._spec('section')
        drawn, text = as_json(section, 'section')
        state = self._state()
        left = (spec.get('previews') or build.PREVIEWS) - state.get('previews', 0)
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
        return accepted

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
        data = picture(slide['image'])
        state = self._state()
        hashes = dict(state.get('looked_hashes') or {})
        hashes[str(wanted)] = hashlib.sha256(data).hexdigest()
        home.write_json(self.folder / 'state.json', {
            **state, 'looked': sorted({*state.get('looked', []), wanted}), 'looked_hashes': hashes})
        return Shown(True, f"Slide {wanted}, `{slide['id']}`: \"{slide['title']}\".",
                     [slide['image']])

    @tool
    def look_at_deck(self):
        """The current contact sheet, for a fresh whole-deck consistency check."""
        review = self._review()
        if not review.get('sheet'):
            raise Refusal('This render has no whole-deck picture. Inspect every slide instead.')
        data = picture(review['sheet'])
        state = self._state()
        home.write_json(self.folder / 'state.json', {**state, 'looked_deck': hashlib.sha256(data).hexdigest()})
        return Shown(True, 'The current whole deck. Check consistency and regressions.', [review['sheet']])

    @tool
    def submit_assessment(self, findings, weakest=None):
        """Hand in every "no" of the review. It is recorded against this exact render."""
        review = self._review()
        self._looked(review)
        given = as_json(findings if findings not in (None, '') else [], 'list of findings')[0]
        named = as_json(weakest if weakest not in (None, '') else [], 'list of slides')[0]
        if not isinstance(given, list) or not isinstance(named, list):
            raise Refusal('findings and weakest are each a list.')
        problems, kept = [], []
        for finding in given:
            found, why = build.checked(finding, review['slides'], review_questions(review))
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
                        {'findings': kept, 'weakest': named, 'coverage': home.read_json(recorded, {}).get('coverage')})
        return True, f'Recorded: {len(kept)} finding{"" if len(kept) == 1 else "s"}.{said}'

    def _looked(self, review: dict) -> None:
        """Every changed/neighbor slide and the current whole deck must actually be shown."""
        self._allowed('assessment', 'The assessment')
        state = self._state()
        required = review.get('inspect', [slide['id'] for slide in review['slides']])
        unseen = [str(slide['number']) for slide in review['slides'] if slide['id'] in required
                  and (slide['number'] not in state.get('looked', []) or
                       (state.get('looked_hashes') or {}).get(str(slide['number'])) != hashlib.sha256(picture(slide['image'])).hexdigest())]
        if unseen:
            raise Refusal('Look at every slide first. Not looked at yet: ' + ', '.join(unseen) + '.')
        for slide in review['slides']:
            reused = (review.get('reused') or {}).get(slide['id'])
            if reused and reused['image_sha256'] != hashlib.sha256(picture(slide['image'])).hexdigest():
                raise Refusal('A reused preview changed. Rebuild the preview before reviewing again.')
        if review.get('sheet') and state.get('looked_deck') != hashlib.sha256(picture(review['sheet'])).hexdigest():
            raise Refusal('Look at the current whole deck with look_at_deck before handing in its review.')

    def _record(self, review: dict, kept: list, named: list, recorded: Path) -> list[str]:
        """Record an assessment with the slides tool, against the render it is of. Returns
        what the tool refused in it."""
        coverage = []
        for slide in review['slides']:
            reused = (review.get('reused') or {}).get(slide['id'])
            note = ('Reused verified native inspection from deck ' + reused['from_deck'] + '; checked current whole-deck consistency. ' if reused else 'Inspected native pixels and all review questions. ') + f"Slide {slide['number']}: {slide['title']}"
            coverage.append({'id': slide['id'], 'number': slide['number'],
                'answers': [not any(f['slide'] == slide['id'] and f['question'] == n for f in kept) for n in range(1, len(review_questions(review)) + 1)],
                'note': note, 'image_sha256': hashlib.sha256(picture(slide['image'])).hexdigest(),
                **({'reused_from': reused['from_deck']} if reused else {})})
        assessment = {'slides': [{key: value[key] for key in ('id', 'answers', 'note')} for value in coverage], 'deckSha256': review['deck'], 'reviewer': 'independent',
                      'weakest': named, 'findings': [
                          {key: finding[key] for key in ('slide', 'question', 'severity',
                                                         'note', 'fix')
                           if finding[key] is not None} for finding in kept]}
        packet = home.read_json(Path(review['preview']) / 'critic.json', {})
        if packet.get('schema') == 1:
            # Older runtimes accept only negative findings. Keep complete local coverage,
            # while preserving their original wire contract; render reuse stays disabled.
            assessment.pop('slides')
        path = _draft(self.folder / 'drafts', 'assessment',
                      json.dumps(assessment, indent=2, ensure_ascii=False) + '\n')
        try:
            self.slides().critique(Path(review['preview']), path)
        except WorkspaceError as refusal:
            return [self._plainly(line) for line in said_no(refusal)]
        home.write_json(recorded, {'findings': kept, 'weakest': named,
            'coverage': {'questions': list(review_questions(review)), 'slides': coverage}})
        return []

    # --- sources ---

    @tool
    def save_source(self, url):
        """Fetch a public page or PDF, keep it, and return the start of its text."""
        if not self.job['fetch']:
            raise Refusal('This job cannot fetch pages. Work from what you were given.')
        url, index = str(url).strip(), self._index()
        known = next((item for item in index if url in (item['url'], item.get('asked'))), None)
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
        """The public addresses a web address leads to. Refuses any other kind, and, for a
        job whose research keeps to your sites, any address that is not under one of them:
        `redirected_from` is the hop that led here."""
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
        # Where research may look, checked before the name is even looked up. A job set up
        # before research_from has no choice, and fetches any public page as it did.
        if self.job.get('research') is not None:
            said = research_sites.refused(url, self.job['research'], redirected_from)
            if said:
                self._outside(url, redirected_from)
                raise Refusal(said)
        try:
            addresses = self.resolver(host)
        except (OSError, UnicodeError) as failure:
            raise Refusal(f'Could not look up {host} ({failure}).')
        if not addresses or not all(public(address) for address in addresses):
            raise Refusal('That address is not on the public internet, so it was not '
                          'fetched.')
        return addresses

    def _outside(self, url: str, redirected_from: str | None) -> None:
        """Note a page refused for being outside the sites, for the research stop."""
        state = self._state()
        kept = list(state.get('outside') or [])
        if url not in (entry.get('url') for entry in kept) and len(kept) < MAX_SOURCES:
            kept.append({'url': clip(url, ADDRESS), 'redirected_from': redirected_from})
            home.write_json(self.folder / 'state.json', {**state, 'outside': kept})

    def _fetch(self, url: str) -> tuple[str, dict, bytes]:
        """A page's final address, headers and body, with every hop on the way checked."""
        came_from = None
        for _ in range(MAX_HOPS + 1):
            # Each hop is checked and asked for without its fragment, which is never sent:
            # parsers split at the first '#' and urllib at the last, so a fragment left in
            # could carry a path the check never saw.
            try:
                url = research_sites.fetchable(url)
            except ValueError:
                raise Refusal('That is not a web address.') from None
            status, headers, data = self._ask(url, self._checked(url, came_from))
            if status in REDIRECTS and headers.get('location'):
                came_from, url = url, urllib.parse.urljoin(url, headers['location'])
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
    def submit_finding(self, item, status, summary, limits='', evidence=None, headline=None):
        """Hand back the finding for the job's question, with exact quotes."""
        wanted = self.job['finding']
        if not wanted:
            raise Refusal('This job does not answer a research question.')
        if str(item).strip() != wanted:
            raise Refusal(f'This job answers {wanted}, not "{item}".')
        self._allowed('finding', 'This finding')
        passages = self._passages(evidence)
        problems, kept = [], []
        # U+FEFF is whitespace to harness-research's trim but not to split(), so it goes first.
        parts = headline.replace('\ufeff', ' ').split() if isinstance(headline, str) else []
        headline, words = ' '.join(parts), len(parts)
        units = len(headline.encode('utf-16-le', 'surrogatepass')) // 2
        if not words:
            problems.append('The headline is empty: give the answer in one sentence.')
        elif words > HEADLINE:
            problems.append(f'The headline is {words} words. Give the answer in one sentence '
                            f'of at most {HEADLINE} words.')
        elif units > HEADLINE_UNITS:
            problems.append(f'The headline is {units:,} characters. Give the answer in one '
                            f'sentence of at most {HEADLINE_UNITS} characters.')
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
            'item': wanted, 'status': status, 'summary': summary.strip(),
            'headline': headline, 'limits': limits, 'evidence': kept})
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
    _described('submit_review', 'After your draft is accepted, give your own honest notes '
               'on it for the person who will review it: where it is weakest, what is '
               'missing, what to look at.', {'text': TEXT}, ['text']),
    _described('check_outline', 'Check a draft of the outline. Returns what to put right. '
               'Nothing is kept: use it until nothing is left to put right.',
               {'outline': TEXT}, ['outline']),
    _described('submit_outline', 'Hand the outline in, whole, as JSON text. It is checked the '
               'same way and kept only when nothing is left to put right.',
               {'outline': TEXT}, ['outline']),
    _described('check_section', 'Compile a draft of your section, whole, as JSON text, '
               'without rendering it. Returns every problem to put right. Free to use as '
               'often as you need.', {'section': TEXT}, ['section']),
    _described('preview_section', 'Compile and render your section and return a picture of '
               'every slide, with what the renderer found. Slow, and limited in number.',
               {'section': TEXT}, ['section']),
    _described('search_icons', "Search the brand's icons by one or two plain words. "
               'Returns the ID to use for each.', {'words': TEXT, 'limit': NUMBER},
               ['words']),
    _described('submit_section', 'Hand your section in. It must be exactly the version you '
               'last previewed. Say what you changed after looking at the pictures, and '
               'what still bothers you.',
               {'section': TEXT, 'changed': TEXT, 'bothers': TEXT}, ['section']),
    _described('look_at_deck', 'Look at the current whole deck to check consistency and regressions.', {}, []),
    _described('look_at_slide', 'Look at one rendered slide at full size, by its number.',
               {'number': NUMBER}, ['number']),
    _described('submit_assessment', 'Hand in your review: one finding for each question '
               'you answered no. It is recorded against this exact render.',
               {'findings': {'type': 'array', 'items': {
                   'type': 'object', 'properties': {
                       'slide': TEXT, 'question': NUMBER,
                       'severity': {'type': 'string', 'enum': list(build.SEVERITIES)},
                       'about': {'type': 'string', 'enum': list(build.ABOUT)},
                       'note': TEXT, 'fix': TEXT},
                   'required': ['slide', 'question', 'severity', 'note']}},
                'weakest': {'type': 'array', 'items': TEXT}}, ['findings']),
    _described('save_source', 'Fetch a public web page or PDF, keep it, and return the '
               'start of its text. Only sources saved this way count as evidence. Where your '
               'task names allowed sites, only a page under one of them is saved.',
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
                'headline': TEXT, 'summary': TEXT, 'limits': TEXT,
                'evidence': {'type': 'array', 'items': {
                    'type': 'object', 'properties': {'source_id': TEXT, 'quote': TEXT},
                    'required': ['source_id', 'quote']}}},
               ['item', 'status', 'headline', 'summary']),
    _described('ask_person', 'Ask the person one question you cannot work without an '
               'answer to. This ends your job: stop as soon as you have asked.',
               {'question': TEXT}, ['question']),
]
NAMES = tuple(entry['name'] for entry in TOOLS)


# --- the server ------------------------------------------------------------------------


if __name__ == '__main__':
    # Started by its path, this file is __main__. The server runs as runner.worker_tools,
    # the one module every check and every registration uses.
    from runner import worker_tools as served  # noqa: E402
    sys.exit(served.main())
