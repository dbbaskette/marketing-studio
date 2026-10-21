"""What a slide deck is made from: the runner's own rules, and what its workers are told.

What a caller needs to know
---------------------------
    deck.handoff(title, level, blueprint, said, settings, ...)   # deck-handoff.md, as text
    deck.rules(outline, blueprint, budget)      # what the runner refuses in an outline
    deck.shown(outline, design=None)            # an outline as its slides, for a person
    deck.design_rules(outline, design)          # what the runner refuses in a design
    proposal = deck.proposal(outline, design)   # the slides tool's design proposal
    deck.unresolved(proposal)                   # what it still needs, a sentence each
    whole = deck.complete(outline, listed, words)   # with direction, layouts, house rules
    deck.lead(part)                             # a cover, section or closing slide, put right
    deck.brief(written, whole, previews)        # a section's brief, for a worker with tools
    spec = deck.fixed(whole, ids, number)       # what a section's composer may not change
    deck.kept(section, spec)                    # what the runner refuses in a section
    deck.as_approved(section, spec)             # each approved intent, as it was approved
    deck.icons(design, recorded=None)           # each concept's icon, across the deck
    deck.candidates(design)                     # every asset the design selected, by slide
    deck.placed(section, recorded)              # the recorded assets a section draws
    deck.icon_for(ref, found)                   # an icon's library ID, from a search for it
    deck.checked(finding, slides)               # one finding of a review, or why it is wrong
    deck.judging(objectives, slides, packets)   # a review against the design, as it is asked
    kept, problems = deck.judged(given, packets)    # a reviewer's answer to every criterion
    deck.assessment(kept, packets, binding, sources=True)   # as the slides tool takes it
    deck.found(unresolved, kept, slides)        # what it leaves unresolved, as findings
    deck.to_repair(findings, sections)          # the sections a review sends back
    deck.to_outline(findings)                   # what only a change at the outline puts right
    deck.before(slides)                         # what a deck of this size has cost before

- Nothing here starts anything, reads a training or knows about runs. Each function takes
  text or parsed JSON and gives back text, parsed JSON or a list of sentences.
- An outline is the slides tool's own format: what each slide says, and nothing about how
  it is drawn. The tool checks its shape. `rules` adds the four things the runner holds an
  outline to: every content slide names the blueprint objectives it serves and every
  objective is served; no slide shows more words than the budget, counting its title,
  points, caveat and source together; a cover carries a title and one subtitle line; and
  nothing the blueprint lists under its open gaps is on a slide in the blueprint's words.
- A design is how each slide is drawn, written by the outline's writer beside the outline
  when the slides tool keeps a design session: for each slide its intent, composition,
  asset and qualifications, and nothing else. `proposal` joins the two in the tool's schema
  2, taking each slide's title, copy, notes and objectives from the outline, so that the
  copy the person approves has one source.
- HOUSE is what the composers are told that no program can check. It goes into the outline
  as its house rules and into each section's brief. A deck drawn from an approved design
  has DESIGNED_HOUSE instead, which draws what the design approved rather than leaving its
  visuals to the composer.
- `design` is the plan the slides tool approved, as `design check` returns it. Each
  section's brief then carries the approved design of its slides and the icon each concept
  has across the whole deck, and a composer copies each slide's `intent` into its section
  exactly. `fixed` takes the wording from the approved copy and adds the intent and the
  wording the copy must keep. A deck without a design is told and held to what it always
  was.
- `recorded` is the slides tool's asset manifest of the deck, as {asset ID: entry}, for a
  deck whose tool keeps one. A section's brief then names each concept's icon by its ID
  in the brand's library and the asset it is recorded as, and says how a recorded picture
  is placed; with `by_asset`, for a tool that places a recorded icon by its asset ID, so is
  each icon. Without it the brief is as it was. A design may name an icon by its library ID
  (`"refType": "library-id"`), which `candidates` gives as `exact`.
- `brief` rewrites the brief the slides tool writes for one section. That brief is written
  for a worker at a shell, with paths to read and a folder to write in. A worker here has
  tools and no files, so those parts are replaced and everything else is kept as written.
- A section keeps every approved word: `kept` holds its title, objectives, caveat, source
  line and notes to the outline's, and looks for each point's words among the text the
  slide draws. What is drawn, and how, is the composer's.
- A finding is about `drawing` or about `content`. Only a major or critical finding about
  drawing sends a section back to its composer. One about what a slide says is the
  person's to settle, at the outline.
- QUESTIONS are the eight the slides tool asks of every slide, numbered as it numbers
  them, in the runner's words. The tool's own are not handed to a caller, so a change to
  them there has to be made here too.
- A deck drawn from its approved design, on a slides tool that reviews a build against it,
  is reviewed by that tool's own assessment instead: `packets` are what it gives of each
  slide (`review --slide`), its criteria, the objects a judgement may cite and what its own
  screens point at. The reviewer answers every criterion of every slide, and says of each
  that is not a pass how grave it is and whether it is about `drawing`, which keeps the
  approved concept and wording, about `content`, or about the visual `concept`. Nothing
  here judges a visual: `judged` checks only that the answer is whole, and the tool checks
  the rest. What the tool leaves unresolved are the findings, each with its `criterion` and
  its `category` as the tool files it. A grave one about content or concept is not drawn
  again: it goes back to the person, at the outline.
"""
from __future__ import annotations

import json
import re

import runner  # noqa: F401  puts the core on the import path
import checks
from studio_core import deck_direction
from workspace import WorkspaceError

PREVIEWS = 4            # times one composer may render its section
REPAIRS = 2             # rounds of drawing again after a review
DELIVERY = 'reading'    # a deck is read alone as well as presented
DIRECTION = deck_direction.FALLBACK   # only until the brand or a chosen look gives one
RATE = {'dollars': 0.40, 'minutes': 1.25}   # a slide, as the first decks cost
KINDS = ('cover', 'section', 'content', 'closing')
LEADS = ('cover', 'section', 'closing')
LATER = ('direction', 'layouts', 'house', 'approval')
COVER = ('id', 'kind', 'title', 'subtitle', 'notes')
CLOSING_WORDS = 10      # words a closing slide's title and subtitle may hold between them
NAMED = {'cover': ('title', 'cover'), 'section': ('section', 'divider'),
         'closing': ('closing', 'thank', 'end')}
SEVERITIES = ('critical', 'major', 'minor')
GRAVE = SEVERITIES[:2]
ABOUT = ('drawing', 'content')
JUDGED = (*ABOUT, 'concept')    # what a finding is about, in a review against the design
STATUSES = ('pass', 'issue', 'uncertain')
# The slides tool's five categories of a review against the design, as a person reads them.
CATEGORIES = {'asset-failure': 'The pictures and icons it was approved with',
              'design-deviation': 'How it departs from the approved design',
              'visual-teaching': 'Whether the visual teaches',
              'fit-defect': 'How it fits', 'direct-text': 'Direct text by decision'}
ABOUT_WORDS = {'drawing': 'how it is drawn', 'content': 'what it says',
               'concept': 'the visual concept it was approved with'}
MARKED = 'Looked at at full size, slide by slide, by a reviewer that drew none of the deck.'
NOTE = 12               # the shortest note the slides tool takes for a finding
CLUSTER = 3             # overlap findings on one slide that send it back to be drawn again
PARTS = 8               # short labels one point may give the parts of a diagram
PART_WORDS = 6          # words one of them may hold, as the slides tool allows
TEXTS = ('text', 'value', 'label', 'title')     # where a drawing's node holds its words
# What the slides tool knows of an outline, by its capability: a point's short `parts` and
# a slide's `provenance`. A tool without one is handed the outline without it.
KNOWS = {'compose-split-point': 'parts', 'compose-provenance': 'provenance'}
# A team's own bookkeeping, which an audience cannot follow: finding, objective and
# blueprint IDs, and a slug used as a prefix. It goes in `provenance`, never on a slide.
_ID = r'(?:[gf]\d{1,3}|O\d{1,2})'
# A bookkeeping word counts only before an ID ("Finding g4", "Blueprint M1"), so a
# title such as "Research shows" is not refused.
INTERNAL = (re.compile(r'\b(?:Findings?|Blueprint|Objectives?|Research)\b[\s:#]*'
                       r'(?:[gfOM]\d{1,3}\b|\d)', re.I),
            re.compile(rf'\b{_ID}(?:\s*[,/–-]\s*{_ID})+\b'),
            re.compile(rf'^\s*{_ID}(?:[\s,;/–-]+{_ID})*\s*$'),
            re.compile(r'\bO\d\b'), re.compile(r'\bg\d+\b'),
            re.compile(r'(?<![\w-])[a-z0-9]+(?:[-_][a-z0-9]+)+:(?=\s|$)'))
SHOWN = ('title', 'subtitle', 'focal', 'caveat', 'source')   # what a slide shows, by field
WHOLE = ('A point is one sentence: keep its text whole in one shape, with its label in that '
         'shape or right beside it. Never split a sentence across boxes. Where a point gives '
         'short `parts` labels, draw them as the parts of its diagram and keep the sentence '
         'whole once on the slide, unless the brief says it is in the notes.')
CAVEAT = ("A caveat and a source line go in the slide's own caveat and source fields, never in "
          'the drawing.')
AS_DESIGNED = ('Draw what the approved design says: its visual, its composition and the '
               'assets it selected.')
# The studio's own house rules are about what a slide says, never how it looks: the look,
# with its direction and its house style, is the brand's, chosen by the person from rendered
# samples. `house` adds a chosen look's own lines first.
HOUSE = (CAVEAT, WHOLE)
DESIGNED_HOUSE = (*HOUSE, AS_DESIGNED)


