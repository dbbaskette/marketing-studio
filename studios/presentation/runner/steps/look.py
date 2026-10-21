"""The look a deck is drawn in, chosen before any slide is designed: the brand draws one slide
of the outline in each of its looks, and the person picks one in their words. A brand too old
to offer looks shows the deck's cover in it instead, so the person can see it is the brand
they meant, and choose another if not.

What a caller needs to know
---------------------------
    shown = look.draw_sample(root, run, slides, renderer)   # work/look/sample.png; work/ only
    look.show_sample(root, run)                             # look.md, and the gate waiting
    look.preview_sample(root, run, slides, renderer)        # the two together
    look.rebrand(root, run, brand, variant, brands)         # another brand: the form, brand/
    look.approve(root, run, note=None)                      # the gate approved

- `draw_looks`, `choose`, `choose_default` and `approve` are the brand's look step, as
  their own docstrings say. Looks that cannot be rendered are drawn again without pictures,
  so that the brand's default can be chosen knowingly and recorded as never seen rendered.
- For a brand without looks, no look is chosen. The sample is the outline's cover, with its approved title and
  subtitle, on the template layout the build gives a cover (`build.layouts`), in the brand's
  own direction (`deck_direction.of_file`, else `build.DIRECTION`). An outline with no
  cover is shown the deck's title on one. Nothing is kept from it: when the deck is built, every slide's layout is designed
  from what that slide says.
- `draw_sample` compiles and previews the cover in work/look/ (never shared) and keeps its
  picture as work/look/sample.png (SAMPLE). Previews are taken one at a time, as
  `build.how` says.
- `show_sample` writes look.md (shared), which names the brand, and sets gate:look waiting.
- `rebrand` puts another brand or variant the brand skill lists into the deck's form and
  intake.md, and removes the exported contract in brand/, so the next step that needs the
  brand exports the one chosen. It refuses one the brand skill does not list, and the one
  the deck is made in already.
- `approve` puts the person's words of approval into outline.json (`approval`), with the
  chosen look's direction, house style and lead layouts, or the brand's default where none
  was chosen, keeps in the run whether the look was seen rendered and who chose it, and
  approves the gate.
"""
from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import deck_direction, deck_flow
from workspace import WorkspaceError, write_atomic

from runner import decks, worker_tools
from runner.jobs import sha256_of
from runner.steps import build, outline as outline_step

GATE = 'gate:look'
OUTLINE = outline_step.OUTLINE
FOLDER = Path('work') / 'look'
SAMPLE = FOLDER / 'sample.png'
SAMPLES = FOLDER / 'samples'     # the brand's look samples, as it rendered them
SHOWN = FOLDER / 'shown.json'    # what the gate shows of them
SHEET = FOLDER / 'sheet.png'     # every look on one sheet
CHOSEN = FOLDER / 'chosen.json'  # the look the person chose, as the brand recorded it
OLDER = ('This brand skill is too old to offer looks to choose from, so the deck is drawn '
         "in the brand's default direction, or in the slides tool's own where the brand "
         'gives none.')
NO_LOOK = 'Choose one of the looks to draw the deck in.'
AGAIN, DEFAULT = 'again', 'default'   # choices on the page: draw the looks again, or carry
                                      # on in the brand's default when none could be rendered
NO_COMMENT = 'Picked {name} on the page, with no comment.'
DEFAULT_NAME = "the brand's default"
LOOK_MD = 'look.md'
COVER = 'cover'


def _outline(root: Path) -> dict:
    found = home.read_json(root / OUTLINE, None)
    if not isinstance(found, dict):
        raise WorkspaceError('There is no approved outline to draw a sample of.')
    return found


def cover(outline: dict, title: str) -> dict:
    """The slide the sample draws: the outline's cover, or the deck's title on one."""
    found = next((one for one in build.slides_of(outline) if one.get('kind') == COVER), None)
    if found is None:
        return {'id': COVER, 'kind': COVER, 'title': outline.get('title') or title}
    return found


