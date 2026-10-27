"""The deck folder and its run record.

What a caller needs to know
---------------------------
    checked = decks.check_form(sent, brands)   # the form, checked; WorkspaceError says what is wrong
    root = decks.create(workspace, checked)    # makes <root>/<id>/ and commits it
    run = decks.read_run(root)                 # the run record: run.json in the deck's folder
    decks.write_run(root, run)                 # atomic; a reader never sees half a record
    decks.deck_id(workspace, 'My talk')        # 'my-talk', or 'my-talk-2' when that is taken,
                                               # here or on the remote branch as last fetched
    decks.write_index(workspace)               # <root>/README.md: one row per deck
    decks.research_from(form)                  # where its research may look, old forms too

A deck is a folder holding `run.json` (decks.RUN, what marks it), `intake.md` (the form, in
words), and `README.md`. The form keeps only a short reference to the source (its kind and
a name or link); uploaded bytes and pasted text belong to documents.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError, write_atomic

from runner import gitstate, settings

ROUTES = ('scratch', 'document', 'existing')
DELIVERIES = ('live', 'reading')     # a talk, or a handout read on its own
DELIVERY_BY_ROUTE = {'scratch': 'live', 'document': 'reading', 'existing': 'reading'}
LEVELS = ('brand-only', 'polish', 'redesign', 'rework', 'selected')
OUTPUTS = ('google', 'pptx')
LIMITS = {'title': 120, 'audience': 2000, 'goal': 2000, 'notes': 4000, 'minutes': 240,
          'selected': 4000}
RUN = 'run.json'            # what marks a deck's folder
DELIVER = 'deliver.json'    # written when the deck is delivered
SCHEMA = 1
SOURCES = {'document': ('upload', 'paste', 'google'), 'existing': ('upload', 'google')}
FLOWS = ('desk',)               # a deck started from the desk's start; none is the gated flow
LOOKS = ('pick', 'default')     # the start's look: picked once the samples are drawn, or not
READINGS = ('spec', 'material')  # how the start said a document is read, where it said
WRONG_LOOK = ('Choose to pick the look when the samples are drawn, or to use the brand’s '
              'default look.')
WRONG_READING = 'Only a document is read as a script for the slides or as material.'


def on_desk(run: dict) -> bool:
    """Whether a deck is on the desk: started from the desk's start (or opened there once it
    was delivered). Every other deck keeps the gated flow and its screens."""
    return isinstance(run, dict) and run.get('flow') == 'desk'


def user_first(run: dict) -> bool:
    return (run.get('form') or {}).get('initial_review') == 'user-first' and not run.get('review_requested')


# --- the form ------------------------------------------------------------------------------

def _text(sent: dict, key: str, label: str, required: bool = False) -> str:
    value = sent.get(key)
    if value is None or value == '':
        if required:
            raise WorkspaceError(f'Give the deck a {label}.')
        return ''
    if not isinstance(value, str):
        raise WorkspaceError(f'The {label} must be text.')
    value = value.strip()
    if required and not value:
        raise WorkspaceError(f'Give the deck a {label}.')
    if len(value) > LIMITS[key]:
        raise WorkspaceError(f'The {label} can be at most {LIMITS[key]} characters.')
    return value


def _source(sent: dict, route: str) -> dict:
    source = sent.get('source')
    kinds = SOURCES[route]
    what = 'document to build from' if route == 'document' else 'deck to improve'
    if not isinstance(source, dict) or source.get('kind') not in kinds:
        raise WorkspaceError(f'Say where the {what} comes from: {", ".join(kinds)}.')
    kind = source['kind']
    if kind == 'upload':
        name = source.get('name')
        if not isinstance(name, str) or not name.strip():
            raise WorkspaceError(f'Name the file for the {what}.')
        return {'kind': 'upload', 'name': name.strip()[:200]}
    if kind == 'google':
        link = source.get('link')
        if not isinstance(link, str) or not link.strip():
            raise WorkspaceError(f'Give the Google link for the {what}.')
        return {'kind': 'google', 'link': link.strip()[:500]}
    text = source.get('text')
    if not isinstance(text, str) or not text.strip():
        raise WorkspaceError(f'Paste the text for the {what}.')
    return {'kind': 'paste'}


RESEARCH_SOURCES = ('documents', 'both')    # what a form sent before research_from


def research_from(form: dict, scope: str | None = None,
                  documents_given: bool | None = None) -> dict | None:
    """Where a deck's research may look, in studio_core.research_sites' shape
    ({'documents', 'sites', 'web'}), or None for a deck with no research. A deck saved before
    research_from is read from its research_sources, else from its research plan's `scope`,
    else as research then looked: the public web, with a document's own documents. Your
    documents count only where they were given (`documents_given`, by default a deck made
    from a document). A choice that would look nowhere reads as the documents alone, so
    nothing is fetched."""
    from studio_core import research_sites
    form = form if isinstance(form, dict) else {}
    if form.get('route') == 'existing' or ('research' in form and not form['research']):
        return None
    if documents_given is None:
        documents_given = form.get('route', 'document') == 'document'
    given = form.get('research_from')
    if not isinstance(given, dict):
        given = research_sites.legacy(form.get('research_sources') or scope or 'public-web') \
            or research_sites.legacy('public-web')
    found = research_sites.effective(given, documents_given)
    if not (found['documents'] or found['sites'] or found['web']):
        return {'documents': True, 'sites': [], 'web': False}
    return found


def _research_from(sent: dict, route: str) -> dict:
    """The form's research_from, checked: sites canonical, the list pinned as sent. A form
    sent the old way, with research_sources or nothing, is taken in the new shape."""
    from studio_core import research_sites
    given = sent.get('research_from')
    if given is None:
        # research_sources was asked only for a document; elsewhere research used the web.
        old = sent.get('research_sources') if route == 'document' else None
        if old is not None and old not in RESEARCH_SOURCES:
            raise WorkspaceError(research_sites.EMPTY)
        given = research_sites.legacy(old) if old else (
            {'documents': True} if route == 'document' else {'web': True})
    try:
        return research_sites.choice(given, documents_given=route == 'document')
    except ValueError as error:
        raise WorkspaceError(str(error)) from None


def research_questions(sent) -> list[str]:
    given = sent.get('research_questions') or []
    if isinstance(given, str):
        given = given.splitlines()
    if not isinstance(given, list) or not all(isinstance(line, str) for line in given):
        raise WorkspaceError('Write the research questions one a line.')
    lines = [' '.join(line.split()) for line in given if line.strip()]
    if len(lines) > 8:
        raise WorkspaceError('Ask research at most 8 questions.')
    if any(len(line) > 300 for line in lines):
        raise WorkspaceError('Keep each research question to 300 characters.')
    return lines


def check_form(sent: dict, brands: list | None) -> dict:
    """The form, checked and trimmed. Raises WorkspaceError with one sentence otherwise.
    `brands` are those the brand skill lists, or None with no brand skill: a deck can then
    still be started, with its brand left to the brand step, or named as a short word the
    brand skill will be asked for there."""
    if not isinstance(sent, dict):
        raise WorkspaceError('The form was not understood.')
    route = sent.get('route')
    if route not in ROUTES:
        raise WorkspaceError(f'Choose how to start: {", ".join(ROUTES)}.')
    title = _text(sent, 'title', 'title', required=True)
    audience = _text(sent, 'audience', 'audience')
    goal = _text(sent, 'goal', 'goal')
    notes = _text(sent, 'notes', 'brief')
    minutes = sent.get('minutes')
    if minutes in (None, ''):
        minutes = None
    else:
        if isinstance(minutes, bool):
            raise WorkspaceError('The length must be a whole number of minutes.')
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            raise WorkspaceError('The length must be a whole number of minutes.') from None
        if not 1 <= minutes <= LIMITS['minutes']:
            raise WorkspaceError(f'The length must be between 1 and {LIMITS["minutes"]} minutes.')
    brand, variant = sent.get('brand'), sent.get('variant')
    if brands is None:
        brand = None if brand in (None, '') else settings.check_word(brand, 'brand')
        variant = None if variant in (None, '') or brand is None \
            else settings.check_word(variant, 'variant')
    else:
        chosen = next((one for one in brands if one.get('brand') == brand), None)
        if chosen is None:
            raise WorkspaceError('That brand is not one your brand skill has.')
        listed = chosen.get('variants') or []
        if not listed and variant in (None, ''):
            variant = None      # a brand with no variants is drawn as it is
        elif variant not in listed:
            raise WorkspaceError(f'The {brand} brand has no "{variant}" variant.')
    output = sent.get('output')
    if output not in OUTPUTS:
        raise WorkspaceError(f'Choose an output: {", ".join(OUTPUTS)}.')
    research = bool(sent.get('research'))
    # Asked once, here: a talk ('live') or a handout ('reading'). A deck from an idea or a
    # brief is a talk unless the person says otherwise; one made from a document or an
    # existing deck, a handout. build.delivery is where every step reads it.
    delivery = sent.get('delivery')
    if delivery in (None, ''):
        delivery = DELIVERY_BY_ROUTE[route]
    if delivery not in DELIVERIES:
        raise WorkspaceError('Say whether the deck is for a talk or a handout.')
    checked = {'route': route, 'title': title, 'audience': audience, 'goal': goal,
               'minutes': minutes, 'brand': brand, 'variant': variant, 'output': output,
               'research': research, 'delivery': delivery, 'notes': notes}
    if research and route != 'existing':
        # Where research may look: your documents, your sites and/or the public web. The
        # sites are the deck's own list, kept as sent: a later change to the shared list
        # never changes a deck that has started.
        checked['research_from'] = _research_from(sent, route)
    checked['research_questions'] = research_questions(sent)
    # Only the form's own choice shows the first draft before its review: nothing in the
    # goal's words flips it.
    mode = sent.get('initial_review')
    if mode is not None:
        if mode not in ('standard', 'user-first'):
            raise WorkspaceError('Choose a checked deck, or the first draft before the check.')
        if route == 'existing' and sent.get('level') == 'selected' and mode == 'user-first':
            raise WorkspaceError('First-draft mode applies to a full build, not a selected-slide patch.')
        checked.update(initial_review=mode, initial_review_source='form')
    if route == 'existing':
        if research:
            raise WorkspaceError('Research is not offered when improving an existing deck.')
        level = sent.get('level')
        if level not in LEVELS:
            raise WorkspaceError(f'Choose how much to change: {", ".join(LEVELS)}.')
        checked['level'] = level
        if level == 'selected':
            selected = _text(sent, 'selected', 'selected changes', required=True)
            checked['selected'] = selected
    if route in SOURCES:
        checked['source'] = _source(sent, route)
    _desk_form(sent, checked)
    return checked


def _desk_form(sent: dict, checked: dict) -> None:
    """What the desk's start adds to the form: its flow, the look it chose and, for a
    document, how the start said to read it. A desk deck is always built as a first draft:
    the deck check runs only when the person asks for it, so a desk form's own choice of
    that is not read."""
    flow = sent.get('flow')
    if flow in (None, ''):
        if sent.get('look') not in (None, '') or sent.get('reading') not in (None, ''):
            raise WorkspaceError('The look and the reading are chosen on the desk’s start.')
        return
    if flow not in FLOWS:
        raise WorkspaceError('A deck is started on the desk, or without a flow.')
    look = sent.get('look')
    look = 'pick' if look in (None, '') else look
    if look not in LOOKS:
        raise WorkspaceError(WRONG_LOOK)
    checked.update(flow=flow, look=look, initial_review='user-first',
                   initial_review_source='desk')
    reading = sent.get('reading')
    if reading not in (None, ''):
        if checked['route'] != 'document' or reading not in READINGS:
            raise WorkspaceError(WRONG_READING)
        checked['reading'] = reading


def review_choice(sent: dict) -> tuple:
    """Where the form says this deck stops: (level, seen, default). `level` is None when the
    form chose none, and the deck then takes the shared level. `seen` is the shared level the
    form read, and `default` whether to make `level` the one new work starts at in every
    studio. None of them is kept in the deck's form."""
    from studio_core import review_policy
    sent = sent if isinstance(sent, dict) else {}
    level = sent.get('review_level')
    if level in (None, ''):
        level = None
    else:
        try:
            review_policy.check({'level': level})
        except ValueError as error:
            raise WorkspaceError(str(error)) from None
    default = sent.get('review_default', False)
    if default not in (True, False):
        raise WorkspaceError('Say whether to use this level for new work: true or false.')
    if default and level is None:
        raise WorkspaceError('Choose where this deck stops before using it for new work.')
    return level, sent.get('review_seen'), default