def house(designed: bool = False, look: dict | None = None) -> tuple[str, ...]:
    """The house rules a deck is drawn by: the chosen look's house style, then the studio's
    own rules about what a slide says."""
    styled = tuple(str(line) for line in ((look or {}).get('house') or ())
                   if isinstance(line, str) and line.strip())
    return (*styled, *(DESIGNED_HOUSE if designed else HOUSE))


QUESTIONS = (
    'After three seconds, is the main point clear, and is it the claim in the title?',
    'Does the eye land first on what carries the point?',
    'Is there exactly one emphasis?',
    'Does everything on the slide support the title?',
    'Is each label inside or right beside what it names?',
    'Is the space balanced, with nothing stranded or crowded?',
    'Is the slide consistent with its neighbours in style, and different from them in '
    'layout unless they are meant to be compared?',
    'Does every picture and icon explain something?',
)
LOOKS_UNFINISHED = (
    'Does the slide look finished, or like a wireframe: outline boxes on white, no colour '
    "from the deck's direction where a product, an actor or a state is named, no icon where "
    'a recognisable thing is named?',
    "Is any approved point's sentence split across shapes, or does text sit on text?",
    'Does the slide show a team\'s bookkeeping, such as finding, objective or blueprint IDs '
    "or a scenario's slug, where the audience reads it?")
WORD = re.compile(r"[^\W_]+(?:['’.-][^\W_]+)*")
KEY_POINT = re.compile(r'^- (K\d+\.\d+):\s*(.+?)\s*(?:\[[^\]]*\]\s*)*$')
POINTER = re.compile(r'Read `references/[^\n]*')
DESIGNED = ('id', 'intent', 'composition', 'asset', 'qualifications')   # a worker's to write
LEAD = 'outline'        # what a cover, section or closing slide cites, as the slides tool does
LIBRARY = 'library-id'  # an icon candidate whose `ref` is its ID in the brand's library
PLACED = ("A picture the design selected is recorded in the deck's asset manifest. Place it "
          'by its asset ID: `{"type": "image", "id": "<your ID>", "asset": "<asset ID>"}`, '
          'with `alt` where the recorded one does not say what it shows here. `list_assets` '
          'lists every recorded asset. Generated art for a slide whose visual is '
          '`generated-art` is made with `request_asset`, from a brief you write.', '')
USE = ('The deck is both presented and handed out. Every slide must make sense to someone '
       'reading it alone, so no slide may depend on its speaker notes for meaning. The notes '
       'carry the talk track and timing for a presenter.')


# --- the handoff -------------------------------------------------------------------------

def frame(blueprint: str) -> dict:
    """What a blueprint's frame says, keyed by the word before each colon, in lower case."""
    found, inside = {}, False
    for line in blueprint.splitlines():
        if line.startswith('## '):
            inside = line[3:].strip().lower() == 'frame'
        elif inside and ':' in line:
            key, _, value = line.partition(':')
            found[key.strip().lower()] = value.strip()
    return found


def handoff(title: str, level: str | None, blueprint: str, said: dict, target: str | None,
            brand: tuple[str, str] | None, guide: bool, scenarios=None) -> str:
    """deck-handoff.md: one page, written from the record, under the headings the skill's
    own deck stage gives it. `said` is what intake says, `guide` whether the training has
    a learner guide, and `scenarios` the titles of the practice scenarios its closing slide
    points to, in words, or None when the training has no practice."""
    parsed, framed = checks.parse_blueprint(blueprint), frame(blueprint)
    modules = '; '.join(f"{ident}, {module['title']}"
                        for ident, module in parsed['modules'].items())
    closing = ('A closing slide.' if scenarios is None else
               'A last content slide that says what to practise next'
               + (': ' + ', '.join(scenarios) if scenarios else '')
               + ', then a closing slide.')
    made = {'google': 'Google Slides', 'pptx': 'PowerPoint'}.get(target, 'not chosen')
    lines = [f'# Deck handoff: {title}' + (f', level {level}' if level else ''), '',
             'Written by the runner from the record of this training. It is written again '
             'whenever the blueprint or the settings change.', '',
             '## Goal', '', 'After the deck the audience can:', '']
    lines += [f"- {objective['text']} ({ident})"
              for ident, objective in parsed['objectives'].items()]
    lines += ['', '## Audience and duration', '',
              f"Audience: {framed.get('audience') or said.get('audience') or 'not given'}",
              f"Duration: {framed.get('time') or said.get('time limit') or 'not given'}"]
    lines += [f'Level: {level}'] if level else []
    lines += ['', '## Use', '', USE, '', '## Required elements', '',
              '- The objectives near the start.',
              '- A check for understanding in each module' + (f': {modules}.' if modules
                                                              else '.'),
              '- A recap.', f'- {closing}', '', '## Sources', '',
              'Work from the blueprint, ' + ('the learner guide and ' if guide else 'and ')
              + 'the research findings. They are your sources, not the audience\'s: a '
              "slide's `source` cites only what the audience can look up by name, such as a "
              "product's documentation, or is left out. Finding, objective and blueprint "
              "IDs go in the slide's `provenance`, which only the speaker notes carry.", '',
              '## Research', '',
              'Complete. Work from the sources only and start no new research. Anything '
              "under the blueprint's open gaps stays out.", '', '## Output', '',
              made + (f', in the brand {brand[0]}' + (f' ({brand[1]}).' if brand[1] else '.')
                      if brand else
                      ', with no brand chosen.'), '']
    assessment = parsed.get('assessment') or {}
    lines += ['## Teaching and assessment', '',
              'Use the module timing for explanation, demonstration, learner practice and '
              'debrief. A slide count is not a duration plan. Each check needs an answer '
              'and rationale in the presenter notes. Keep learner-facing meaning visible.', '']
    # Carry the author's actual check/observation wording, not an invented replacement.
    if isinstance(assessment, dict):
        lines += [f'- {ident}: {value}' for ident, value in assessment.items()]
    lines += ['']
    return '\n'.join(lines)


# --- the outline's rules -----------------------------------------------------------------

def count(text) -> int:
    """How many words a piece of text has."""
    return len(WORD.findall(text)) if isinstance(text, str) else 0


def _points(slide: dict) -> list[dict]:
    return [point for point in slide.get('points') or () if isinstance(point, dict)]


def visible(slide: dict) -> int:
    """The words a slide will show: its title, its points, its caveat and its source."""
    return (count(slide.get('title')) + count(slide.get('caveat')) + count(slide.get('source'))
            + sum(count(point.get('label')) + count(point.get('text'))
                  + sum(count(node) for node in _parts_of(point))
                  for point in _points(slide)))


def _parts_of(point: dict) -> list[str]:
    """A point's short labels for the parts of a diagram, when it gives them."""
    nodes = point.get('parts') if isinstance(point, dict) else None
    return [node for node in nodes if isinstance(node, str)] if isinstance(nodes, list) else []


def for_tool(outline, knows=frozenset()):
    """An outline as the slides tool takes it: without the short `parts` labels a point
    gives its diagram, and without a slide's `provenance`, when the tool does not know
    them. `knows` holds what it knows, by the names KNOWS gives. The runner keeps its own."""
    if not isinstance(outline, dict) or not isinstance(outline.get('slides'), list):
        return outline
    slides = []
    for slide in outline['slides']:
        if not isinstance(slide, dict):
            slides.append(slide)
            continue
        made = dict(slide)
        if 'provenance' not in knows:
            made.pop('provenance', None)
        if 'parts' not in knows and isinstance(slide.get('points'), list):
            made['points'] = [{key: value for key, value in point.items() if key != 'parts'}
                              if isinstance(point, dict) else point
                              for point in slide['points']]
        slides.append(made)
    return {**outline, 'slides': slides}


def with_provenance(outline, knows=frozenset()):
    """An outline whose slides' `provenance` the slides tool does not know: each one is
    added to that slide's notes instead, where a presenter reads it and no slide shows it."""
    if 'provenance' in knows or not isinstance(outline, dict) \
            or not isinstance(outline.get('slides'), list):
        return outline
    slides = []
    for slide in outline['slides']:
        said = slide.get('provenance') if isinstance(slide, dict) else None
        if isinstance(said, str) and said.strip():
            notes = slide.get('notes') if isinstance(slide.get('notes'), str) else ''
            slide = {**{key: value for key, value in slide.items() if key != 'provenance'},
                     'notes': (notes.rstrip() + '\n\n' if notes.strip() else '')
                     + f'Provenance: {said.strip()}'}
        slides.append(slide)
    return {**outline, 'slides': slides}


def internal(text) -> str | None:
    """The bookkeeping a piece of a slide's visible copy shows, or None when it shows none.
    A web address is a citation, and is left out."""
    if not isinstance(text, str):
        return None
    bare = re.sub(r'https?://\S+', '', text)
    for pattern in INTERNAL:
        found = pattern.search(bare)
        if found:
            return found.group(0).strip(' ;.')
    return None