def composition(outline: dict, title: str, listed, direction: dict | None = None) -> dict:
    """The sample as the slides tool compiles it: the cover alone, on the template layout a
    cover is given, in the brand's own colours: `direction`, as the build will use it."""
    slide = cover(outline, title)
    laid = {'id': slide.get('id') or COVER, 'title': slide.get('title') or title,
            'layout': build.layouts(listed, [slide])[COVER], 'sources': ['outline'],
            'brief': {'rhythm': 'anchor'}}
    if slide.get('subtitle'):
        laid['subtitle'] = slide['subtitle']
    return {'version': 1, 'title': outline.get('title') or title,
            'direction': dict(direction or build.DIRECTION), 'slides': [laid]}


def draw_sample(root, run: dict, slides, renderer) -> Path:
    """Compile and preview the deck's cover in its brand, in work/look/. Only work/ is
    written. Returns the picture."""
    root = Path(root)
    brand = root / build.CONTRACT
    title = run.get('title') or 'Deck'
    shutil.rmtree(root / FOLDER, ignore_errors=True)
    folder = root / FOLDER
    try:
        folder.mkdir(parents=True)
        made = composition(_outline(root), title, slides.layouts(brand).get('layouts'),
                           deck_direction.of_file(brand))
        home.write_json(folder / 'composition.json', made)
        slides.compile(folder / 'composition.json', brand, folder=folder / 'compiled')
        found = worker_tools.render(slides, folder / 'compiled', folder / 'preview',
                                    build.how(root, run, renderer))
        first = (found.get('slides') or [None])[0]
        image = Path(str((first or {}).get('image'))).resolve()
        if (folder / 'preview').resolve() not in image.parents:
            raise WorkspaceError('The renderer drew no picture of it.')
        (root / SAMPLE).write_bytes(worker_tools.picture(image))
    except (WorkspaceError, OSError, KeyError, TypeError, ValueError) as refusal:
        shutil.rmtree(folder, ignore_errors=True)
        raise WorkspaceError(f'Your cover could not be drawn in the brand. {refusal}') \
            from None
    return root / SAMPLE


def draw_looks(root, run: dict, brand_skill, renderer, has=lambda name: False) -> dict:
    """Have the brand render a slide of the outline in each of its deck directions, in
    work/look/, and keep a picture of each and the sheet of them all for the gate. They go
    through the slides tool's own preview route (deck_flow.route): locally where this
    computer renders locally, else through Google Slides, in the tool's preview pool where
    `has` says it has one; one at a time either way. Samples that cannot be rendered are
    not a failure: what went wrong is kept for the gate, which offers to try again or carry
    on in the brand's default look. Returns what the gate shows."""
    root = Path(root)
    form = run.get('form') or {}
    how = build.how(root, run, renderer)
    routed = deck_flow.route(how.get('renderer'), has)
    shutil.rmtree(root / FOLDER, ignore_errors=True)
    folder = root / FOLDER
    folder.mkdir(parents=True)
    base = {'says': routed['says'], 'route': routed['preview'],
            'outline': sha256_of(root / OUTLINE)}
    try:
        with worker_tools.one_at_a_time(Path(how['lock'])):
            made = brand_skill.look_samples(root / OUTLINE, root / SAMPLES, form.get('brand'),
                                            form.get('variant'), preview=routed['preview'],
                                            delivery=build.delivery(run))
        manifest = home.read_json(root / SAMPLES / 'looks.json', {})
        looks = deck_flow.sampled(manifest, root / SAMPLES)
        for look in looks:
            if not look['image']:
                raise WorkspaceError(f"The brand drew no picture of the look {look['name']}.")
            (folder / f"{look['number']}.png").write_bytes(
                worker_tools.picture(Path(look.pop('image'))))
        sheet = Path(str(made.get('sheet') or manifest.get('sheet'))).resolve()
        if (root / SAMPLES).resolve() in sheet.parents and sheet.is_file():
            (root / SHEET).write_bytes(worker_tools.picture(sheet))
        shown = {**base, 'looks': looks, 'default': manifest.get('default'),
                 'slide': manifest.get('slide'), 'house': manifest.get('house') or []}
    except (WorkspaceError, OSError, KeyError, TypeError, ValueError) as refusal:
        for made_here in folder.iterdir():
            if made_here.is_dir():
                shutil.rmtree(made_here, ignore_errors=True)
            else:
                made_here.unlink(missing_ok=True)
        said = ' '.join(getattr(refusal, 'problems', None) or [str(refusal)]).strip()
        shown = {**base, 'failed': said or type(refusal).__name__,
                 'unseen': _unseen(root, run, brand_skill)}
    home.write_json(root / SHOWN, shown)
    return shown