# --- ids -----------------------------------------------------------------------------------

def deck_id(space, title: str) -> str:
    """A slug of the title, numbered when a folder of that name is already here or on the
    remote branch as last fetched."""
    base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:48].strip('-') or 'deck'
    n, ident = 1, base
    while (space.deck(ident).exists() or gitstate.known(space, space.deck(ident))
           or gitstate.theirs(space, f'{ident}/{RUN}') is not None):
        n += 1
        suffix = f'-{n}'
        ident = base[:48 - len(suffix)].rstrip('-') + suffix
    return ident


# --- the run record ------------------------------------------------------------------------

def read_run(root: Path) -> dict:
    return json.loads((Path(root) / RUN).read_text(encoding='utf-8'))


def write_run(root: Path, run: dict) -> None:
    write_atomic(Path(root) / RUN, json.dumps(run, indent=2, ensure_ascii=False) + '\n')


def _new_run(ident: str, form: dict) -> dict:
    made = {'schema': SCHEMA, 'id': ident, 'title': form['title'], 'route': form['route'],
            'form': form, 'created': home.now(), 'driver': None, 'gates': {}, 'steps': {},
            'classified': None, 'look': None, 'revisions': [], 'halted': None,
            'agent': None, 'model': None, 'level_of_effort': None, 'limits': {}}
    if form.get('flow'):
        made['flow'] = form['flow']
    return made