def provenance_rules(outline, slugs=()) -> list[str]:
    """What the runner refuses because it shows a team's bookkeeping on a slide: finding,
    objective or blueprint IDs, and scenario slugs, in any visible field. Each problem says
    where it goes instead."""
    problems = []
    told = ('Audiences cannot follow finding, objective or blueprint IDs, or a scenario\'s '
            'slug. Cite a document the audience can look up by name in `source`, such as '
            '"Tanzu for Postgres 4.5 documentation", or leave it out; write a scenario by its '
            'title in words; and put the IDs in the slide\'s `provenance`, which goes only '
            'into the speaker notes.')
    named = [slug for slug in slugs if isinstance(slug, str) and slug]
    for slide in slides_of(outline):
        ident = slide.get('id') or 'a slide'
        if 'provenance' in slide and (not isinstance(slide['provenance'], str)
                                      or not slide['provenance'].strip()):
            problems.append(f'{ident}: `provenance` is text: the IDs and notes behind the '
                            'slide, which no slide shows. Leave it out when there are none.')
        seen = [(key, slide.get(key)) for key in SHOWN]
        seen += [(f'a point\'s {key}', point.get(key)) for point in _points(slide)
                 for key in ('label', 'text')]
        seen += [("a point's part", part) for point in _points(slide)
                 for part in _parts_of(point)]
        for where, text in seen:
            # A scenario's slug: anywhere when it is hyphenated, as only a slug is, and
            # otherwise only as a prefix, so that a plain word is not taken for one.
            found = internal(text) or next(
                (slug for slug in named if isinstance(text, str) and re.search(
                    rf'(?<![\w-]){re.escape(slug)}' + (r'(?![\w-])' if re.search('[-_]', slug)
                                                        else ':'), text)), None)
            if found:
                problems.append(f'{ident}: {where} shows {json.dumps(found)}. {told}')
    return problems


def plain(text) -> str:
    """Text as it is compared: lower case, one space between its words, nothing else."""
    return ' '.join(WORD.findall(text.lower())) if isinstance(text, str) else ''


def gaps(blueprint: str) -> dict:
    """The key points a deck must leave out: each one the blueprint marks as unsupported
    or names under its open gaps, with its wording."""
    points, section = {}, None
    for line in blueprint.splitlines():
        if line.startswith('## '):
            section = line[3:].strip().lower()
        found = KEY_POINT.match(line)
        if found and section != 'open gaps':
            points[found.group(1)] = (found.group(2), '[unsupported]' in line)
    named = set(re.findall(r'\bK\d+\.\d+\b', checks.parse_blueprint(blueprint)['open_gaps']))
    return {ident: text for ident, (text, unsupported) in points.items()
            if unsupported or ident in named}


def _says(slide: dict) -> str:
    """Everything a slide says, to its audience and to its presenter, as it is compared."""
    said = [slide.get(key) for key in ('title', 'subtitle', 'understand', 'focal', 'caveat',
                                       'notes')]
    said += [point.get(key) for point in _points(slide) for key in ('label', 'text')]
    said += [node for point in _points(slide) for node in _parts_of(point)]
    return ' . '.join(plain(text) for text in said if text)


def slides_of(outline) -> list[dict]:
    """An outline's slides, leaving out anything that is not one."""
    found = outline.get('slides') if isinstance(outline, dict) else None
    return [slide for slide in found or () if isinstance(slide, dict)]


def rules(outline, blueprint: str, budget: int | None = None) -> list[str]:
    """What the runner holds an outline to, beyond the slides tool's own check. Each
    problem is a sentence the worker can act on. `budget` is the most words one slide may
    show, when the tool has said."""
    if not isinstance(outline, dict) or not slides_of(outline):
        return ['The outline is one JSON object with its slides under "slides".']
    problems = [f'Leave out `{key}`: it is added after you hand the outline in.'
                for key in LATER if key in outline]
    if outline.get('delivery') not in (None, DELIVERY):
        problems.append(f'This deck is read alone as well as presented: set `delivery` to '
                        f'"{DELIVERY}".')
    objectives = list(checks.parse_blueprint(blueprint)['objectives'])
    left_out, served = gaps(blueprint), set()
    for slide in slides_of(outline):
        ident, kind = slide.get('id') or 'a slide', slide.get('kind')
        if kind == 'cover':
            extra = sorted(key for key in slide if key not in COVER)
            if extra:
                problems.append(f'{ident}: a cover carries a title and one subtitle line, '
                                'and no more. Leave out ' + ', '.join(extra) + '.')
            if '\n' in str(slide.get('subtitle') or '').strip():
                problems.append(f'{ident}: the subtitle of a cover is one line.')
        if kind in LEADS and any('\n' in str(slide.get(key) or '').strip()
                                 for key in ('title', *(('subtitle',) if kind != 'cover'
                                                        else ()))):
            problems.append(f'{ident}: a {kind} slide\'s title and subtitle are one line '
                            'each. Put a second line in the subtitle, or on a content slide.')
        if kind == 'closing':
            # A closing slide is the template's own, with room for a few words and no body.
            said = f"{slide.get('title') or ''} {slide.get('subtitle') or ''}".split()
            extra = sorted(key for key in slide if key not in COVER)
            if extra or len(said) > CLOSING_WORDS:
                problems.append(f'{ident}: a closing slide is the brand\'s own last slide: a '
                                f'title and one subtitle line, {CLOSING_WORDS} words at most '
                                'between them, and nothing drawn under it. Put anything the '
                                'audience should read, such as what to practise next, on a '
                                'content slide before it.')
        for point in _points(slide):
            if 'parts' not in point:
                continue
            nodes = point['parts']
            if not isinstance(point.get('text'), str) or not point['text'].strip() \
                    or not isinstance(nodes, list) or not 1 <= len(nodes) <= PARTS \
                    or not all(isinstance(node, str) and 1 <= count(node) <= PART_WORDS
                               for node in nodes):
                problems.append(f'{ident}: `parts` gives a point with a text 1 to {PARTS} '
                                f'short labels, {PART_WORDS} words at most each, for the '
                                'parts of its diagram. Its text stays one whole sentence.')
        if kind == 'content':
            sources = slide.get('sources')
            sources = sources if isinstance(sources, list) else []
            unknown = [str(source) for source in sources if source not in objectives]
            if unknown:
                problems.append(f'{ident}: `sources` names ' + ', '.join(unknown) + ', which '
                                'the blueprint does not have. It may hold only the '
                                'objectives this slide serves: ' + ', '.join(objectives) + '.')
            elif not sources:
                problems.append(f'{ident}: `sources` is empty. Name the objectives this '
                                'slide serves, or leave the slide out.')
            served.update(sources)
            if budget and visible(slide) > budget:
                problems.append(f'{ident}: {visible(slide)} words will be seen, counting the '
                                f'title, the points, the caveat and the source. The most is '
                                f'{budget}. Say less, or make it two slides.')
        said = _says(slide)
        problems += [f'{ident}: this states {gap}, which the blueprint lists under its open '
                     'gaps. Leave it out.' for gap, text in left_out.items()
                     if plain(text) and plain(text) in said]
    slugs = [entry['id'] for entry in checks.parse_blueprint(blueprint)['practice']]
    problems += provenance_rules(outline, slugs)
    missing = [objective for objective in objectives if objective not in served]
    if missing:
        problems.append('No slide serves ' + ', '.join(missing) + '. Every objective is '
                        'named in the `sources` of at least one content slide.')
    return problems


def shown(outline, design=None) -> list[dict]:
    """An outline as its slides, in order, for a person to read. With the design proposed
    with it, each slide also says how it is drawn; without, its `design` is None."""
    def text(slide: dict, key: str) -> str | None:
        return slide[key] if isinstance(slide.get(key), str) and slide[key].strip() else None

    drawn = {slide.get('id'): drawn_as(slide) for slide in slides_of(design)}

    return [{'id': str(slide.get('id') or ''), 'kind': str(slide.get('kind') or ''),
             'title': str(slide.get('title') or ''), 'subtitle': text(slide, 'subtitle'),
             'understand': text(slide, 'understand'),
             'points': [{'label': str(point.get('label') or ''),
                         'text': str(point.get('text') or ''),
                         **({'parts': _parts_of(point)} if _parts_of(point) else {})}
                        for point in _points(slide)],
             'caveat': text(slide, 'caveat'), 'source': text(slide, 'source'),
             'notes': text(slide, 'notes'),
             'serves': [str(source) for source in slide.get('sources') or ()
                        if isinstance(slide.get('sources'), list)],
             'design': drawn.get(slide.get('id'))}
            for slide in slides_of(outline)]


# --- the design proposed with the outline ------------------------------------------------

def design_rules(outline, design) -> list[str]:
    """What the runner refuses in the design a worker hands in with an outline, before the
    slides tool sees it: one entry for every slide, in the outline's order, holding only
    what is the worker's to write. Each problem is a sentence the worker can act on."""
    if not isinstance(design, dict) or not isinstance(design.get('slides'), list):
        return ['The design is one JSON object, with one entry for each slide under "slides".']
    problems = [f'Leave out `{key}`: the design holds its slides and nothing else.'
                for key in design if key != 'slides']
    wanted = [slide.get('id') for slide in slides_of(outline)]
    entries = design['slides']
    if [entry.get('id') if isinstance(entry, dict) else None for entry in entries] != wanted:
        return problems + ['The design has one entry for every slide of the outline, the '
                           'cover, section and closing slides too, in its order: '
                           + ', '.join(str(ident) for ident in wanted) + '.']
    for entry in entries:
        extra = sorted(key for key in entry if key not in DESIGNED)
        if extra:
            problems.append(f"{entry['id']}: leave out " + ', '.join(f'`{key}`' for key in extra)
                            + '. The title, the copy, the notes and the objectives are taken '
                            'from the outline.')
    return problems


