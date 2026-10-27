"""A slide's words on the desk: the new words put into the outline and into the section as it
is drawn, checked by the slides tool, with no composer.

What a caller needs to know
---------------------------
    outline = words.retext(outline, slide_id, field, text)       # a new outline, not written
    section = words.patch_section(drawn, slide_id, field, old, new)  # a new drawn section
    lines = words.fits(root, run, section_id, section, slides, outline)  # the tool's lines
    words.land(root, run, section_id, section)                   # kept as a new drawn file
    words.retold(root, slide_id, outline, knows)                 # the start's outline told

- A field is one of FIELDS, or a point's label or text: ('points', index, 'label'|'text').
  Title, subtitle, detail, caveat, source and notes are the slide's own fields in a drawn
  section. A point's words are text in its canvas: the old words must be found in exactly
  one piece of the slide's text, where they are replaced; otherwise nothing is patched
  (NOT_FOUND), and the slide is redrawn instead.
- `fits` is the check a composer's section passes (`worker_tools.check_section`): what was
  fixed is as it was, every approved word is there, and the slides tool compiles it. It
  refuses rather than shrinks: words that no longer fit come back as the tool's own lines.
- `land` writes only this computer's work/build/drawn/; `retold` only the start's given/
  outline (work/), so the next start of the deck keeps every section whose words are the
  same. Neither starts a job; the engine puts the deck together afterwards.
"""
from __future__ import annotations

import copy
import json
import secrets
import tempfile
from pathlib import Path

# isort: off
import runner  # noqa: F401  puts the core on the import path
import home
from workspace import WorkspaceError, write_atomic

from runner.steps import build
# isort: on


FIELDS = ('title', 'subtitle', 'detail', 'caveat', 'source', 'notes')
KEYS = ('label', 'text')
NO_FIT = 'These words do not fit the slide as it is drawn.'
NOT_FOUND = 'The old words were not found once on the drawn slide.'
NO_FIELD = 'Choose the title, subtitle, detail, a point, the caveat, the source or the notes.'
TOO_LONG = 2000   # characters in one field's words
NOTES_LONG = 4000  # characters in a slide's speaker notes
SHARED_OPS = Path('desk') / 'patch-ops.json'   # the desk's changes to your own deck, shared
NO_OBJECT = 'Choose the words of one part of the slide.'
MANY_RUNS = 'These words are in several parts on the slide: change one part at a time.'


def field_of(field):
    """A field as the desk names it: one of FIELDS, or ('points', index, 'label'|'text')
    (a list from the page is taken as that tuple). Refused otherwise."""
    if isinstance(field, str) and field in FIELDS:
        return field
    if isinstance(field, (list, tuple)) and len(field) == 3 and field[0] == 'points' \
            and type(field[1]) is int and field[1] >= 0 and field[2] in KEYS:
        return ('points', field[1], field[2])
    raise WorkspaceError(NO_FIELD)


def field_words(field) -> str:
    """A field as a sentence names it: 'title', 'first point's text'."""
    field = field_of(field)
    if isinstance(field, tuple):
        return f"point {field[1] + 1}'s {field[2]}"
    return {'notes': 'speaker notes'}.get(field, field)


def check_words(text: str, spec: dict):
    """A words job's result: the replacement for one passage, one string of at most
    TOO_LONG characters, on one line for a title or a point. Returns problems, the checks
    that ran, warnings and the text to keep."""
    from runner import worker_tools
    problems = []
    kept = (text or '').strip()
    if not kept:
        problems.append('Hand back the words that replace the passage.')
    if len(kept) > TOO_LONG:
        problems.append(f'Keep the words to {TOO_LONG:,} characters.')
    if spec.get('single') and '\n' in kept:
        problems.append('These words are on one line: a title or a point has no line breaks.')
    return problems, [worker_tools.result('words.text', problems)], [], kept