# --- the files -----------------------------------------------------------------------------

def _source_words(source: dict) -> str:
    if source['kind'] == 'upload':
        return f"uploaded file {source['name']}"
    if source['kind'] == 'google':
        return f"Google link {source['link']}"
    return 'pasted text'


NOT_OFFERED = ('Your brand skill does not offer the brand {brand}, so this deck cannot be made '
               'in it: start a deck in one of the brands it lists ({listed}), or install a '
               'brand skill that offers {brand} and retry.')
NO_VARIANT = ('Your brand skill offers no "{variant}" variant of {brand}, so this deck cannot be '
              'made in it: start a deck in one of the variants it lists ({listed}), or install '
              'a brand skill that offers it and retry.')


def default_brand(brand: str | None, variant: str | None, brands) -> dict:
    """The brand and variant offered first: `brand` and `variant` where the brand skill
    has them, else the first it lists, else the first variant of that brand. With nothing
    listed, they stay as they are. No brand is named here. For a deck's own brand, see
    `deck_brand`."""
    listed = [entry for entry in brands or [] if isinstance(entry, dict) and entry.get('brand')]
    if not listed:
        return {'brand': brand, 'variant': variant}
    entry = next((one for one in listed if one.get('brand') == brand), listed[0])
    variants = [str(one) for one in entry.get('variants') or []]
    return {'brand': entry['brand'],
            'variant': variant if variant in variants else (variants[0] if variants else None)}