def _copy(slide: dict) -> dict:
    """What a slide shows besides its title, as the slides tool's design takes it: a content
    slide's points, focal statement, caveat and source; a lead slide's subtitle, or its
    title when it has nothing else."""
    def text(value) -> bool:
        return isinstance(value, str) and bool(value.strip())

    if slide.get('kind') != 'content':
        return {'points': [], 'focal': slide['subtitle'] if text(slide.get('subtitle'))
                else slide.get('title')}
    copy = {'points': [{key: point[key] for key in ('label', 'text') if text(point.get(key))}
                       for point in _points(slide)]}
    copy['points'] = [point for point in copy['points'] if point]
    copy.update({key: slide[key] for key in ('focal', 'caveat', 'source')
                 if text(slide.get(key))})
    if not copy['points'] and 'focal' not in copy:
        copy['focal'] = slide.get('title')
    return copy


def proposal(outline, design) -> dict:
    """The design proposal the slides tool keeps, in its schema 2, made from an outline and
    the design handed in with it, which `design_rules` has let through. The outline gives
    each slide its title, its visible copy, its notes and the objectives it serves, which
    are also its sources; a lead slide's source is the outline itself. The design gives
    the rest. A slide's evidence is its sources unless the design names its own."""
    written = {entry['id']: entry for entry in design['slides']}
    slides = []
    for slide in slides_of(outline):
        mine, content = written[slide['id']], slide.get('kind') == 'content'
        sources = [str(source) for source in slide.get('sources') or ()] if content else []
        intent = mine.get('intent')
        if isinstance(intent, dict) and 'evidence' not in intent:
            intent = {**intent, 'evidence': sources or [LEAD]}
        made = {'id': slide['id'], 'title': slide.get('title'), 'sources': sources or [LEAD]}
        made.update({'objectives': sources} if sources else {})
        made['copy'] = _copy(slide)
        made.update({'qualifications': mine['qualifications']}
                    if 'qualifications' in mine else {})
        made.update({'notes': slide['notes']} if isinstance(slide.get('notes'), str)
                    and slide['notes'].strip() else {})
        made.update(composition=mine.get('composition'), intent=intent, asset=mine.get('asset'))
        slides.append(made)
    return {'schema': 2, 'title': outline.get('title'), 'scope': 'new', 'slides': slides}


def drawn_as(slide: dict) -> dict:
    """How one slide of a design proposal is drawn, for a person to read beside its copy."""
    intent = slide.get('intent') if isinstance(slide.get('intent'), dict) else {}
    asset = slide.get('asset') if isinstance(slide.get('asset'), dict) else {}
    visual = intent.get('visual') if isinstance(intent.get('visual'), dict) else {}
    other = intent.get('alternative') if isinstance(intent.get('alternative'), dict) else {}
    return {'claim': intent.get('takeaway'), 'question': intent.get('audienceQuestion'),
            'family': visual.get('family'), 'purpose': visual.get('purpose'),
            'drawn': slide.get('composition'), 'why': intent.get('rationale'),
            'alternative': ({'treatment': other.get('treatment'), 'reason': other.get('reason')}
                            if other else None),
            'asset': {key: asset.get(key) for key in ('description', 'disposition', 'reason')},
            'candidates': [{key: candidate.get(key) for key in ('kind', 'ref', 'concept',
                                                                 'status')}
                           for candidate in asset.get('candidates') or ()
                           if isinstance(candidate, dict)],
            'keeps': [str(kept) for kept in slide.get('qualifications') or ()]}


def unresolved(design) -> list[str]:
    """What a design proposal still needs, a sentence each: an asset it could not find, and
    each candidate not yet resolved."""
    found = []
    for number, slide in enumerate(design.get('slides') or (), start=1):
        shown = drawn_as(slide)
        if shown['asset']['disposition'] == 'unavailable':
            found.append(f'Slide {number}: the asset it would use is unavailable, so it is '
                         'drawn another way.')
        found += [f"Slide {number}: the {candidate['kind']} \"{candidate['ref']}\" for "
                  f"{candidate['concept']} is not resolved yet."
                  for candidate in shown['candidates'] if candidate['status'] == 'pending']
    return found


def before(slides: int) -> dict:
    """What a deck of this many slides has cost before, in dollars and minutes of agent
    time. A round of drawing again after a review has cost as much again."""
    return {'dollars': round(RATE['dollars'] * slides, 2),
            'minutes': round(RATE['minutes'] * slides, 1)}


# --- starting the deck -------------------------------------------------------------------

def layouts(listed, slides: list[dict], preferred: dict | None = None) -> dict:
    """The template layout for each kind of lead slide an outline has: the one the deck's
    look names for that kind (`preferred`, such as the brand's title-capable closing) when
    the template has it and it holds what the slide carries; else one that shows a title,
    has room for the subtitle if there is one and no place for a picture, and is named for
    that kind of slide where the template has such a one."""
    chosen = {}
    listed = [layout for layout in listed or () if isinstance(layout, dict)
              and isinstance(layout.get('name'), str)]
    for kind in LEADS:
        mine = [slide for slide in slides if slide.get('kind') == kind]
        if not mine:
            continue
        need = 1 if any(slide.get('subtitle') for slide in mine) else 0
        wanted = next((layout for layout in listed if layout['name']
                       == (preferred or {}).get(kind) and layout.get('title')
                       and (layout.get('subtitles') or 0) >= need), None)
        if wanted:
            chosen[kind] = wanted['name']
            continue
        fits = [layout for layout in listed
                if layout.get('title') and (layout.get('subtitles') or 0) >= need]
        fits = [layout for layout in fits if not layout.get('pictures')] or fits
        named = [layout for layout in fits
                 if any(word in layout['name'].lower() for word in NAMED[kind])] or fits
        exact = [layout for layout in named if (layout.get('subtitles') or 0) == need]
        if not named:
            raise WorkspaceError(
                f"The brand's template has no layout that shows the title of a {kind} "
                'slide' + (' with its subtitle' if need else '') + ', so the deck cannot '
                'be started with this brand.')
        chosen[kind] = (exact or named)[0]['name']
    return chosen


def complete(outline: dict, listed, words: list[str], designed: bool = False,
             look: dict | None = None, knows=frozenset()) -> dict:
    """An approved outline as the slides tool starts a deck from: with the direction, a
    layout for each kind of lead slide, the house rules, and the person's own words of
    approval. A deck `designed` is drawn from its approved design. `look` is what the
    deck is drawn in: the look the person chose, as {'direction', 'house'}, or the brand's
    own direction alone. Without one a deck has deck_direction.FALLBACK. A slide's
    `provenance` joins its notes unless the slides tool `knows` it."""
    look = look or {}
    outline = with_provenance(outline, knows)
    return {**outline, 'delivery': DELIVERY,
            'direction': dict(look.get('direction') or DIRECTION),
            'layouts': layouts(listed, slides_of(outline), look.get('layouts')),
            'house': list(house(designed, look)), 'approval': list(words)}


def lead(part: dict) -> dict:
    """A lead slide's file as the compiler takes it. A cover has no second line under its
    subtitle: no layout holds one."""
    slides = [{key: value for key, value in slide.items() if key != 'detail'}
              if isinstance(slide, dict) else slide for slide in part.get('slides') or ()]
    return {**part, 'slides': slides}


def _part(text: str, heading: str, body: str, renamed: str | None = None) -> str:
    """A brief with what is under one heading replaced. A heading the brief does not have
    is added at its end."""
    new = f'## {renamed or heading}\n\n{body.strip()}\n'
    pattern = re.compile(rf'^## {re.escape(heading)}[^\n]*\n.*?(?=^## |\Z)', re.S | re.M)
    if pattern.search(text):
        return pattern.sub(lambda found: new + '\n', text, count=1)
    return text.rstrip('\n') + '\n\n' + new


def brief(written: str, whole: dict, previews: int = PREVIEWS, design=None,
          recorded: dict | None = None, by_asset: bool = False) -> str:
    """The brief the slides tool wrote for one section, for a worker with tools and no
    files. Its slides, their order and the direction are kept as written. With `design`,
    the plan the slides tool approved, it also carries the approved design of each of its
    slides and the icon of each concept across the deck; with `recorded`, the deck's asset
    manifest, each by the ID it is recorded with. With `by_asset`, for a slides tool that
    places a recorded icon by its asset ID, an icon is placed so."""
    skeleton = json.dumps({'version': 1, 'title': whole.get('title'),
                           'direction': whole.get('direction') or DIRECTION,
                           'slides': ['your slides, in order']}, ensure_ascii=False)
    text = POINTER.sub('Your instructions say how to work; `list_inputs` shows what you '
                       'can read.', written)
    named = ('id', 'title', 'sources', *(('intent',) if design else ()))
    shape, copied = (''.join(f'{mark}{key}{mark}, ' for key in named) for mark in '"`')
    text = _part(text, 'Paths', f'''
One JSON object, the section, handed in with `submit_section`:

```json
{skeleton}
```

Each slide is `{{{shape}"brief": {{"relation", "focal": the ID of the node that carries the point, "rhythm"}}, "canvas", "connect"?, "caveat"?, "source"?, "notes"}}`. Copy each slide's {copied}caveat, source line and notes exactly as they are given below, and keep every word of every point. The input "composition contract" has the exact format.''',
                 'What you write')
    text = _part(text, 'House style', '\n'.join(
        f'- {line}' for line in (whole.get('house') or (DESIGNED_HOUSE if design else HOUSE))))
    text = _part(text, 'Colour', deck_direction.told(whole.get('direction') or DIRECTION))
    parts = _parts_told(whole, named_in(written, whole))
    if parts:
        text = _part(text, 'Diagram parts', parts)
    if design:
        text = _part(text, 'The approved design', drawn_from(design, named_in(written, whole),
                                                             recorded, by_asset))
        text = _part(text, 'Icons across the deck', _icons_told(
            icons(design, recorded), recorded is not None, by_asset and recorded is not None))
    text = _part(text, 'Preview', f'''
`preview_section` renders your whole section and returns a picture of every slide, with what the renderer found. You have {previews} previews. `check_section` is free: use it until the section compiles before you spend a preview.''')
    return _part(text, 'Return', '''
Hand the section in with `submit_section`. It must be the version you last previewed. Say what you changed after looking at the pictures and what still bothers you, naming your weakest slide.''')