def text_of(slide: dict, field) -> str:
    """A slide's words in one field, '' where it has none."""
    field = field_of(field)
    if isinstance(field, tuple):
        points = slide.get('points') or []
        if field[1] >= len(points):
            raise WorkspaceError(NO_FIELD)
        return str(points[field[1]].get(field[2]) or '')
    value = slide.get(field)
    return str((value.get('text') if isinstance(value, dict) else value) or '')


def retext(outline: dict, slide_id: str, field, text: str) -> dict:
    """A new outline with one slide's words in one field changed. The given one is kept."""
    field = field_of(field)
    most = NOTES_LONG if field == 'notes' else TOO_LONG
    if not isinstance(text, str) or len(text) > most:
        raise WorkspaceError(f'Keep the words to {most:,} characters.')
    if (field == 'title' or isinstance(field, tuple)) and '\n' in text.strip():
        raise WorkspaceError('Keep a title and a point to one line.')
    made = copy.deepcopy(outline)
    slide = next((one for one in build.slides_of(made) if one.get('id') == slide_id), None)
    if slide is None:
        raise WorkspaceError('The deck has no such slide.')
    text = text.strip()
    if isinstance(field, tuple):
        points = slide.get('points') or []
        if field[1] >= len(points):
            raise WorkspaceError(NO_FIELD)
        points[field[1]][field[2]] = text
    elif text:
        slide[field] = text
    else:
        slide.pop(field, None)
    return made


def _texts(node, found: list) -> None:
    """Every dict in a drawing that shows a piece of text, in order."""
    if isinstance(node, list):
        for item in node:
            _texts(item, found)
    elif isinstance(node, dict):
        for key in ('text', 'value', 'label'):
            if isinstance(node.get(key), str) and node.get('type') != 'badge':
                found.append((node, key))
        for value in node.values():
            if isinstance(value, (dict, list)):
                _texts(value, found)


def patch_section(section: dict, slide_id: str, field, old: str, new: str) -> dict:
    """A new drawn section with one slide's words changed: a field of the slide set as it
    is, or a point's old words replaced where they are drawn, once. NOT_FOUND when they
    are drawn more than once, or not at all."""
    field = field_of(field)
    made = copy.deepcopy(section)
    slide = next((one for one in made.get('slides') or () if isinstance(one, dict)
                  and one.get('id') == slide_id), None)
    if slide is None:
        raise WorkspaceError(NOT_FOUND)
    new = (new or '').strip()
    if not isinstance(field, tuple):
        if field == 'caveat' and isinstance(slide.get('caveat'), dict):
            slide['caveat'] = {**slide['caveat'], 'text': new}
        elif new:
            slide[field] = new
        else:
            slide.pop(field, None)
        return made
    old = (old or '').strip()
    if not old or not new:
        raise WorkspaceError(NOT_FOUND)
    found = []
    _texts([slide.get('canvas'), slide.get('connect')], found)
    held = [(node, key) for node, key in found if old in node[key]]
    if len(held) != 1 or held[0][0][held[0][1]].count(old) != 1:
        raise WorkspaceError(NOT_FOUND)
    node, key = held[0]
    node[key] = node[key].replace(old, new)
    return made


def fits(root, run: dict, section: str, patched: dict, slides, outline: dict) -> list[str]:
    """The slides tool's lines where the patched section no longer fits, and the runner's
    where an approved word is gone: empty when it fits. Checked against `outline`, the start's
    approved outline with the new words, as a composer's section is."""
    from runner import worker_tools
    spec = build.section_spec(root, run, section, outline=outline)
    with tempfile.TemporaryDirectory(prefix='presentation-words-') as scratch:
        problems, _, _, _ = worker_tools.check_section(
            json.dumps(patched, ensure_ascii=False), spec, slides, Path(scratch))
    return list(problems)


