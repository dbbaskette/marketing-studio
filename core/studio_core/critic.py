"""The slides tool's own review questions, read from a whole-deck preview, in Presentation
Studio and Training Studio alike.

What a caller needs to know
---------------------------
    critic.questions(folder)      # the questions in folder/critic.json, as a tuple
    critic.of_round(round)        # the questions a round was reviewed with
    critic.MISSING                # why a preview's questions cannot be read
    critic.LEGACY                 # Harness Slides 0.16.0's eight

- Every whole-deck preview the slides tool makes writes critic.json beside it, and its
  `questions` are what a reviewer answers of every slide, numbered from 1 as the tool
  numbers them. A studio asks those, never a copy of its own, so that an update of the tool
  cannot leave a review asked one set of questions and checked against another.
- `questions` refuses with ValueError(MISSING) a folder without critic.json, or one whose
  `questions` is not a list of 1 to MOST non-empty strings.
- A round records the questions it was reviewed with. `of_round` reads them, and gives
  LEGACY for a round saved before rounds recorded them: those were asked the 0.16.0 eight.
- Nothing here writes anything.
"""
from __future__ import annotations

import json
from pathlib import Path

PACKET = 'critic.json'
MOST = 12   # questions a preview may ask of a slide
MISSING = ("The slides tool's review questions are not with this preview. Put the deck "
           'together again.')
LEGACY = (
    'After three seconds, is the main point clear, and is it the claim in the title?',
    'Does the eye land first on the element that carries the point?',
    'Is there exactly one emphasis?',
    'Does every element support the title?',
    'Is each label inside or right beside what it names?',
    'Is the space balanced, with nothing stranded or crowded?',
    'Is the slide consistent with its neighbours in style, and different from them in layout '
    'unless they are meant to be compared?',
    'Does every image and icon explain something?',
)


def _valid(found) -> bool:
    return isinstance(found, (list, tuple)) and 1 <= len(found) <= MOST \
        and all(isinstance(question, str) and question.strip() for question in found)


def questions(folder) -> tuple[str, ...]:
    """The questions the slides tool asks of every slide of the preview in `folder`."""
    try:
        packet = json.loads((Path(folder) / PACKET).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError(MISSING) from None
    found = packet.get('questions') if isinstance(packet, dict) else None
    if not _valid(found):
        raise ValueError(MISSING)
    return tuple(found)


def of_round(round_: dict | None) -> tuple[str, ...]:
    """The questions a round was reviewed with: its own, or LEGACY for one saved before
    rounds recorded them."""
    found = (round_ or {}).get('questions')
    return tuple(found) if _valid(found) else LEGACY