def _parts_told(whole: dict, ids: list[str]) -> str:
    """The short labels the points of a section's slides give their diagrams, for its
    composer: each drawn whole, in a shape of its own, with the point's sentence kept whole
    once on the slide or left in the notes."""
    by_id = {slide.get('id'): slide for slide in slides_of(whole)}
    lines = []
    for ident in ids:
        for point in _points(by_id.get(ident) or {}):
            if _parts_of(point):
                lines.append(f"- `{ident}`, {json.dumps(point.get('label') or point.get('text'))}"
                             ': ' + ', '.join(json.dumps(node) for node in _parts_of(point)))
    if not lines:
        return ''
    return '\n'.join(['These points give their diagrams shorter parts. Draw each short label '
                      "whole, in a shape of its own. Keep the point's sentence whole once on "
                      'the slide, or leave it only in the notes, where it already is. Never '
                      'split the sentence itself across shapes.', '', *lines])


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def drawn_from(design, ids: list[str], recorded: dict | None = None,
               by_asset: bool = False) -> str:
    """What a section's composer is told of the approved design of its slides, one record
    each, with the intent it copies. With `recorded`, each candidate says how it is
    recorded, and a picture is placed by its asset ID; with `by_asset`, an icon too."""
    by_id = {slide.get('id'): slide for slide in slides_of(design)}
    lines = ['The person approved how each of your slides teaches together with what it '
             'says, in one decision. Draw each as its design says: the visual, what the '
             'composition places and joins, and the asset it selected. How you realise it '
             'is yours: the layout, the sizes, what is large. A slide whose visual is `text` '
             'is direct text by decision: draw it as text and add nothing to decorate it. If '
             'a design cannot be drawn as approved, draw the nearest you can and say so when '
             'you hand in. Another concept needs the person\'s approval.', '',
             *(PLACED if recorded is not None else (
                 'Only icons can be placed in this version. Where a design selects a picture, '
                 'draw the rest as designed and name the picture when you hand in.', '')),
             'Copy each slide\'s `intent` into it exactly as it is given here. The slides '
             'tool checks it against the approval.']
    for ident in ids:
        slide = by_id.get(ident) or {}
        shown = drawn_as(slide)
        lines += ['', f'### `{ident}`', '', f"- Claim: {shown['claim']}",
                  f"- The question it answers: {shown['question']}",
                  f"- Relationship: {(slide.get('intent') or {}).get('relationship')}",
                  f"- Visual: {shown['family']}. Its purpose: {shown['purpose']}",
                  f"- How it is drawn: {shown['drawn']}", f"- Why: {shown['why']}"]
        if shown['alternative']:
            lines.append(f"- Weighed against: {shown['alternative']['treatment']}. "
                         f"{shown['alternative']['reason']}")
        asset = shown['asset']
        lines.append(f"- Asset: {asset['description']} ({asset['disposition']}: "
                     f"{asset['reason']})")
        lines += [f"  - {candidate['kind']} \"{candidate['ref']}\" for {candidate['concept']}"
                  + (_held(candidate, (recorded or {}).get(candidate['asset']), by_asset)
                     if recorded is not None else
                     ', still to be found' if candidate['status'] == 'pending' else '')
                  for candidate in _with_ids(slide)]
        lines += [f'- Wording it must keep: {_json(kept)}' for kept in shown['keeps']]
        lines += ['- `intent`, to copy:', '', '```json', _json(slide.get('intent')), '```']
    return '\n'.join(lines)


def _held(candidate: dict, entry: dict | None, by_asset: bool = False) -> str:
    """How a candidate stands in the deck's asset manifest, as its composer is told."""
    if entry is None:
        return (f", to be made with `request_asset` as `{candidate['asset']}`"
                if candidate['kind'] == 'generated' else ', not recorded')
    if candidate['kind'] == 'icon' and by_asset:
        return (f", recorded as `{candidate['asset']}`, the icon `{entry.get('ref')}`: place "
                'it by that asset ID')
    if candidate['kind'] == 'icon':
        return f", recorded as `{candidate['asset']}`: the icon `{entry.get('ref')}`"
    return f", recorded as `{candidate['asset']}`: place it by that asset ID"


def _with_ids(slide: dict) -> list[dict]:
    """A slide's candidates as `drawn_as` gives them, each with its `asset` ID."""
    asset = slide.get('asset') if isinstance(slide.get('asset'), dict) else {}
    raw = [candidate for candidate in asset.get('candidates') or ()
           if isinstance(candidate, dict)]
    return [{**shown, 'asset': candidate.get('assetId')}
            for shown, candidate in zip(drawn_as(slide)['candidates'], raw)]


def candidates(design) -> list[dict]:
    """Every asset candidate of the approved design, as {'slide', 'asset', 'kind', 'ref',
    'concept', 'alt', 'exact'}, in slide order. `exact` says an icon's `ref` is its ID in
    the brand's library."""
    return [{'slide': slide.get('id'), 'asset': candidate.get('assetId'),
             'kind': candidate.get('kind'), 'ref': candidate.get('ref'),
             'concept': candidate.get('concept'), 'alt': candidate.get('alt'),
             'exact': candidate.get('refType') == LIBRARY}
            for slide in slides_of(design) if isinstance(slide.get('asset'), dict)
            for candidate in slide['asset'].get('candidates') or ()
            if isinstance(candidate, dict)]


def icons(design, recorded: dict | None = None) -> list[dict]:
    """The icon the approved design names for each concept, across every slide of the
    deck, as {'concept', 'ref', 'status', 'slides'}, in the order they first appear. With
    `recorded`, the deck's asset manifest, each also has `icon`, its ID in the brand's
    library, and `asset`, the ID it is recorded as: both None for one not recorded."""
    found: dict = {}
    for slide in slides_of(design):
        for candidate in _with_ids(slide):
            if candidate['kind'] != 'icon':
                continue
            entry = (recorded or {}).get(candidate['asset']) or {}
            made = found.setdefault((candidate['concept'], candidate['ref']), {
                'concept': candidate['concept'], 'ref': candidate['ref'],
                'status': candidate['status'], 'slides': [],
                **({'icon': entry.get('ref'), 'asset': candidate['asset'] if entry else None}
                   if recorded is not None else {})})
            made['status'] = 'resolved' if 'resolved' in (made['status'], candidate['status']) \
                else made['status']
            if slide.get('id') not in made['slides']:
                made['slides'].append(slide.get('id'))
    return list(found.values())


def _icons_told(listed: list[dict], recorded: bool = False, by_asset: bool = False) -> str:
    if not listed:
        return ('The approved design names no icon. Use one only where it names a '
                'recognisable thing, and the same one for the same thing in every section.')
    if by_asset:
        return '\n'.join(['The same concept has the same icon in every section of the deck. '
                          'These are the icons the approved design names, found in the '
                          "brand's library and recorded before any section was drawn. Place "
                          'each by the asset ID it is recorded as, on any slide of yours that '
                          'shows that concept: `{"type": "icon", "id": "<your ID>", "asset": '
                          '"<asset ID>"}`. `search_icons` finds others, for a thing the design '
                          'does not name.', ''] + [
            f"- {icon['concept']}: recorded as `{icon['asset']}`, the icon `{icon['icon']}`, on "
            + ', '.join(f'`{ident}`' for ident in icon['slides']) for icon in listed])
    if recorded:
        return '\n'.join(['The same concept has the same icon in every section of the deck. '
                          'These are the icons the approved design names, found in the '
                          "brand's library and recorded before any section was drawn. Use "
                          'each ID as the `icon` of an icon node, on any slide of yours that '
                          'shows that concept. `search_icons` finds others, for a thing the '
                          'design does not name.', ''] + [
            f"- {icon['concept']}: `{icon['icon']}`, recorded as `{icon['asset']}`, on "
            + ', '.join(f'`{ident}`' for ident in icon['slides']) for icon in listed])
    return '\n'.join(['The same concept has the same icon in every section of the deck. These '
                      'are the icons the approved design names, on every slide. Find each with '
                      '`search_icons` by its name and use the ID it gives you for that '
                      'concept, on any slide of yours that shows it.', ''] + [
        f"- {icon['concept']}: \"{icon['ref']}\", on " + ', '.join(
            f'`{ident}`' for ident in icon['slides']) for icon in listed])


def named_in(written: str, whole: dict) -> list[str]:
    """The slides a section's brief gives its worker, by ID, in the outline's order."""
    return [slide['id'] for slide in slides_of(whole)
            if slide.get('kind') == 'content' and f"`{slide.get('id')}`" in written]


