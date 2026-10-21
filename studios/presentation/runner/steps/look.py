"""The brand a deck is made in, shown before any slide is designed: the deck's cover drawn in
that brand, so the person can see it is the brand they meant, and choose another if not.

What a caller needs to know
---------------------------
    shown = look.draw_sample(root, run, slides, renderer)   # work/look/sample.png; work/ only
    look.show_sample(root, run)                             # look.md, and the gate waiting
    look.preview_sample(root, run, slides, renderer)        # the two together
    look.rebrand(root, run, brand, variant, brands)         # another brand: the form, brand/
    look.approve(root, run, note=None)                      # the gate approved

- No look is chosen. The sample is the outline's cover, with its approved title and
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
- `approve` puts the person's words of approval into outline.json (`approval`), takes out a
  `direction` an earlier version of this step put there, so that the build uses the brand's
  own colours, and approves the gate.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import home
from studio_core import deck_direction
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
THROUGH_DRIVE = ('The looks were rendered through Google Drive, the way this computer '
                 'renders every preview: there is no local renderer here.')
NO_LOOK = 'Choose one of the looks to draw the deck in.'
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


def draw_looks(root, run: dict, brand_skill, renderer) -> dict:
    """Have the brand render a slide of the outline in each of its deck directions, in
    work/look/, and keep a picture of each and the sheet of them all for the gate. Previews
    are taken locally where this computer renders locally, and otherwise through Google
    Drive, as every preview here is; one at a time either way. Returns what the gate shows."""
    root = Path(root)
    form = run.get('form') or {}
    how = build.how(root, run, renderer)
    preview = 'local' if how.get('renderer') == 'local' else 'google'
    shutil.rmtree(root / FOLDER, ignore_errors=True)
    folder = root / FOLDER
    try:
        folder.mkdir(parents=True)
        with worker_tools.one_at_a_time(Path(how['lock'])):
            made = brand_skill.look_samples(root / OUTLINE, root / SAMPLES, form.get('brand'),
                                            form.get('variant'), preview=preview,
                                            delivery=build.DELIVERY)
        manifest = home.read_json(root / SAMPLES / 'looks.json', {})
        inside = (root / SAMPLES).resolve()
        looks = []
        for number, sample in enumerate(manifest.get('samples') or (), start=1):
            image = Path(str(sample.get('image'))).resolve()
            if inside not in image.parents:
                raise WorkspaceError('The brand drew no picture of a look.')
            (folder / f'{number}.png').write_bytes(worker_tools.picture(image))
            looks.append({'id': str(sample['id']), 'name': str(sample.get('name') or ''),
                          'useWhen': str(sample.get('useWhen') or ''), 'picture': number,
                          'direction': sample.get('direction'),
                          'layouts': sample.get('layouts') or {}})
        if not looks:
            raise WorkspaceError('The brand offered no look to choose from.')
        sheet = Path(str(made.get('sheet') or manifest.get('sheet'))).resolve()
        if inside in sheet.parents and sheet.is_file():
            (root / SHEET).write_bytes(worker_tools.picture(sheet))
        shown = {'looks': looks, 'default': manifest.get('default') or made.get('default'),
                 'slide': manifest.get('slide'), 'house': manifest.get('house') or [],
                 'route': preview, 'outline': sha256_of(root / OUTLINE)}
        home.write_json(root / SHOWN, shown)
    except (WorkspaceError, OSError, KeyError, TypeError, ValueError) as refusal:
        shutil.rmtree(folder, ignore_errors=True)
        raise WorkspaceError(f"The brand's looks could not be drawn. {refusal}") from None
    return shown


def shown_looks(root) -> dict | None:
    """What the gate shows of the brand's looks, or None when there are none here."""
    found = home.read_json(Path(root) / SHOWN, None)
    return found if isinstance(found, dict) and found.get('looks') else None


def chosen(root) -> dict | None:
    """The look the person chose, as the brand recorded it, or None."""
    found = home.read_json(Path(root) / CHOSEN, None)
    return found if isinstance(found, dict) and found.get('choice') else None


def choose(root, brand_skill, choice, words: str) -> dict:
    """Record the person's pick of a look, in their words, with the brand, and keep it."""
    root = Path(root)
    shown = shown_looks(root)
    if shown is None:
        raise WorkspaceError('There are no looks to choose from here.')
    if not isinstance(choice, str) or choice not in [look['id'] for look in shown['looks']]:
        raise WorkspaceError(NO_LOOK)
    if chosen(root) is not None:
        return chosen(root)
    picked = next(look for look in shown['looks'] if look['id'] == choice)
    made = brand_skill.look_choose(root / SAMPLES, choice, words)
    record = {'choice': choice, 'name': picked['name'], 'words': words.strip(),
              'direction': made.get('direction') or picked['direction'],
              'layouts': made.get('layouts') or picked['layouts'],
              'house': list(shown.get('house') or ()), 'at': home.now()}
    home.write_json(root / CHOSEN, record)
    return record


def choose_default(root, brand_skill) -> dict | None:
    """Under Automatic draft: the brand's default look, recorded with why. None where the
    brand offered no looks."""
    shown = shown_looks(root)
    if shown is None:
        return None
    if chosen(root) is not None:
        return chosen(root)
    default = next((look for look in shown['looks'] if look['id'] == shown.get('default')),
                   shown['looks'][0])
    return choose(root, brand_skill, default['id'],
                  f"Automatic draft: the brand's default look, {default['name']}, was used.")


def _markdown(form: dict, shown: dict | None = None) -> str:
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
    picked = chosen(root) or (run.get('look_choice') if isinstance(run.get('look_choice'), dict)
                              and run['look_choice'].get('direction') else None)
    if picked:
        words.append(f"Look chosen: {picked['name']} ({picked['choice']}). In their words: "
                     f"\"{picked['words']}\"")
    words += [line for line in (said, note) if line]
    # The look the person chose, or the brand's default where it offered none to choose.
    look = picked or deck_direction.default_look(root / build.CONTRACT)
    for key in ('direction', 'house', 'layouts'):
        outline.pop(key, None)
    if look:
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
