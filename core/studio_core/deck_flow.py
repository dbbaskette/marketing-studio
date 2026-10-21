"""The one way Training Studio and Presentation Studio make a slide deck: the Tanzu Brand path.

What a caller needs to know
---------------------------
    deck_flow.STEPS                         # the canonical steps, in order
    deck_flow.canonical(product, gate)      # 'draft', 'look' or 'final' for a deck gate
    deck_flow.pauses(level)                 # where a deck stops for the person, by level
    deck_flow.stops(product, level, gate)   # whether that studio's gate is a real stop
    deck_flow.OUTLINE_READING, COMPOSER_READING, REVIEW_READING   # what each worker reads
    deck_flow.for_workers(has_worker)       # what of the brand's own a worker is handed
    deck_flow.route(renderer, has)          # how look samples and previews are rendered
    deck_flow.sampled(manifest, folder)     # the looks a brand drew, as a studio keeps them
    deck_flow.chosen_from(outline)          # the look a brand wrote into an outline

- The studios differ only in where an outline's words come from: Presentation Studio from
  research, material or an existing deck; Training Studio from its handoff, blueprint and
  objectives. Everything else is this flow, in this order (STEPS):
  brand entry (contract export, then the brand's `guidance start|resume --skill slides
  --brand`), outline (the outline contract, the pinned drafting guidance and the brand's
  worker guidance), the `draft` checkpoint, `look samples`, the `look` checkpoint (`look
  choose --outline <approved> --write <new>`, so the brand checks the outline is the one the
  samples were drawn from and writes the chosen direction, house and lead layouts into it),
  sections (the brand's worker guidance and the pinned design and composition guidance and
  gallery), the whole deck, screens (split points, repair clusters, the brand's audit),
  review and repair, render and audit, and the `final` checkpoint.
- The brand defines three checkpoints: draft approval, the look, and final acceptance.
  PAUSES says where each review level stops for them. Step by step stops at each. Balanced
  asks for the draft and the look in one combined stop (`direction`), then the final.
  Automatic draft stops only for the final, and uses the brand's default look, saying why.
  GATES maps each studio's own gate IDs to the canonical checkpoints, and HOSTS names the
  stop of its own that hosts a combined one. A gate whose checkpoint a level folds into a
  combined stop continues on its own once that stop is answered.
- Look samples and deck previews are rendered only through harness-slides' own preview
  route: Google Slides, through its reusable preview pool where the runtime says it has one
  (POOL), or LibreOffice where a studio renders locally. No preview file is made any other
  way. `route` names the route, for the gate to say which rendered the samples.
- Standard library only. Nothing here runs a command or writes a file.
"""
from __future__ import annotations

from pathlib import Path

from studio_core import deck_direction

STEPS = ('brand', 'outline', 'draft', 'look-samples', 'look', 'sections', 'whole', 'screens',
         'review', 'repair', 'render', 'final')
CHECKPOINTS = ('draft', 'look', 'final')
# Where each review level stops for the brand's checkpoints. `direction` is the draft and the
# look, asked together in one stop.
PAUSES = {'step_by_step': ('draft', 'look', 'final'),
          'balanced': ('direction', 'final'),
          'automatic': ('final',)}
FOLDED = {'direction': ('draft', 'look')}
# Each studio's own gates for the brand's checkpoints.
GATES = {'training': {'gate:deck-outline': 'draft', 'gate:deck-look': 'look',
                      'gate:deck': 'final'},
         'presentation': {'gate:outline': 'draft', 'gate:look': 'look', 'gate:build': 'final'}}
# The stop of a studio's own that hosts a combined one, by level. A level without an entry
# stops at the studio's gate for the checkpoint itself: the final is always the deck's own
# gate, so that the person's answer there is the one bound to the slides tool's design record.
HOSTS = {'training': {'balanced': {'direction': 'review:direction'}},
         'presentation': {'balanced': {'direction': 'gate:outline'}}}
POOL = 'preview-pool'          # harness-slides' capability: Google previews reuse a few decks

BRAND_WORKER = 'brand worker guidance'
BRAND_OWN = ('brand design', 'brand slide recipes', 'brand icons')
OUTLINE_READING = ('drafting guidance',)
DESIGN_READING = ('design guidance',)
COMPOSER_READING = ('design guidance', 'composition guidance', 'gallery')
REVIEW_READING = ('review guidance',)