def given(root) -> dict:
    """The start's approved outline, as the build began from it."""
    state = build.read_state(root)
    began = state.get('start') or {}
    if not began:
        raise WorkspaceError('There is no drawing of this deck on this computer.')
    found = home.read_json(Path(root) / began['folder'] / 'given' / 'outline.json', None)
    if not isinstance(found, dict):
        raise WorkspaceError('There is no drawing of this deck on this computer.')
    return found


def with_words(whole: dict, outline: dict, slide_id: str) -> dict:
    """The start's approved outline with one slide's words as `outline` has them now."""
    made = copy.deepcopy(whole)
    now = next((one for one in build.slides_of(outline) if one.get('id') == slide_id), None)
    for at, slide in enumerate(made.get('slides') or ()):
        if isinstance(slide, dict) and slide.get('id') == slide_id and now is not None:
            kept = {key: value for key, value in slide.items()
                    if key not in (*FIELDS, 'points')}
            made['slides'][at] = {**kept, **{key: now[key] for key in (*FIELDS, 'points')
                                             if key in now}}
    return made


def _register() -> None:
    from runner import worker_tools
    worker_tools.register('words', check_words, extension='.txt')


_register()


def lead_file(root, state: dict, slide_id: str) -> Path | None:
    """The start's file for a lead slide (cover, section or closing), which no composer
    draws: the deck is put together from it as it is."""
    began = state.get('start') or {}
    folder = Path(root) / began['folder']
    for part in (home.read_json(folder / 'parts.json', {}) or {}).get('parts') or ():
        if build.SECTION.match(Path(part).stem):
            continue
        made = home.read_json(folder / part, {})
        if any(isinstance(one, dict) and one.get('id') == slide_id
               for one in made.get('slides') or ()):
            return folder / part
    return None


def lead_fits(patched: dict, brand, slides) -> list[str]:
    """The slides tool's lines where a lead slide's new words do not compile."""
    from runner import worker_tools
    with tempfile.TemporaryDirectory(prefix='presentation-lead-') as scratch:
        file = Path(scratch) / 'lead.json'
        file.write_text(json.dumps(patched, ensure_ascii=False), encoding='utf-8')
        try:
            slides.compile(file, Path(brand))
        except WorkspaceError as refusal:
            return list(worker_tools.said_no(refusal))
    return []


def land_lead(root, file: Path, patched: dict) -> None:
    """Keep a lead slide's new words in the start's file, and have the deck put together
    again from it."""
    write_atomic(Path(file), json.dumps(patched, ensure_ascii=False, indent=2) + '\n')
    state = build.read_state(root)
    state['rewhole'] = True
    build.write_state(root, state)


def land(root, run: dict, section: str, patched: dict) -> Path:
    """Keep the patched section as a new drawn file of this computer's, so the deck is put
    together again from it (`Engine._needs_whole`). Returns the file."""
    root = Path(root)
    state = build.read_state(root)
    entry = (state.get('sections') or {}).get(section)
    if entry is None:
        raise WorkspaceError(f'The deck has no drawing of {section} here.')
    file = build.DRAWN / f'{section}-w{secrets.token_hex(3)}.json'
    write_atomic(root / file, json.dumps(patched, ensure_ascii=False, indent=2) + '\n')
    state['sections'][section] = {**entry, 'file': file.as_posix(),
                                  'round': len(state.get('rounds') or ()), 'words': True,
                                  'at': home.now()}
    build.write_state(root, state)
    return root / file


def retold(root, whole: dict, knows=frozenset()) -> None:
    """Write the start's approved outline again with the new words: given/outline.json, and
    the slides tool's copy of it, so a later start keeps the sections they did not change."""
    root = Path(root)
    began = build.read_state(root).get('start') or {}
    folder = root / began['folder']
    home.write_json(folder / 'given' / 'outline.json', whole)
    if (folder / build.TOOL_OUTLINE).is_file():
        home.write_json(folder / build.TOOL_OUTLINE, build.for_tool(whole, knows))


