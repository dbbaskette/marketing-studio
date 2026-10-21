"""The slide guidance a brand skill hands a deck, and the looks a deck may be drawn in.

What a caller needs to know
---------------------------
    kept = brand_guidance.recorded(answer)        # what a studio keeps of `guidance start`
    texts = brand_guidance.snapshot(answer)       # {name: text} from the returned snapshot
    texts.update(brand_guidance.brand_texts(contract_path))   # the brand's own handoff
    brand_guidance.worker(answer)                 # what every composer is handed unchanged

- A brand skill that has a `guidance start|resume --skill slides --project DIR` command
  is the entry to slide building: it fetches the slides tool's public guidance, pins it to
  a task, and returns {task, revision, guidance, runtime, ...}: `guidance` is the
  snapshot's SKILL.md, and `runtime` the installed slides tool to run every command with.
  A studio records the task with the deck and resumes it later. `recorded` keeps only the
  fields a studio needs, as text.
- `snapshot` reads the guidance a worker is handed from that snapshot, by the names the
  studios already use for them, and one drawn example for each relation. Only regular
  files inside the snapshot are read, each up to READ_MOST characters.
- `brand_texts` reads the brand's own handoff beside its exported contract: DESIGN.md, and
  the slide-design recipes and icon catalog the contract points to, when it does. A path
  the contract names is read only when it is an absolute path to a Markdown file.
- With `--brand`, a brand's answer also carries a `brand` block: its entry, recipes and
  review references, its commands, the checkpoints it defines (draft approval, the look,
  final acceptance), its deck direction, and `worker`, markdown a studio forwards unchanged
  to every composer and to the writer of a deck's design.
- Standard library only. Nothing here runs a command or writes a file.
"""
from __future__ import annotations

import json
from pathlib import Path

from studio_core import deck_direction

READ_MOST = 60_000
GUIDES = {'slides guidance': 'SKILL.md', 'drafting guidance': 'references/draft.md',
          'design guidance': 'references/design.md',
          'composition guidance': 'references/compositions.md',
          'gallery': 'references/gallery.md', 'review guidance': 'references/review.md',
          'parallel build': 'references/parallel-build.md'}
RELATIONS = ('order', 'dependency', 'hierarchy', 'membership', 'contrast', 'parallel',
             'overlap', 'quantity', 'none')
KEPT = ('task', 'revision', 'runtime', 'runtimeVersion', 'freshness', 'notice')
RECIPES = ('recipes', 'slideRecipes', 'slideDesignRecipes', 'designRecipes')


def example(relation: str) -> str:
    """What the drawn example of one relation is called among a worker's inputs."""
    return f'example: {relation}'


def recorded(answer) -> dict:
    """What a studio keeps of a brand's `guidance start` or `resume` answer."""
    answer = answer if isinstance(answer, dict) else {}
    return {key: str(answer[key]) for key in KEPT if isinstance(answer.get(key), (str, int))}


def _read(base: Path, relative: str) -> str | None:
    path = base / relative
    try:
        if path.is_symlink() or not path.is_file() or base.resolve() not in \
                path.resolve().parents:
            return None
        with open(path, encoding='utf-8', errors='replace') as stream:
            return stream.read(READ_MOST)
    except OSError:
        return None


def snapshot(answer) -> dict:
    """The guidance a worker is handed, from the snapshot a brand's guidance entry returned,
    as {name: text}. Empty when there is none."""
    entry = (answer or {}).get('guidance') if isinstance(answer, dict) else None
    if not isinstance(entry, str) or not entry:
        return {}
    base = Path(entry).parent
    wanted = {**GUIDES, **{example(relation): f'references/gallery/{relation}.json'
                           for relation in RELATIONS}}
    found = {name: _read(base, relative) for name, relative in wanted.items()}
    return {name: text for name, text in found.items() if text and text.strip()}


def _markdown(value) -> str | None:
    if not isinstance(value, str) or not value.endswith('.md') or not Path(value).is_absolute():
        return None
    path = Path(value)
    try:
        if not path.is_file():
            return None
        with open(path, encoding='utf-8', errors='replace') as stream:
            return stream.read(READ_MOST)
    except OSError:
        return None


def brand_texts(contract_path) -> dict:
    """The brand's own slide handoff beside its exported contract, as {name: text}:
    'brand design' (DESIGN.md), 'brand slide recipes' and 'brand icons', each only when
    the brand gives it."""
    path = Path(contract_path)
    texts = {}
    design = _read(path.parent, 'DESIGN.md')
    if design and design.strip():
        texts['brand design'] = design
    references = ((deck_direction.contract_of(path).get('design') or {})
                  .get('references') or {})
    references = references if isinstance(references, dict) else {}
    for key in RECIPES:
        recipes = _markdown(references.get(key))
        if recipes and recipes.strip():
            texts['brand slide recipes'] = recipes
            break
    icons = references.get('icons')
    if isinstance(icons, str) and icons.strip():
        texts['brand icons'] = _markdown(icons) or icons.strip()
    return texts


def worker(answer) -> str | None:
    """The markdown a brand's guidance entry asks a studio to forward, unchanged, to every
    composer and to the writer of a deck's design, or None when it gives none."""
    block = (answer or {}).get('brand') if isinstance(answer, dict) else None
    text = block.get('worker') if isinstance(block, dict) else None
    return text if isinstance(text, str) and text.strip() else None


def checkpoints(answer) -> list[str]:
    """The checkpoints the brand defines for a deck, a sentence each."""
    block = (answer or {}).get('brand') if isinstance(answer, dict) else None
    listed = block.get('checkpoints') if isinstance(block, dict) else None
    return [str(line) for line in listed or () if isinstance(line, str) and line.strip()]