# What a contract between the studios compares of a worker's inputs: the deck's own guidance
# and the brand's, never the studio's own content.
SHARED_INPUTS = frozenset({'outline contract', 'composition contract', *OUTLINE_READING,
                           *DESIGN_READING, *COMPOSER_READING, BRAND_WORKER, *BRAND_OWN})

LOOK_FAILED = ("The brand's looks could not be rendered here ({why}). Nothing was picked for "
               "you: try again, or carry on in the brand's default look.")
DEFAULT_WORDS = "Automatic draft: the brand's default look, {name}, was used."
PROCEED_WORDS = ("The samples could not be rendered, and the person chose to carry on in the "
                 "brand's default look, {name}.")


def canonical(product: str, gate: str) -> str | None:
    """The brand's checkpoint a studio's gate is, or None for a gate that is not a deck's.
    A Training Studio gate may carry its level, as `gate:deck@101`."""
    return GATES.get(product, {}).get(gate.partition('@')[0])


def pauses(level: str) -> tuple[str, ...]:
    """Where a deck stops for the person at this review level, by checkpoint."""
    return PAUSES[level]


def stops(product: str, level: str, gate: str) -> bool | None:
    """Whether a studio's own gate is a real stop at this level: True, False, or None for a
    gate that is not a deck checkpoint. A checkpoint a combined stop hosts continues on its
    own; the stop that hosts it is a stop."""
    base = gate.partition('@')[0]
    hosts = HOSTS.get(product, {}).get(level, {})
    if base in hosts.values() and base in GATES.get(product, {}):
        return True
    checkpoint = canonical(product, gate)
    if checkpoint is None:
        return None
    for stop in pauses(level):
        if checkpoint == stop or checkpoint in FOLDED.get(stop, ()):
            return stop not in hosts
    return False


def for_workers(has_worker: bool) -> tuple[str, ...]:
    """What of the brand's own a deck's design writer and composers are handed: the worker
    guidance its slides entry asks be forwarded unchanged, else its own handoff."""
    return (BRAND_WORKER,) if has_worker else BRAND_OWN


def route(renderer: str, has=lambda name: False) -> dict:
    """How look samples and previews are rendered: through the slides tool's Google preview
    (its preview pool where it has one) or LibreOffice where the studio renders locally, as
    {'preview': what the brand's `look samples --preview` takes, 'says': the gate's words}."""
    if renderer == 'local':
        return {'preview': 'local', 'says': 'Rendered on this computer with LibreOffice.'}
    pooled = bool(has(POOL))
    return {'preview': 'google', 'pool': pooled,
            'says': ("Rendered through Google Slides, in the slides tool's reusable preview "
                     'decks.' if pooled else 'Rendered through Google Slides, the way this '
                     'computer renders every preview.')}


def sampled(manifest, folder: Path) -> list[dict]:
    """The looks a brand drew, from its looks.json, as a studio keeps them: {'id', 'name',
    'useWhen', 'number', 'image', 'direction', 'layouts'}, `image` its picture's path when
    it is a file inside `folder`. Raises ValueError when there are none."""
    inside, looks = Path(folder).resolve(), []
    samples = manifest.get('samples') if isinstance(manifest, dict) else None
    for number, sample in enumerate(samples or (), start=1):
        if not isinstance(sample, dict) or not isinstance(sample.get('id'), str):
            continue
        image = Path(str(sample.get('image'))).resolve() if sample.get('image') else None
        looks.append({'id': sample['id'], 'name': str(sample.get('name') or sample['id']),
                      'useWhen': str(sample.get('useWhen') or ''), 'number': number,
                      'image': str(image) if image and inside in image.parents
                      and image.is_file() else None,
                      'direction': sample.get('direction'),
                      'layouts': sample.get('layouts') if isinstance(sample.get('layouts'),
                                                                     dict) else {}})
    if not looks:
        raise ValueError('The brand offered no look to choose from.')
    return looks


def chosen_from(outline, contract=None) -> dict | None:
    """The look a brand's `look choose --write` put into an outline: its direction, held to
    the brand's colours when the contract is given, its house lines and its lead layouts."""
    if not isinstance(outline, dict) or not isinstance(outline.get('direction'), dict):
        return None
    direction = deck_direction.checked(outline['direction'], contract) if contract \
        else outline['direction']
    if not direction:
        return None
    layouts = outline.get('layouts') if isinstance(outline.get('layouts'), dict) else {}
    return {'direction': direction,
            'house': [line for line in outline.get('house') or () if isinstance(line, str)
                      and line.strip()],
            'layouts': {kind: name for kind, name in layouts.items()
                        if kind in ('cover', 'section', 'closing') and isinstance(name, str)}}