# --- Selected changes: the words of your own deck, changed only through its plan ------------

def plan_of(root) -> list[dict]:
    """The operations of the plan the copy of the deck given is made from: work/patch.json,
    else the desk's shared copy of the operations made on the desk."""
    from runner.steps import existing
    root = Path(root)
    found = home.read_json(root / existing.PATCH, None)
    if not isinstance(found, dict):
        found = home.read_json(root / SHARED_OPS, None)
    listed = found.get('operations') if isinstance(found, dict) else None
    return [op for op in listed or () if isinstance(op, dict)]


def objects_now(slide: dict, plan: list[dict]) -> list[dict]:
    """The objects of one slide of the inventory that hold words, each with its runs as the
    plan makes them: {'id', 'type', 'runs', 'changed'}."""
    made = []
    for item in slide.get('objects') or ():
        runs = item.get('runs') if isinstance(item, dict) else None
        if not isinstance(runs, list) or not runs:
            continue
        was = [str(one) for one in runs]
        now = _applied(was, _op_on(plan, slide.get('number'), item.get('id')))
        made.append({'id': str(item.get('id')), 'type': item.get('type'), 'runs': now,
                     'changed': now != was})
    return made


def _op_on(plan: list[dict], number, object_id) -> dict | None:
    return next((op for op in plan if op.get('slide') == number
                 and str(op.get('object')) == str(object_id)), None)


def object_field(field) -> tuple[str, int | None]:
    """A field of a Selected changes deck's card: ['object', object_id, run_index], where
    run_index is None for an object whose words are one run. Returns (object_id, run_index);
    refused otherwise."""
    if isinstance(field, (list, tuple)) and len(field) == 3 and field[0] == 'object' \
            and isinstance(field[1], str) and field[1] \
            and (field[2] is None or (type(field[2]) is int and field[2] >= 0)):
        return field[1], field[2]
    raise WorkspaceError(NO_OBJECT)


def _object_of(inventory: dict, number, object_id) -> dict:
    slide = next((one for one in inventory.get('slides') or ()
                  if isinstance(one, dict) and one.get('number') == number), None)
    if slide is None:
        raise WorkspaceError(f'The deck has no slide {number}.')
    found = next((item for item in slide.get('objects') or () if isinstance(item, dict)
                  and str(item.get('id')) == str(object_id)), None)
    if found is None or not isinstance(found.get('runs'), list) or not found['runs']:
        raise WorkspaceError(f'Slide {number} has no such words.')
    return found


def run_text(inventory: dict, plan: list[dict], number, object_id, run_index) -> str:
    """The words of one run of one object, or of a one-run object, as the plan makes them."""
    found = _object_of(inventory, number, object_id)
    runs = _applied([str(one) for one in found['runs']], _op_on(plan, number, object_id))
    if run_index is None:
        if len(runs) != 1:
            raise WorkspaceError(MANY_RUNS)
        return runs[0]
    if run_index >= len(runs):
        raise WorkspaceError(f'Slide {number} has no such words.')
    return runs[run_index]


def plan_op(inventory: dict, number, object_id, run_index, text: str) -> dict:
    """One operation of the plan for `pptx patch`: one run of one top-level object of slide
    `number` given new words, {'slide', 'object', 'expectedHash', 'runs': [{'index', 'text'}]},
    or for an object whose words are one run (`run_index` None), {..., 'text'}. The hash is the
    object's in the inventory of the deck given, which the plan is always made to. The spaces
    the run began and ended with are kept, so runs that read as one stay apart."""
    found = _object_of(inventory, number, object_id)
    if not isinstance(text, str) or len(text) > TOO_LONG:
        raise WorkspaceError(f'Keep the words to {TOO_LONG:,} characters.')
    runs = [str(one) for one in found['runs']]
    if run_index is None and len(runs) != 1:
        raise WorkspaceError(MANY_RUNS)
    if run_index is not None and run_index >= len(runs):
        raise WorkspaceError(f'Slide {number} has no such words.')
    was = runs[run_index or 0]
    lead, tail = was[:len(was) - len(was.lstrip())], was[len(was.rstrip()):]
    said = text.strip()
    new = lead + said + tail if said else ''
    op = {'slide': number, 'object': str(found['id']), 'expectedHash': found.get('contentHash')}
    if run_index is None:
        return {**op, 'text': new}
    return {**op, 'runs': [{'index': run_index, 'text': new}]}


