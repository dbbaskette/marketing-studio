"""A deck's visual direction as its brand, or the person's choice of look, gives it.

What a caller needs to know
---------------------------
    deck_direction.of_file(contract_path)          # the brand's own direction, or None
    deck_direction.direction(contract, beside)     # the same, from parsed JSON
    deck_direction.checked(given, contract)        # a look's direction, held to the brand
    deck_direction.told(direction)                 # what a composer is told of its colours

- A studio does not choose how a deck looks. The brand's slide guidance does, through its
  look step: the person picks one of a few rendered looks, and that look's direction and
  house style are what the deck is built with. Until a look is chosen, a brand may give a
  default direction of its own: in `deck-direction.json` beside its exported contract, or
  in the contract under `design.deckDirection`, `design.direction` or
  `design.slides.direction`. Reading it is tolerant: a meaning whose role the brand does
  not have, or whose colour is the focal's or the neutral's, is left out, and anything
  unreadable is passed over.
- A direction is harness-slides' own: `focal`, the one colour that means "look here";
  `neutral`, the panel colour everything starts as; `meanings`, what each other colour
  stands for in the deck; and `motif`, one recurring device. Every value is a colour role
  of the brand.
- FALLBACK is harness-slides' own two-colour example. It is what a deck has only when
  neither the brand nor a chosen look gives a direction, as every deck had before.
- Nothing here runs anything or writes anything. Standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = 'deck-direction.json'
FALLBACK = {'focal': 'headingPrimary', 'neutral': 'canvasSecondary'}
MOTIF = 200     # characters a motif may hold


def _colours(contract) -> dict:
    design = contract.get('design') if isinstance(contract, dict) else None
    colours = design.get('colors') if isinstance(design, dict) else None
    return colours if isinstance(colours, dict) else {}


def checked(given, contract) -> dict | None:
    """A direction as harness-slides takes it, held to the brand's colour roles, or None
    when it does not name a focal and a neutral the brand has."""
    colours = _colours(contract)
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


def direction(contract, beside=None) -> dict | None:
    """The direction the brand gives its decks, or None when it gives none."""
    design = contract.get('design') if isinstance(contract, dict) else None
    design = design if isinstance(design, dict) else {}
    slides = design.get('slides') if isinstance(design.get('slides'), dict) else {}
    for given in (beside, design.get('deckDirection'), design.get('direction'),
                  slides.get('direction')):
        found = checked(given, contract)
        if found:
            return found
    return None


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def contract_of(contract_path) -> dict:
    """The exported contract at `contract_path`, or an empty one when it cannot be read."""
    found = _json(Path(contract_path))
    return found if isinstance(found, dict) else {}


def of_file(contract_path) -> dict | None:
    """The direction the brand exported to `contract_path` gives, reading
    deck-direction.json beside it when the brand wrote one; None when it gives none."""
    path = Path(contract_path)
    return direction(contract_of(path), _json(path.parent / FILE))


def told(given: dict) -> str:
    """What a composer is told of a direction's colours, in a few sentences."""
    meanings = given.get('meanings') or {}
    lines = [f"`{given.get('focal')}` marks the one node that carries a slide's point. "
             f"Panels start as `{given.get('neutral')}`."]
    if meanings:
        lines.append('Each of these colours means one thing on every slide; use it for that '
                     'thing and nothing else, with its name in words too:')
        lines += [f'- `{role}`: {said}' for role, said in meanings.items()]
    if given.get('motif'):
        lines.append(f"The deck's recurring device: {given['motif']}")
    return '\n'.join(lines)