def fixed(whole: dict, ids: list[str], number: int, design=None) -> dict:
    """What the composer of one section may not change: the deck's title and direction,
    and for each of its slides the title, the objectives, the points, the caveat, the
    source line and the notes that were approved. With `design`, the plan the slides tool
    approved, the title and the visible copy are the approved ones, and each slide also
    has the wording it must keep and its approved `intent`, as the JSON text the slides
    tool compares: a text keeps the order of its keys wherever it is kept."""
    by_id = {slide.get('id'): slide for slide in slides_of(whole)}
    made = {'title': whole.get('title'), 'direction': whole.get('direction') or DIRECTION,
            'prefix': f's{number}_',
            'slides': [{'id': ident, 'title': by_id[ident].get('title'),
                        'sources': list(by_id[ident].get('sources') or ()),
                        'points': [{'label': point.get('label'), 'text': point.get('text'),
                                    'parts': _parts_of(point)}
                                   for point in _points(by_id[ident])],
                        'caveat': by_id[ident].get('caveat'),
                        'source': by_id[ident].get('source'),
                        'notes': by_id[ident].get('notes'),
                        **({'provenance': by_id[ident]['provenance']}
                           if by_id[ident].get('provenance') else {})} for ident in ids]}
    if design is None:
        return made
    approved = {slide.get('id'): slide for slide in slides_of(design)}
    for slide in made['slides']:
        mine = approved.get(slide['id']) or {}
        copy = mine.get('copy') if isinstance(mine.get('copy'), dict) else {}
        # The short labels are the outline's own: the approved copy does not carry them.
        nodes = {(point['label'], point['text']): point['parts'] for point in slide['points']}
        slide.update(title=mine.get('title'), points=[
            {'label': point.get('label'), 'text': point.get('text'),
             'parts': nodes.get((point.get('label'), point.get('text'))) or []}
            for point in copy.get('points') or () if isinstance(point, dict)],
            caveat=copy.get('caveat'), source=copy.get('source'),
            intent=json.dumps(mine.get('intent'), separators=(',', ':'), ensure_ascii=False),
            qualifications=[str(kept) for kept in mine.get('qualifications') or ()])
    return made


def icon_for(ref, found) -> str | None:
    """The brand library's ID for the icon a design names by `ref`, from what a search of
    the library for it found: the one whose ID is `ref`, else the one called that, else the
    first found. None when the search found no icon that can be drawn."""
    found = [icon for icon in found or () if isinstance(icon, dict)
             and isinstance(icon.get('id'), str) and icon.get('native', True) is not False]
    wanted = plain(ref)
    for chosen in ([icon for icon in found if icon['id'] == ref],
                   [icon for icon in found if plain(icon.get('name')) == wanted], found):
        if chosen:
            return chosen[0]['id']
    return None


def placed(section, recorded: dict) -> list[str]:
    """The assets of the deck's manifest a section draws, by their IDs, in the order it
    draws them: each picture or icon it names by `asset`, and each recorded icon whose
    library ID it places."""
    found: list[str] = []
    by_icon = {entry.get('ref'): ident for ident, entry in recorded.items()
               if entry.get('kind') == 'icon'}

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            # A picture is named by `asset`, in an image node or a layout's picture slot, and
            # so is an icon placed by its asset ID; another icon by its library ID.
            named = by_icon.get(node.get('icon')) \
                if node.get('type') == 'icon' and 'asset' not in node else node.get('asset')
            if isinstance(named, str) and named in recorded and named not in found:
                found.append(named)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    for slide in slides_of(section):
        walk([slide.get('canvas'), slide.get('picture')])
    return found


# --- a section, as it is handed in -------------------------------------------------------

def _drawn(node, found: list[str], ids: list[str]) -> None:
    """Every piece of text a drawing shows, in the order it is written, and every ID in it.
    A badge's character is not one of the slide's words."""
    if isinstance(node, list):
        for item in node:
            _drawn(item, found, ids)
    elif isinstance(node, dict):
        if isinstance(node.get('id'), str) and ('type' in node or 'from' in node):
            ids.append(node['id'])
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                _drawn(value, found, ids)
            elif isinstance(value, str) and key in ('text', 'value', 'label', 'title') \
                    and node.get('type') != 'badge':
                found.append(value)


def _same(one, other) -> bool:
    return ' '.join(str(one or '').split()) == ' '.join(str(other or '').split())


def _caveat(slide: dict):
    stated = slide.get('caveat')
    return stated.get('text') if isinstance(stated, dict) else stated


def _shapes(node, found: list[dict], within: tuple = ()) -> None:
    """Each node of a drawing that shows words: its own words, as compared, and the nodes it
    sits inside, by identity. A badge's character is not one of the slide's words."""
    if isinstance(node, list):
        for item in node:
            _shapes(item, found, within)
    elif isinstance(node, dict):
        own = [value for key, value in node.items() if key in TEXTS
               and isinstance(value, str) and node.get('type') != 'badge']
        if own:
            found.append({'said': f" {' '.join(plain(text) for text in own)} ",
                          'within': within, 'self': id(node)})
        for value in node.values():
            if isinstance(value, (dict, list)):
                _shapes(value, found, (*within, id(node)))


def _beside(one: dict, other: dict) -> bool:
    """Whether two shapes are one, or one sits in what holds the other: a label in the box
    or row that holds its text, or the text in the one that holds its label."""
    return one is other or bool(one['within']) and one['within'][-1] in (
        *other['within'], other['self']) or bool(other['within']) and other['within'][-1] in (
        *one['within'], one['self'])


def whole_points(drawing, points: list[dict], notes=None) -> list[str]:
    """What is wrong with how a slide's drawing carries its approved points, a sentence
    each: a point's text is whole in one shape, and its label is whole in that shape or right
    beside it. A point that gives its diagram short `parts` labels has each of them drawn,
    and its text whole once on the slide or in the notes."""
    shapes: list[dict] = []
    _shapes(drawing, shapes)
    joined = ' ' + ' '.join(shape['said'].strip() for shape in shapes) + ' '
    in_notes = f' {plain(notes)} ' if isinstance(notes, str) else ''
    problems = []

    def holding(text: str) -> list[dict]:
        return [shape for shape in shapes if f' {plain(text)} ' in shape['said']]

    for point in points:
        label, text, nodes = point.get('label'), point.get('text'), point.get('parts') or []
        held_text = holding(text) if plain(text) else []
        held_label = holding(label) if plain(label) else []
        for words, held in ((text, held_text), (label, held_label)):
            if not plain(words) or held:
                continue
            if words == text and nodes and f' {plain(text)} ' in in_notes:
                continue    # the diagram draws its short labels; the sentence is in the notes
            if f' {plain(words)} ' in joined:
                problems.append(f'this approved point is split across shapes: '
                                f'{json.dumps(words)}. Keep it whole in one shape, with its '
                                'label in that shape or right beside it.')
            else:
                problems.append(f'these approved words are missing or changed: '
                                f'{json.dumps(words)}')
        if held_text and held_label and not any(_beside(one, other) for one in held_text
                                                for other in held_label):
            problems.append(f'the label {json.dumps(label)} is far from its text: put it in '
                            'the same shape or right beside it.')
        problems += [f'the short label {json.dumps(node)} of a diagram part is missing or '
                     'changed. Draw each of a point\'s `parts` whole, in a shape of its own.'
                     for node in nodes if plain(node) and not holding(node)]
    return problems


def kept(section, spec: dict) -> list[str]:
    """What the runner refuses in a section: anything that was fixed before its composer
    started and is not as it was, and any approved word that is gone."""
    if not isinstance(section, dict):
        return ['A section is one JSON object.']
    problems = []
    if section.get('direction') != spec['direction']:
        problems.append('`direction` is copied unchanged: ' + json.dumps(spec['direction']))
    if section.get('title') != spec['title']:
        problems.append(f"`title` is the deck's title: {json.dumps(spec['title'])}")
    slides = [slide for slide in section.get('slides') or () if isinstance(slide, dict)] \
        if isinstance(section.get('slides'), list) else []
    wanted = [slide['id'] for slide in spec['slides']]
    if [slide.get('id') for slide in slides] != wanted:
        return problems + ['The slides are exactly these, in this order: '
                           + ', '.join(wanted) + '.']
    for mine, theirs in zip(slides, spec['slides']):
        ident = theirs['id']
        if mine.get('title') != theirs['title']:
            problems.append(f"{ident}: the title is fixed: {json.dumps(theirs['title'])}")
        if mine.get('sources') != theirs['sources']:
            problems.append(f"{ident}: `sources` is fixed: {json.dumps(theirs['sources'])}")
        if 'layout' in mine:
            problems.append(f'{ident}: a slide you draw names no template layout.')
        texts, ids = [], []
        _drawn([mine.get('canvas'), mine.get('connect')], texts, ids)
        wrong = [found for found in ids if not found.startswith(spec['prefix'])]
        if wrong:
            problems.append(f"{ident}: every node and edge ID starts with {spec['prefix']}. "
                            'These do not: ' + ', '.join(wrong[:8]) + '.')
        problems += [f'{ident}: {problem}' for problem in whole_points(
            [mine.get('canvas'), mine.get('connect')], theirs['points'], theirs.get('notes'))]
        for name, got in (('caveat', _caveat(mine)), ('source', mine.get('source')),
                          ('notes', mine.get('notes')),
                          *((('provenance', mine.get('provenance')),)
                            if 'provenance' in theirs or 'provenance' in mine else ())):
            approved = theirs.get(name)
            if not _same(got, approved):
                problems.append(f'{ident}: `{name}` stays exactly as it was approved'
                                + (f': {json.dumps(approved)}' if approved
                                   and name != 'notes' else '.' if approved
                                   else ': the slide has none.'))
        if 'intent' not in theirs:
            continue
        if mine.get('intent') != json.loads(theirs['intent']):
            problems.append(f'{ident}: `intent` is copied exactly as it was approved. Your '
                            'brief gives it under the approved design.')
        shown = ' '.join(plain(text) for text in (*texts, _caveat(mine), mine.get('source'))
                         if isinstance(text, str))
        problems += [f'{ident}: the approved design keeps this wording, which is missing or '
                     f'changed: {json.dumps(kept)}' for kept in theirs['qualifications']
                     if plain(kept) and plain(kept) not in shown]
    return problems