def _unseen(root: Path, run: dict, brand_skill) -> dict:
    """The brand's looks drawn again without pictures, where they could not be rendered, so
    that a choice of its default is recorded with the brand as one nobody saw rendered:
    {'looks', 'default', 'house'}, the samples kept in SAMPLES. Empty when even that fails."""
    form = run.get('form') or {}
    shutil.rmtree(root / SAMPLES, ignore_errors=True)
    try:
        brand_skill.look_samples(root / OUTLINE, root / SAMPLES, form.get('brand'),
                                 form.get('variant'), delivery=build.delivery(run))
        manifest = home.read_json(root / SAMPLES / 'looks.json', {})
        return {'looks': [{key: value for key, value in look.items() if key != 'image'}
                          for look in deck_flow.sampled(manifest, root / SAMPLES)],
                'default': manifest.get('default'),
                'house': [str(line) for line in manifest.get('house') or ()]}
    except (WorkspaceError, OSError, KeyError, TypeError, ValueError):
        shutil.rmtree(root / SAMPLES, ignore_errors=True)
        return {}


def shown_looks(root) -> dict | None:
    """What the gate shows of the brand's looks: the looks drawn, or why none could be;
    None when the brand was not asked for any here."""
    found = home.read_json(Path(root) / SHOWN, None)
    return found if isinstance(found, dict) and (found.get('looks') or found.get('failed')) \
        else None


def chosen(root) -> dict | None:
    """The look chosen for the deck, as it was recorded, or None."""
    found = home.read_json(Path(root) / CHOSEN, None)
    return found if isinstance(found, dict) and found.get('choice') else None


def drop(root) -> None:
    """Throw the looks away, so that they are drawn again from what the outline says now."""
    shutil.rmtree(Path(root) / FOLDER, ignore_errors=True)


def choose(root, brand_skill, choice, words: str, by: str = 'page') -> dict | None:
    """Record the look chosen for the deck, in the person's words, and keep it. A look the
    brand drew is chosen with the brand, which checks the approved outline is the one its
    samples were drawn from and writes it again with the look in it (deck_flow.chosen_from
    reads it back). DEFAULT, where none could be rendered, is the brand's own default look.
    `by` is who chose: 'page' for the person, 'review-policy' for the saved level. None when
    the outline changed since the samples, which are then dropped."""
    root = Path(root)
    shown = shown_looks(root)
    if shown is None:
        raise WorkspaceError('There are no looks to choose from here.')
    if chosen(root) is not None:
        return chosen(root)
    contract = root / build.CONTRACT
    if choice == DEFAULT:
        if not shown.get('failed'):
            raise WorkspaceError(NO_LOOK)
        record = _unseen_default(root, brand_skill, shown, contract, words)
    else:
        picked = next((look for look in shown.get('looks') or () if look['id'] == choice),
                      None)
        if picked is None:
            raise WorkspaceError(NO_LOOK)
        written = root / FOLDER / f'outline-{secrets.token_hex(3)}.json'
        try:
            brand_skill.look_choose(root / SAMPLES, picked['id'], words, outline=root / OUTLINE,
                                    write=written)
        except WorkspaceError as refusal:
            if 'changed' in str(refusal).lower():
                drop(root)
                return None
            raise
        look = deck_flow.chosen_from(home.read_json(written, None),
                                     deck_direction.contract_of(contract)) or {}
        record = {'choice': picked['id'], 'name': picked['name'], 'shown': 'rendered',
                  'direction': look.get('direction') or picked['direction'],
                  'house': look.get('house') or list(shown.get('house') or ()),
                  'layouts': look.get('layouts') or picked['layouts']}
    record = {**record, 'words': words.strip(), 'by': by, 'at': home.now()}
    home.write_json(root / CHOSEN, record)
    return record