def deck_brand(form: dict, brands, brand: str | None, variant: str | None) -> dict:
    """The brand and variant a deck is made in, once the brand skill lists its brands. A
    brand or variant the deck's form names must be one the brand skill offers, or this
    refuses with NOT_OFFERED or NO_VARIANT. Only one left empty is chosen: `brand` and
    `variant` (what Settings names) where the skill has them, else its first."""
    listed = [entry for entry in brands or [] if isinstance(entry, dict) and entry.get('brand')]
    named = form.get('brand')
    if not named:
        return default_brand(brand, form.get('variant') or variant, listed)
    entry = next((one for one in listed if one.get('brand') == named), None)
    if entry is None:
        raise WorkspaceError(NOT_OFFERED.format(brand=named, listed=', '.join(
            str(one['brand']) for one in listed) or 'none'))
    variants = [str(one) for one in entry.get('variants') or []]
    wanted = form.get('variant')
    if wanted and wanted not in variants:
        raise WorkspaceError(NO_VARIANT.format(variant=wanted, brand=named,
                                               listed=', '.join(variants) or 'none'))
    if not wanted:
        wanted = variant if variant in variants else (variants[0] if variants else None)
    return {'brand': named, 'variant': wanted}


def name_brand(root: Path, form: dict) -> None:
    """Say in the deck's intake which brand and variant it is made in, once they are
    chosen."""
    path = Path(root) / 'intake.md'
    try:
        lines = path.read_text(encoding='utf-8').split('\n')
    except OSError:
        return
    if '## Brand' in lines and lines.index('## Brand') + 1 < len(lines):
        lines[lines.index('## Brand') + 1] = brand_words(form)
        write_atomic(path, '\n'.join(lines))