def _merged(plan: dict, op: dict) -> dict:
    """The plan with `op` in it: an earlier operation on the same object is replaced, except
    that its runs the new one does not change are kept."""
    operations = [one for one in plan.get('operations') or () if isinstance(one, dict)]
    earlier = _op_on(operations, op['slide'], op['object'])
    if earlier is not None and 'runs' in earlier and 'runs' in op:
        given = {one['index']: one for one in op['runs']}
        op = {**op, 'runs': sorted([*(one for one in earlier['runs']
                                      if one.get('index') not in given), *given.values()],
                                   key=lambda one: one['index'])}
    kept = [one for one in operations if one is not earlier]
    return {**plan, 'operations': [*kept, op]}


def add_op(root, op: dict) -> dict:
    """Add one operation to the deck's plan (work/patch.json), replacing any earlier one on the
    same object, and to the desk's shared copy of what was changed on the desk
    (desk/patch-ops.json), so another computer can make the plan again. Nothing else in the
    plan changes. Returns the operation as the plan holds it."""
    from runner.steps import existing, outline
    root = Path(root)
    sha = (outline.inventory_of(root) or {}).get('sha256')
    for file in (root / existing.PATCH, root / SHARED_OPS):
        found = home.read_json(file, None)
        plan = found if isinstance(found, dict) else {'sourceSha256': sha, 'operations': []}
        plan = _merged({**plan, 'sourceSha256': sha}, op)
        file.parent.mkdir(parents=True, exist_ok=True)
        home.write_json(file, plan)
    return _op_on(plan_of(root), op['slide'], op['object'])


def with_shared_ops(root, before: list | None = None, slide=None) -> None:
    """After a plan job on a desk deck, make the plan it handed back whole again. A plan made
    for a note on one `slide` changes that slide only: for every other slide the plan before
    it (`before`, its operations) is kept. Then the words the person typed on the desk are
    put back over it, run by run, as `add_op` puts them: the plan's changes to the other runs
    of an object stay, and nothing typed is let go. The shared copy is not changed."""
    from runner.steps import existing
    root = Path(root)
    found = home.read_json(root / existing.PATCH, None)
    if not isinstance(found, dict):
        return
    planned = [one for one in found.get('operations') or () if isinstance(one, dict)]
    if slide is not None and before is not None:
        planned = [*(op for op in before if isinstance(op, dict) and op.get('slide') != slide),
                   *(op for op in planned if op.get('slide') == slide)]
    plan = {**found, 'operations': planned}
    shared = home.read_json(root / SHARED_OPS, None)
    for op in (shared.get('operations') if isinstance(shared, dict) else None) or ():
        if isinstance(op, dict) and op.get('slide') is not None and op.get('object') is not None:
            plan = _merged(plan, op)
    write_atomic(root / existing.PATCH, json.dumps(plan, indent=2, ensure_ascii=False) + '\n')


def _applied(runs: list[str], op: dict | None) -> list[str]:
    """An object's runs with one operation of the plan made to them."""
    now = list(runs)
    if op is not None and isinstance(op.get('text'), str):
        return [op['text']]
    for edit in (op or {}).get('runs') or ():
        if isinstance(edit, dict) and type(edit.get('index')) is int \
                and 0 <= edit['index'] < len(now) and isinstance(edit.get('text'), str):
            now[edit['index']] = edit['text']
    return now