def as_approved(section, spec: dict):
    """A section whose intents are written exactly as they were approved: each one that is
    the approved intent is given its keys in the approved order, which the slides tool
    compares as written. Anything else is left as it is, to be refused."""
    wanted = {slide['id']: json.loads(slide['intent']) for slide in spec['slides']
              if 'intent' in slide}
    if not wanted or not isinstance(section, dict) or not isinstance(section.get('slides'),
                                                                     list):
        return section
    return {**section, 'slides': [
        {**slide, 'intent': wanted[slide['id']]} if isinstance(slide, dict)
        and slide.get('id') in wanted and slide.get('intent') == wanted[slide['id']] else slide
        for slide in section['slides']]}


# --- what a review finds -----------------------------------------------------------------

def checked(finding, slides: list[dict]) -> tuple[dict | None, str | None]:
    """One finding of a review as it is kept, or why it cannot be. `slides` are the
    slides that were looked at, each with its `id` and `number`."""
    if not isinstance(finding, dict):
        return None, 'A finding is an object with slide, question, severity and note.'
    numbers = {slide['id']: slide['number'] for slide in slides}
    ident, question = finding.get('slide'), finding.get('question')
    if ident not in numbers:
        return None, f'{ident!r} is not a slide of this deck. Name a slide by its ID.'
    if type(question) is not int or not 1 <= question <= len(QUESTIONS):
        return None, f'{ident}: `question` is a number from 1 to {len(QUESTIONS)}.'
    if finding.get('severity') not in SEVERITIES:
        return None, f'{ident}: `severity` is one of: ' + ', '.join(SEVERITIES) + '.'
    note = finding.get('note')
    if not isinstance(note, str) or len(note.strip()) < NOTE:
        return None, f'{ident}: `note` is one sentence on what is wrong on the slide.'
    if finding.get('about', ABOUT[0]) not in ABOUT:
        return None, f'{ident}: `about` is one of: ' + ', '.join(ABOUT) + '.'
    fix = finding.get('fix')
    return {'slide': ident, 'number': numbers[ident], 'question': question,
            'severity': finding['severity'], 'about': finding.get('about', ABOUT[0]),
            'note': note.strip(),
            'fix': fix.strip() if isinstance(fix, str) and fix.strip() else None}, None


def ordered(findings) -> list[dict]:
    """Findings as a person reads them: the gravest first, then in slide order."""
    return sorted(findings or (), key=lambda finding: (
        SEVERITIES.index(finding['severity']), finding['number']))


def grave(findings) -> list[dict]:
    """The findings that keep a deck from being called clear."""
    return [finding for finding in ordered(findings) if finding['severity'] in GRAVE]


def to_repair(findings, sections: list[dict]) -> list[str]:
    """The sections a review sends back to their composers: each with a major or critical
    finding about how one of its slides is drawn."""
    drawn = {finding['slide'] for finding in grave(findings) if finding['about'] == ABOUT[0]}
    return [section['id'] for section in sections if drawn & set(section['slides'])]


def remains(findings) -> str:
    """What a review still finds, counted, in a sentence. A deck is never called clear
    while a major finding remains."""
    left = grave(findings)
    if not left:
        small = len(findings or ())
        return ('The review found nothing major' + (f', and {small} small thing'
                f'{"" if small == 1 else "s"} worth a look.' if small else '.'))
    critical = sum(finding['severity'] == 'critical' for finding in left)
    major = len(left) - critical
    parts = [f'{critical} critical'] if critical else []
    parts += [f'{major} major'] if major else []
    return ('This deck is not clear: the review still finds ' + ' and '.join(parts)
            + f" thing{'' if len(left) == 1 else 's'} wrong.")


def screened(slides: list[dict], repair=None, audit=None) -> list[dict]:
    """What the slides tool's screens and the brand's audit found on each slide of a whole
    deck, before anyone reviews it: {'slide', 'number', 'codes': {code: count},
    'blocking'}, a slide with nothing found left out. `slides` are the round's, with the
    findings each preview gave; `repair` is the tool's own grouping of them, when it gives
    one; `audit` the brand's, whose warnings name a slide by its number."""
    by_number = {slide['number']: slide for slide in slides}
    found: dict = {}

    def add(slide, code, blocking=False, many=1) -> None:
        if not slide or not code:
            return
        entry = found.setdefault(slide['id'], {'slide': slide['id'], 'number': slide['number'],
                                               'codes': {}, 'blocking': False})
        entry['codes'][str(code)] = entry['codes'].get(str(code), 0) + many
        entry['blocking'] = entry['blocking'] or blocking

    clusters = (repair or {}).get('slides') if isinstance(repair, dict) else None
    if isinstance(clusters, list):
        ids = {slide['id']: slide for slide in slides}
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            for code, many in (cluster.get('codes') or {}).items():
                add(ids.get(cluster.get('slide')), code, bool(cluster.get('blocking')),
                    many if isinstance(many, int) else 1)
    else:
        for slide in slides:
            for finding in slide.get('findings') or ():
                if finding.get('severity') in ('warn', 'error'):
                    add(slide, finding.get('code'), finding.get('severity') == 'error')
    for warning in (audit or {}).get('warnings') or ():
        if isinstance(warning, dict):
            add(by_number.get(warning.get('slide')), warning.get('code'))
    return sorted(found.values(), key=lambda entry: entry['number'])


def sent_back(screens: list[dict]) -> list[dict]:
    """The slides the screens send back to be drawn again before a review, as findings
    about how each is drawn: one that blocks delivery, one with a sentence split across
    shapes, and one where text overlaps text again and again."""
    made = []
    for entry in screens:
        codes = entry['codes']
        split = any('split' in code.lower() for code in codes)
        overlaps = sum(many for code, many in codes.items() if 'overlap' in code.lower())
        if not (entry['blocking'] or split or overlaps >= CLUSTER):
            continue
        why = (['a sentence of an approved point is split across shapes'] if split else []) \
            + ([f'text overlaps text {overlaps} times'] if overlaps >= CLUSTER else []) \
            + (['the slides tool found what blocks delivery'] if entry['blocking'] else [])
        made.append({'slide': entry['slide'], 'number': entry['number'], 'severity': 'major',
                     'about': ABOUT[0], 'criterion': 'screen', 'category': 'fit-defect',
                     'note': 'Before any review, the screens found that ' + '; '.join(why)
                             + ' (' + ', '.join(f'{code} ×{many}' for code, many in
                                                 sorted(codes.items())) + ').',
                     'fix': 'Keep each point whole in one shape, give every text room of its '
                            'own, and look at the slide again before handing it in.',
                     'by': 'screen'})
    return made


def told(findings, slides: list[dict]) -> str:
    """What a review found on some slides, as their composer is told it."""
    lines = ['# What the review found in your section', '',
             'Someone who drew none of these slides looked at each one as it was rendered '
             'and answered the same questions about it. Each "no" is below.', '']
    for slide in slides:
        mine = [finding for finding in ordered(findings) if finding['slide'] == slide['id']]
        if not mine:
            continue
        lines += [f"## Slide {slide['number']}: `{slide['id']}`, \"{slide['title']}\"", '']
        for finding in mine:
            what = ('This is about what the slide says, which is not yours to change: '
                    'leave the words as they are. ' if finding['about'] == ABOUT[1] else
                    'This would need another visual concept than the one approved, which is '
                    'not yours to change: draw within the approved design. '
                    if finding['about'] == JUDGED[2] else '')
            asked_as = (f"{CATEGORIES.get(finding.get('category'), 'Found')}, "
                        f"`{finding['criterion']}`:" if 'criterion' in finding else
                        f"\"{QUESTIONS[finding['question'] - 1]}\"")
            lines.append(f"- **{finding['severity']}**, {asked_as} {what}{finding['note']}"
                         + (f" Suggested: {finding['fix']}" if finding['fix'] else ''))
        lines.append('')
    return '\n'.join(lines)


def _looked(screens) -> list[str]:
    """What a reviewer is told to look for beyond the questions, and what the screens and
    the brand's audit already found, slide by slide."""
    lines = ['', '## Look for these too', '',
             'Answer them inside the questions or criteria you are given: a wireframe look '
             'or visible bookkeeping is at least `major`, a split sentence or text on text '
             'is `major` and about `drawing`.', '']
    lines += [f'- {question}' for question in LOOKS_UNFINISHED]
    if screens:
        lines += ['', 'The screens and the brand\'s audit found these. Each is a prompt to '
                  'look, not a verdict:', '']
        lines += [f"- Slide {entry['number']}, `{entry['slide']}`: " + ', '.join(
            f'{code} ×{many}' for code, many in sorted(entry['codes'].items()))
            for entry in screens]
    return lines


def asked(objectives: dict, slides: list[dict], earlier=None, screens=None) -> str:
    """What a reviewer is asked: the questions, how grave a "no" is, the slides, the
    objectives, what to look for beyond the questions with what the screens found, and on
    a later round what was found before."""
    lines = ['# The review', '', '## The questions, asked of every slide', '']
    lines += [f'{number}. {question}' for number, question in enumerate(QUESTIONS, start=1)]
    lines += ['', '## How grave a "no" is', '',
              '- `critical`: the slide misleads, cannot be read, or its point cannot be '
              'found.',
              '- `major`: the slide works but is clearly weaker than it should be.',
              '- `minor`: a small flaw.', '', '## The slides', '']
    lines += [f"- {slide['number']}. `{slide['id']}`: \"{slide['title']}\"" for slide in slides]
    lines += ['', '## The objectives', '']
    lines += [f'- {ident}: {text}' for ident, text in objectives.items()]
    lines += _looked(screens)
    if earlier:
        lines += ['', '## What an earlier review found', '',
                  'These slides were drawn again since. Look for each of these, and where '
                  'one is not put right, record it again.', '']
        lines += [f"- Slide `{finding['slide']}`, {finding['severity']}, {_named(finding)}: "
                  f"{finding['note']}" for finding in ordered(earlier)]
    return '\n'.join(lines) + '\n'