def _unseen_default(root: Path, brand_skill, shown: dict, contract: Path, words: str) -> dict:
    """The brand's default look, chosen knowingly where its samples could not be rendered:
    recorded with the brand as unrendered (`look choose --unrendered`) where it kept samples
    without pictures and takes that, else read from its deck direction record. Either way
    it is marked as nobody saw it rendered."""
    unseen = shown.get('unseen') or {}
    default = next((look for look in unseen.get('looks') or ()
                    if look['id'] == unseen.get('default')), None)
    if default and (root / SAMPLES / 'looks.json').is_file():
        written = root / FOLDER / f'outline-{secrets.token_hex(3)}.json'
        try:
            brand_skill.look_choose(root / SAMPLES, default['id'], words,
                                    outline=root / OUTLINE, write=written, unrendered=True)
        except WorkspaceError:
            written = None   # a brand that does not take it: the record is the studio's own
        if written:
            look = deck_flow.chosen_from(home.read_json(written, None),
                                         deck_direction.contract_of(contract)) or {}
            return {'choice': default['id'], 'name': default['name'], 'shown': 'unrendered',
                    'direction': look.get('direction') or default.get('direction'),
                    'house': look.get('house') or list(unseen.get('house') or ()),
                    'layouts': look.get('layouts') or default.get('layouts') or {}}
    brand_default = deck_direction.default_look(contract) or {}
    return {'choice': brand_default.get('id') or DEFAULT,
            'name': brand_default.get('id') or DEFAULT_NAME, 'shown': 'unrendered',
            **{key: brand_default.get(key) for key in ('direction', 'house', 'layouts')}}


def default_name(root, shown: dict) -> str:
    """What the brand's default look is called, for the words recorded with it."""
    unseen = shown.get('unseen') or {}
    named = next((look['name'] for look in unseen.get('looks') or ()
                  if look['id'] == unseen.get('default')), None)
    return named or (deck_direction.default_look(Path(root) / build.CONTRACT) or {}).get('id') \
        or DEFAULT_NAME


def choose_default(root, brand_skill) -> dict | None:
    """Under Automatic draft: the brand's default look, recorded with why, whether or not
    its looks could be rendered. None where the brand was not asked for looks, or where the
    outline changed since they were drawn."""
    shown = shown_looks(root)
    if shown is None:
        return None
    if chosen(root) is not None:
        return chosen(root)
    looks = shown.get('looks') or []
    default = next((look for look in looks if look['id'] == shown.get('default')),
                   looks[0] if looks else None)
    if default is None:
        # Nothing could be rendered: the default, used without anyone seeing it, and why.
        return choose(root, brand_skill, DEFAULT, deck_flow.UNRENDERED_WORDS.format(
            why=shown.get('failed') or 'no samples', name=default_name(root, shown)),
            by='review-policy')
    return choose(root, brand_skill, default['id'],
                  deck_flow.DEFAULT_WORDS.format(name=default['name']), by='review-policy')


def _markdown(form: dict, shown: dict | None = None) -> str:
    if shown and shown.get('failed'):
        return '\n'.join(['# The look', '', f'This deck is made in {decks.brand_words(form)}.',
                          '', deck_flow.LOOK_FAILED.format(why=shown['failed']), ''])
    if shown:
        lines = ['# The look', '',
                 f'This deck is made in {decks.brand_words(form)}. The brand drew one of its '
                 'slides in each of its looks. The look chosen sets the colours, what each '
                 'one means and how cards are drawn on every slide.', '']
        lines += [f"- {look['name']}" + (' (the brand\'s default)' if look['id']
                                          == shown.get('default') else '')
                  + (f": {look['useWhen']}" if look['useWhen'] else '')
                  for look in shown['looks']]
        return '\n'.join([*lines, ''])
    return '\n'.join([
        '# The brand', '',
        f'This deck is made in {decks.brand_words(form)}. Its cover is drawn here in that '
        'brand, so you can see it is the one you meant.', '', OLDER, ''])


