"""A deck's visual direction and house rules, read from its brand's exported contract.

What a caller needs to know
---------------------------
    look = deck_direction.of_file(contract_path)   # {'direction', 'square'}
    deck_direction.direction(contract, beside)     # the direction alone, from parsed JSON
    deck_direction.house(square)                   # the house rules a composer is told

- A direction is harness-slides' own: `focal`, the one colour that means "look here";
  `neutral`, the panel colour everything starts as; `meanings`, what each other colour
  stands for in the deck; and `motif`, one recurring device. Every value is a colour role
  of the brand.
- A brand may say which direction its decks take: in `deck-direction.json` beside its
  contract, or in the contract under `design.deckDirection`, `design.direction` or
  `design.slides.direction`. The first that names a focal and a neutral the brand has is
  used. Reading is tolerant: a meaning whose role the brand does not have, or whose colour
  is the focal's or the neutral's, is left out, and anything unreadable is passed over.
- A brand that says nothing gets BUILT_IN: the heading colour as focal, the secondary
  canvas as neutral, and a meaning for each of the standard accents the brand has, so that
  products, alternatives and results can be told apart by colour as well as by word. A
  brand without those roles gets LEGACY, the two colours decks always had.
- `square` is True when the brand's geometry gives rectangles no radius, False when it
  gives them one, and None when it does not say. Only True puts square corners into the
  house rules.
- Nothing here runs anything or writes anything. Standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = 'deck-direction.json'
LEGACY = {'focal': 'headingPrimary', 'neutral': 'canvasSecondary'}
# What each standard accent stands for when the brand does not say: the deck's own product,
# what it is compared with, and a result or a healthy state.
MEANINGS = (
    ('accentAqua', 'The product or platform this deck teaches'),
    ('accentPurple', 'Another product, vendor or approach it is compared with'),
    ('accentGreen', 'A recommended step, a healthy state or a result'),
)
MOTIF = 200     # characters a motif may hold

PEERS = ('Equals share one size and weight: never set one of several peers larger or '
         'bolder. Peers may share a light fill from the direction, and a peer that is one '
         "of the direction's meanings, such as a product or an actor, takes that colour on "
         'every slide.')
FOCAL = ('The focal point is what the title singles out, and never one of several peers. A '
         'slide that lists equals has a focal that is not one of them.')
ANNOUNCE = 'Draw nothing the title does not announce.'
CASE = 'Titles and labels are in sentence case. Names and acronyms stay as they are written.'
SQUARE = 'Boxes have square corners, as the brand draws them.'
CAVEAT = ("A caveat and a source line go in the slide's own caveat and source fields, never "
          'in the drawing.')
BADGES = ('Leave out badges, labels on arrows and small print wherever the slide reads '
          'without them.')
ICONS = ("Give each recognisable product, platform, tool or actor its icon from the brand's "
         'functional icon library: the same icon for the same thing across the deck, never '
         'twice on one slide. Leave abstract ideas without one.')


def _colours(contract) -> dict:
    design = contract.get('design') if isinstance(contract, dict) else None
    colours = design.get('colors') if isinstance(design, dict) else None
    return colours if isinstance(colours, dict) else {}


def _checked(given, colours: dict) -> dict | None:
    """A direction the brand gives, as harness-slides takes it, or None when it does not
    name a focal and a neutral the brand has."""
    if not isinstance(given, dict):
        return None
    focal, neutral = given.get('focal'), given.get('neutral')
    if focal not in colours or neutral not in colours or focal == neutral:
        return None
    made = {'focal': focal, 'neutral': neutral}
    meanings = given.get('meanings')
    if isinstance(meanings, dict):
        taken = {role: said.strip() for role, said in meanings.items()
                 if role in colours and isinstance(said, str) and said.strip()
                 and role not in (focal, neutral)
                 and str(colours[role]).lower() not in (str(colours[focal]).lower(),
                                                        str(colours[neutral]).lower())}
        if taken:
            made['meanings'] = taken
    motif = given.get('motif')
    if isinstance(motif, str) and motif.strip() and len(motif.strip()) <= MOTIF:
        made['motif'] = motif.strip()
    return made


def built_in(contract) -> dict:
    """The direction a deck takes when its brand gives none."""
    colours = _colours(contract)
    if not all(role in colours for role in LEGACY.values()):
        return dict(LEGACY)
    return _checked({**LEGACY, 'meanings': dict(MEANINGS)}, colours) or dict(LEGACY)


def direction(contract, beside=None) -> dict:
    """A deck's direction: the one its brand gives, else the built-in one."""
    colours = _colours(contract)
    design = contract.get('design') if isinstance(contract, dict) else None
    design = design if isinstance(design, dict) else {}
    slides = design.get('slides') if isinstance(design.get('slides'), dict) else {}
    for given in (beside, design.get('deckDirection'), design.get('direction'),
                  slides.get('direction')):
        found = _checked(given, colours)
        if found:
            return found
    return built_in(contract)


def square(contract) -> bool | None:
    """Whether the brand draws rectangles with square corners, or None when it does not say."""
    design = contract.get('design') if isinstance(contract, dict) else None
    geometry = design.get('geometry') if isinstance(design, dict) else None
    radius = geometry.get('rectangularRadiusPx') if isinstance(geometry, dict) else None
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        return None
    return radius == 0


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def of_file(contract_path) -> dict:
    """The direction and corners of the brand exported to `contract_path`, reading
    deck-direction.json beside it when the brand wrote one. A contract that cannot be read
    gives LEGACY and no word on corners."""
    path = Path(contract_path)
    contract = _json(path)
    contract = contract if isinstance(contract, dict) else {}
    return {'direction': direction(contract, _json(path.parent / FILE)),
            'square': square(contract)}


def house(square_corners: bool | None = None) -> tuple[str, ...]:
    """The house rules a composer is told, with square corners only where the brand says."""
    return (PEERS, FOCAL, ANNOUNCE, CASE, *((SQUARE,) if square_corners else ()), CAVEAT,
            BADGES, ICONS)


def told(direction_given: dict) -> str:
    """What a composer is told of a direction's colours, in a few sentences."""
    meanings = direction_given.get('meanings') or {}
    lines = [f"`{direction_given.get('focal')}` marks the one node that carries a slide's "
             f"point. Panels start as `{direction_given.get('neutral')}`."]
    if meanings:
        lines.append('Each of these colours means one thing on every slide; use it for that '
                     'thing and nothing else, with its name in words too:')
        lines += [f'- `{role}`: {said}' for role, said in meanings.items()]
    if direction_given.get('motif'):
        lines.append(f"The deck's recurring device: {direction_given['motif']}")
    return '\n'.join(lines)