def brand_words(form: dict) -> str:
    """The deck's brand and variant, or what stands for them until the brand step chooses."""
    if not form.get('brand'):
        return 'your brand, chosen when the brand skill is installed'
    return f"{form['brand']} ({form['variant']})" if form.get('variant') else form['brand']


def intake(form: dict) -> str:
    parts = [f"# {form['title']}", '', '## Title', form['title'], '',
             '## Route', form['route']]
    if 'source' in form:
        parts += ['', f'Source: {_source_words(form["source"])}']
    if form['audience']:
        parts += ['', '## Audience', form['audience']]
    if form['goal']:
        parts += ['', '## Goal', form['goal']]
    if form['minutes']:
        parts += ['', '## Length', f"{form['minutes']} minutes"]
    if form.get('delivery'):
        parts += ['', '## Delivery', 'a talk' if form['delivery'] == 'live' else 'a handout']
    parts += ['', '## Brand', brand_words(form),
              '', '## Output', form['output']]
    if form['route'] != 'existing':
        from studio_core import research_sites
        looks = research_from(form)
        parts += ['', '## Research', 'yes, ' + research_sites.summary(looks) if looks else 'no']
    if 'level' in form:
        parts += ['', '## Change level', form['level']]
    if 'selected' in form:
        parts += ['', '## Selected changes', form['selected']]
    return '\n'.join(parts) + '\n'


def delivered(root: Path) -> dict | None:
    """What was delivered: deliver.json in the deck's folder, or None."""
    try:
        data = json.loads((Path(root) / DELIVER).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def state(run: dict, root: Path | None = None) -> str:
    """Where a deck stands, in a few words."""
    if root is not None and (Path(root) / DELIVER).is_file():
        return 'finished'
    if run.get('halted'):
        return 'stopped'
    gates = run.get('gates') or {}
    for name, gate in gates.items():
        if gate.get('state') == 'waiting':
            return f'waiting on {name}'
    for name, gate in gates.items():
        if gate.get('state') == 'changes':
            return f'changes asked at {name}'
    return 'in progress'


def _where(deliver: dict) -> str:
    """Where a delivered deck is: its Google Slides link, or the PowerPoint file's name."""
    if deliver.get('output') == 'pptx':
        return str(deliver.get('pptx') or 'PowerPoint file')
    return str(deliver.get('url') or '')


def readme(run: dict, deliver: dict | None) -> str:
    form = run['form']
    lines = [f"# {run['title']}", '', f"Route: {run['route']}",
             f"Brand: {brand_words(form)}", f"Output: {form['output']}",
             f"State: {'finished' if deliver else state(run)}"]
    if deliver:
        where = _where(deliver)
        if where:
            lines += ['', f'Delivered: {where}']
    return '\n'.join(lines) + '\n'


def create(space, form: dict) -> Path:
    """Make the deck's folder, with its intake, run record and README, and commit it."""
    ident = deck_id(space, form['title'])
    root = space.deck(ident)
    root.mkdir(parents=True)
    run = _new_run(ident, form)
    write_atomic(root / 'intake.md', intake(form))
    write_run(root, run)
    write_atomic(root / 'README.md', readme(run, None))
    gitstate.commit(space, f"{form['title']}: start the deck", [ident])
    return root


def index(space) -> str:
    rows = []
    for folder in sorted(space.root.iterdir()) if space.root.is_dir() else []:
        if not (folder / RUN).is_file():
            continue
        try:
            run = read_run(folder)
        except (OSError, ValueError):
            continue
        title = run.get('title', folder.name).replace('|', '\\|')
        link = f"[{folder.name}]({folder.name}/README.md)"
        done = delivered(folder)
        if done and done.get('output') == 'pptx':
            link += ' · PowerPoint file'
        elif done and done.get('url'):
            link += f" · [Google Slides]({done['url']})"
        rows.append(f"| {title} | {run.get('route', '')} | {state(run, folder)} | {link} |")
    return '\n'.join(['# Presentations', '', '| Deck | Route | State | Link |',
                      '| --- | --- | --- | --- |'] + rows) + '\n'


def write_index(space) -> None:
    write_atomic(space.root / 'README.md', index(space))