def _named(finding: dict) -> str:
    """Which question or criterion a finding answered, as an earlier review is listed."""
    return f"`{finding['criterion']}`" if 'criterion' in finding \
        else f"question {finding['question']}"


def to_outline(findings) -> list[dict]:
    """The grave findings of a review against the design that drawing again cannot put
    right: those about what a slide says, or about the visual concept it was approved with."""
    return [finding for finding in grave(findings) if finding['about'] in JUDGED[1:]]


# --- a review against the approved design ------------------------------------------------

def judging(objectives: dict, slides: list[dict], packets: list[dict], earlier=None,
            screens=None) -> str:
    """What a reviewer is asked of a deck reviewed against its approved design: the slides
    tool's criteria, how grave a "no" is and what it can be about, each slide with what the
    tool gives of it, the objectives, and on a later round what was found before. `packets`
    are what `review --slide` gave, in slide order."""
    asked = {criterion['id']: criterion['question'] for packet in packets
             for criterion in packet['slide']['criteria']}
    lines = ['# The review', '', 'The slides tool rendered this deck and prepared its review '
             'against the design the person approved. Answer every criterion it lists for a '
             'slide, from what you see on that slide.', '', '## The criteria', '']
    lines += [f'- `{ident}`: {question}' for ident, question in asked.items()]
    lines += ['', '## How grave a "no" is', '',
              '- `critical`: the slide misleads, cannot be read, or its point cannot be found.',
              '- `major`: the slide works but is clearly weaker than it should be.',
              '- `minor`: a small flaw.', '', '## What a "no" is about', '',
              '- `drawing`: drawing the slide again puts it right, keeping the visual concept '
              'and the words that were approved.',
              '- `content`: only a change to what the slide says, its words or its facts, puts '
              'it right.',
              '- `concept`: the approved visual concept itself does not teach the claim, and '
              'only another one would.', '', '## The slides']
    numbers = {slide['id']: slide['number'] for slide in slides}
    for packet in packets:
        prompt = packet['slide']
        intent = prompt.get('intent') or {}
        lines += ['', f"### Slide {numbers.get(prompt['slide'], '?')}, `{prompt['slide']}`: "
                      f"\"{prompt.get('title')}\"", '',
                  f"- Treatment: {prompt.get('treatment')}"
                  + (', direct text by decision: no picture is wanted'
                     if prompt.get('treatment') == 'direct-text' else ''),
                  f"- Claim: {intent.get('takeaway')}",
                  f"- Relationship: {intent.get('relationship')}",
                  f"- Approved composition: {prompt.get('approvedComposition')}",
                  '- Criteria: ' + ', '.join(f"`{criterion['id']}`"
                                             for criterion in prompt['criteria'])]
        texts = {entry['object']: entry['text'] for entry in prompt.get('expectedText') or ()}
        lines.append('- Objects you may cite: ' + '; '.join(
            f'`{ident}`' + (f' {_json(texts[ident])}' if ident in texts else '')
            for ident in prompt['objects']))
        if prompt.get('proseCards'):
            lines.append('- Prose cards, of which `teaching-treatment` cites at least one: '
                         + ', '.join(f'`{ident}`' for ident in prompt['proseCards']))
        lines += [f"- The slides tool points at this ({found.get('category')}, "
                  f"{found['code']}, {found['severity']}): {found['detail']}"
                  for found in packet.get('findings') or ()]
    lines += ['', '## The objectives', '']
    lines += [f'- {ident}: {text}' for ident, text in objectives.items()]
    lines += _looked(screens)
    if earlier:
        lines += ['', '## What an earlier review found', '',
                  'These slides were drawn again since. Look for each of these, and where '
                  'one is not put right, answer its criterion so again.', '']
        lines += [f"- Slide `{finding['slide']}`, {finding['severity']}, {_named(finding)}: "
                  f"{finding['note']}" for finding in ordered(earlier)]
    return '\n'.join(lines) + '\n'


def judged(given, packets: list[dict]) -> tuple[list[dict], list[str]]:
    """A reviewer's answer to a review against the design, as it is kept, and what is wrong
    with it: one entry for every slide, by its ID, answering each of its criteria once, with
    a judgement, a reason and the objects it cites; and for each that is not a pass, how
    grave it is and what it is about. Whether the answer is right is the slides tool's to
    check, and the person's to judge."""
    if not isinstance(given, list) or not all(isinstance(entry, dict) for entry in given):
        return [], ['`slides` is a list: one entry for each slide, `{"slide", "checks"}`.']
    wanted = [packet['slide']['slide'] for packet in packets]
    if [entry.get('slide') for entry in given] != wanted:
        return [], ['Answer every slide once, in order, by its ID: ' + ', '.join(wanted) + '.']
    kept, problems = [], []
    for entry, packet in zip(given, packets):
        prompt, ident = packet['slide'], entry['slide']
        criteria = [criterion['id'] for criterion in prompt['criteria']]
        checks = entry.get('checks')
        if not isinstance(checks, list) or sorted(
                str(check.get('criterion')) if isinstance(check, dict) else ''
                for check in checks) != sorted(criteria):
            problems.append(f'{ident}: answer each of these criteria once: '
                            + ', '.join(criteria) + '.')
            continue
        mine = []
        for check in sorted(checks, key=lambda check: criteria.index(check['criterion'])):
            where, status = f"{ident}, `{check['criterion']}`", check.get('status')
            objects, reason = check.get('objects'), check.get('reason')
            if status not in STATUSES:
                problems.append(f'{where}: `status` is one of: ' + ', '.join(STATUSES) + '.')
            if not isinstance(reason, str) or len(reason.strip()) < NOTE:
                problems.append(f'{where}: `reason` says, for this slide, why.')
            if not isinstance(objects, list) or not objects \
                    or any(name not in prompt['objects'] for name in objects):
                problems.append(f"{where}: `objects` names what you judged, from this slide's "
                                'objects: ' + ', '.join(prompt['objects']) + '.')
            made = {'criterion': check['criterion'], 'status': status,
                    'reason': reason.strip() if isinstance(reason, str) else reason,
                    'objects': objects}
            if status in STATUSES[1:]:
                fix = check.get('fix')
                if check.get('severity') not in SEVERITIES:
                    problems.append(f'{where}: `severity` is one of: '
                                    + ', '.join(SEVERITIES) + '.')
                if check.get('about') not in JUDGED:
                    problems.append(f'{where}: `about` is one of: ' + ', '.join(JUDGED) + '.')
                made.update(severity=check.get('severity'), about=check.get('about'),
                            fix=fix.strip() if isinstance(fix, str) and fix.strip() else None)
            mine.append(made)
        kept.append({'slide': ident, 'checks': mine})
    return kept, problems


def assessment(kept: list[dict], packets: list[dict], binding: dict,
               sources: bool = True) -> dict:
    """A reviewer's answer as the slides tool takes an assessment: bound to the review it
    answers, each judgement with the sources the slide keeps. Without `sources`, for a
    tool that takes each slide's own, they are left out."""
    kept_by = {packet['slide']['slide']: packet['slide']['sources'] for packet in packets}
    return {**binding, 'slides': [
        {'id': entry['slide'], 'checks': [
            {**{key: check[key] for key in ('criterion', 'status', 'reason', 'objects')},
             **({'sources': list(kept_by[entry['slide']])} if sources else {})}
            for check in entry['checks']]}
        for entry in kept]}


def found(unresolved, kept: list[dict], slides: list[dict]) -> list[dict]:
    """What the slides tool left unresolved, as findings: each judgement that was not a
    pass, with how grave the reviewer said it is and what it is about, and each failure the
    build itself showed, such as an approved asset that is not there, which is critical and
    about drawing."""
    numbers = {slide['id']: slide['number'] for slide in slides}
    judged_as = {(entry['slide'], check['criterion'], check['reason']): check
                 for entry in kept for check in entry['checks'] if check['status'] != 'pass'}
    made = []
    for entry in unresolved or ():
        mine = judged_as.get((entry.get('slide'), entry.get('criterion'), entry.get('detail')))
        made.append({'slide': entry.get('slide'), 'number': numbers.get(entry.get('slide')),
                     'criterion': entry.get('criterion'), 'category': entry.get('category'),
                     'severity': mine['severity'] if mine else SEVERITIES[0],
                     'about': mine['about'] if mine else ABOUT[0],
                     'note': str(entry.get('detail') or '').strip(),
                     'fix': mine['fix'] if mine else None})
    return [finding for finding in made if finding['number'] is not None]


def link(made: dict, title: str, rendered: str) -> str:
    """deck-link.md for a deck kept in Google Slides. It names the rendered deck it was
    made from, so that an approval of this file is an approval of those slides."""
    return (f"# Slide deck: {title}\n\n- URL: {made.get('url')}\n"
            f"- Title: {made.get('name') or title}\n- ID: {made.get('id')}\n"
            f'- Made from the rendered deck with the SHA-256 {rendered}\n')