def show_sample(root, run: dict) -> None:
    """Write look.md, which names the brand the sample is drawn in, and set the gate
    waiting."""
    root = Path(root)
    write_atomic(root / LOOK_MD, _markdown(run.get('form') or {}, shown_looks(root)))
    gate = (run.setdefault('gates', {})).get(GATE) or {}
    run['gates'][GATE] = {**gate, 'state': 'waiting', 'round': int(gate.get('round') or 0) + 1}
    decks.write_run(root, run)


def preview_sample(root, run: dict, slides, renderer) -> Path:
    """Draw the sample, then show it. A caller that must not hold its lock through the
    drawing calls `draw_sample`, then `show_sample` under its lock."""
    drawn = draw_sample(root, run, slides, renderer)
    show_sample(root, run)
    return drawn


def rebrand(root, run: dict, brand, variant, brands) -> dict:
    """Make the deck in another brand or variant the brand skill lists: the form and
    intake.md name it, and the contract exported for the old one is removed. Returns the
    form."""
    root = Path(root)
    if not isinstance(brand, str) or not brand.strip():
        raise WorkspaceError('Choose the brand to make the deck in.')
    if variant is not None and not isinstance(variant, str):
        raise WorkspaceError('Choose one of the brand\'s variants.')
    form = run.get('form') or {}
    chosen = decks.deck_brand({**form, 'brand': brand.strip(),
                               'variant': (variant or '').strip() or None}, brands, None, None)
    if (chosen['brand'], chosen['variant']) == (form.get('brand'), form.get('variant')):
        raise WorkspaceError(f'This deck is made in {decks.brand_words(chosen)} already.')
    run['form'] = {**form, **chosen}
    decks.name_brand(root, run['form'])
    shutil.rmtree(root / build.BRAND, ignore_errors=True)
    return run['form']


def approve(root, run: dict, note: str | None = None, by: str = 'page') -> None:
    """Approve the brand: the person's words of approval go into outline.json, without a
    direction of an earlier look, and the gate is approved."""
    root = Path(root)
    at = home.now()
    note = (note or '').strip() or None
    outline = _outline(root)
    said = (((run.get('gates') or {}).get('gate:outline') or {}).get('note'))
    words = [f'{"Continued automatically" if by == "review-policy" else "Approved on the page"}, {at}, in {decks.brand_words(run.get("form") or {})}.']
    picked = chosen(root)
    if picked:
        # Kept in the run, which every computer reads: whether the look was seen rendered.
        run['look_shown'] = picked.get('shown') or 'rendered'
        run['look_by'] = picked.get('by') or by
        words.append(f"Look chosen: {picked['name']} ({picked['choice']}). In their words: "
                     f"\"{picked['words']}\"")
    words += [line for line in (said, note) if line]
    # The look the person chose, or the brand's default where it offered none to choose.
    look = picked if picked and picked.get('direction') \
        else deck_direction.default_look(root / build.CONTRACT)
    for key in ('direction', 'house', 'layouts'):
        outline.pop(key, None)
    if look and look.get('direction'):
        outline['direction'] = look['direction']
        if look.get('house'):
            outline['house'] = list(look['house'])
        if look.get('layouts'):
            outline['layouts'] = {kind: look['layouts'][kind] for kind in
                                  ('cover', 'section', 'closing') if look['layouts'].get(kind)}
    outline['approval'] = words
    write_atomic(root / OUTLINE, json.dumps(outline, indent=2, ensure_ascii=False) + '\n')
    gate = (run.setdefault('gates', {})).get(GATE) or {}
    run['gates'][GATE] = {**gate, 'state': 'approved', 'at': at, 'by': by, 'note': note}
    decks.write_run(root, run)
