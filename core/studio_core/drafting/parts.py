"""An item's parts: a Markdown draft as a title, an opening and sections, and back.

A draft record holds `title`, `opening` and `sections`, each section `{id, heading, brief,
text}` (with `level` and `mark` when its heading was written another way), plus `revision`
and `changed`. `split` and `join` are Blog Studio's Markdown reading, unchanged; `Codec`
names the parts an item has, so a deck can later make each slide a part.
"""

import re
import secrets
import textwrap

FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
TITLE = re.compile(r'# (?!#)(.*\S)\s*')
# A heading that may start a section: up to three spaces, ## to ######, then spaces or a tab,
# then its words. Four spaces in is indented code.
SECTION = re.compile(r' {0,3}(#{2,6})[ \t]+(?![# \t])(.*\S)\s*')
ANY_HEADING = re.compile(r'(#{1,6})\s+(.*?\S)\s*#*\s*')
ITEM = re.compile(r'(?:[-*+]|\d{1,3}[.)])\s+(\S.*)')
SECTIONS = 60  # sections in one outline or draft
TOO_MANY = 'Keep the draft to 60 sections.'
BRIEF = 4000  # characters in one section's brief
LIMIT = 200_000  # characters in one part
PART = re.compile(r'[a-f0-9]{8}')


def new_id(taken):
    while True:
        value = secrets.token_hex(4)
        if value not in taken:
            taken.add(value)
            return value


def tidy(lines):
    """Lines as one text without blank lines around it; a first line keeps its indent."""
    return re.sub(r'^(?:[ \t]*\n)+', '', '\n'.join(lines)).rstrip()


def free(lines):
    """Each line with whether it is outside fenced code; a fence line itself is not."""
    fence = None
    for line in lines:
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
            yield line, False
            continue
        yield line, fence is None


def divide(lines):
    """The opening and the sections of a draft's body, as lines.

    The section level is the shallowest heading level from ## to ###### used outside fenced
    code: each heading at that level starts a section, and deeper ones stay inside it. A
    Google Doc's export often uses ### headings, in bold; a draft that mixes ## and ### is
    divided at ##. The heading keeps its words as written, bold marks included, and a
    section split at a level other than ## records it (`level`), as one whose marks are
    indented or followed by a tab keeps them (`mark`), so `join` writes it back."""
    found = [SECTION.fullmatch(line) if outside else None for line, outside in free(lines)]
    levels = [len(match.group(1)) for match in found if match]
    depth = min(levels) if levels else None
    opening, sections, current, taken = [], [], None, set()
    for match, line in zip(found, lines, strict=True):
        if match and len(match.group(1)) == depth:
            current = {'id': new_id(taken), 'heading': match.group(2).strip(), 'brief': ''}
            if depth != 2:
                current['level'] = depth
            if line[: match.start(2)] != '#' * depth + ' ':
                current['mark'] = line[: match.start(2)]  # Indented, or a tab: kept as written.
            current['lines'] = []
            sections.append(current)
        else:
            (current['lines'] if current else opening).append(line)
    for section in sections:
        section['text'] = tidy(section.pop('lines'))
    return tidy(opening), sections



def split(markdown, title='', take=None):
    """Title, opening and sections of a Markdown draft.

    The first line is the title when it is a `# ` heading; a `# ` line further down is text.
    Sections start at the shallowest heading level from ## to ###### used below the title
    (`divide`); text before the first one is the opening. A bold line is not a heading,
    and a heading inside a fenced code block is text. `take(body) -> (body, images)` lets a
    studio take something out of the body first, such as image data, kept as `images`.
    """
    lines = markdown.replace('\r\n', '\n').strip('\n').split('\n')
    found = TITLE.fullmatch(lines[0]) if lines else None
    if found:
        title, lines = found.group(1), lines[1:]
    body, images = '\n'.join(lines), None
    if take is not None:
        body, images = take(body)
    opening, sections = divide(body.strip('\n').split('\n'))
    draft = {'title': title.strip(), 'opening': opening, 'sections': sections}
    if take is not None:
        draft['images'] = images
    return draft


def level(draft):
    """The heading level a draft's sections start at: ## unless it was split deeper."""
    for section in draft.get('sections') or []:
        if section.get('level') in range(3, 7):
            return section['level']
    return 2


def limit(draft):
    """The deepest heading a part may not hold: one at the section level or above would
    start a section the next time the draft is read, and in a draft with no sections, any
    heading from ## to ###### would. A record kept before the desk read headings below ##,
    whose opening still holds them (a job was under way when it was read, or it has more
    headings than a draft has sections), keeps the old rule: ## only."""
    if draft.get('sections'):
        return level(draft)
    return 2 if has_heading(draft.get('opening') or '', 6) else 6


def heading_in(text, level=2):
    """The marks of the first heading from ## down to `level` a part's text holds outside
    code, such as '###', or ''. Such a heading would start a new section the next time the
    draft is read."""
    for line, outside in free(text.replace('\r\n', '\n').split('\n')):
        match = SECTION.fullmatch(line) if outside else None
        if match and len(match.group(1)) <= level:
            return match.group(1)
    return ''


def has_heading(text, level=2):
    """Whether a part's text holds a heading from ## down to `level` outside code."""
    return bool(heading_in(text, level))


def heading_problem(deepest):
    """What to say when a part holds a heading that would start a section."""
    if deepest >= 6:
        return 'A heading would start a new section. Add sections on the Outline tab.'
    mark = '#' * deepest
    return (
        'A ' + mark + ' heading would start a new section. Use ' + mark + '# for a heading '
        'inside this part.'
    )


def added_problem(mark):
    """What to say when a rewrite came back with a heading that would start a section."""
    return 'The rewrite added a ' + mark + ' section heading, so it was not applied. Run it again.'


def outline_from(text):
    """The outline a person pasted, as a title, an opening brief and sections with briefs,
    or None when it is notes without structure.

    Headings outside code (at the shallowest level used) start sections; without headings,
    top-level list items do, and the lines indented under each are its brief. Text before
    the first section is the opening brief. Fewer than two sections is not an outline."""
    lines = (text or '').replace('\r\n', '\n').strip('\n').split('\n')
    title = ''
    found = TITLE.fullmatch(lines[0]) if lines and lines[0] else None
    if found:
        title, lines = found.group(1), lines[1:]
    headings, items, fence = [], [], None
    for at, line in enumerate(lines):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1).startswith(fence[0] * len(fence)):
                fence = None
            continue
        if fence is not None:
            continue
        heading = ANY_HEADING.fullmatch(line)
        if heading:
            headings.append((at, len(heading.group(1)), heading.group(2)))
        elif ITEM.fullmatch(line) and not line[:1].isspace():
            items.append((at, ITEM.fullmatch(line).group(1)))
    if headings:
        top = min(depth for _, depth, _ in headings)
        cuts = [(at, words) for at, depth, words in headings if depth == top]
    else:
        cuts = items
    if not 2 <= len(cuts) <= SECTIONS:
        return None
    sections, taken = [], set()
    for number, (at, words) in enumerate(cuts):
        end = cuts[number + 1][0] if number + 1 < len(cuts) else len(lines)
        body = '\n'.join(lines[at + 1 : end])
        words = words.strip()
        if not headings:
            body = textwrap.dedent(body)
            lead, colon, rest = words.partition(': ')
            if colon and len(lead) <= 100:
                words, body = lead, rest + ('\n' + body if body.strip() else '')
        heading = ' '.join(words.rstrip(':').split())[:200] or 'Section ' + str(number + 1)
        sections.append(
            {
                'id': new_id(taken),
                'heading': heading,
                'brief': tidy(body.split('\n'))[:BRIEF],
                'text': '',
            }
        )
    return {
        'title': title.strip()[:500],
        'opening_brief': tidy(lines[: cuts[0][0]])[:BRIEF],
        'sections': sections,
    }


def title_line(text):
    """The `# ` title on the first line of a pasted outline or notes, or ''."""
    first = (text or '').replace('\r\n', '\n').strip('\n').split('\n')[0]
    found = TITLE.fullmatch(first)
    return found.group(1).strip()[:500] if found else ''


def join(draft, after=()):
    """The Markdown the parts make, then each block in `after` (a studio's own, such as the
    definitions of the images the text refers to) at the end."""
    parts = []
    if draft.get('title'):
        parts.append('# ' + draft['title'])
    if draft.get('opening'):
        parts.append(draft['opening'])
    mark = '#' * level(draft) + ' '
    for section in draft['sections']:
        written = section.get('mark') or mark
        if written.strip() != mark.strip():
            written = mark  # Marks kept from another level are not this draft's.
        parts.append(
            written + section['heading'] + ('\n\n' + section['text'] if section['text'] else '')
        )
    return '\n\n'.join(parts + list(after)) + '\n'


def _identity(draft, *rest):
    return rest[0] if rest else draft


class Codec:
    """The parts an item has and how its text is read.

    - `fixed`: the parts every item has, by name (`('title', 'opening')` for Markdown);
      every other part is a section whose id matches `part`;
    - `single`: the parts that are one line (the title);
    - `thing` and `noun`: the words sentences use ("Choose a part of this draft.",
      "Keep the outline to 60 sections.");
    - `split` and `join`: the item's text as parts and back;
    - `deepest(draft)`: the deepest heading level a part of this draft may not hold;
      `heading_in(text, deepest)`: the marks of such a heading in `text`, or '';
      `break_message(deepest)` and `added_message(mark)`: what to say about one;
    - a studio's own hooks, all optional: `vet(part, text)` refuses text for the studio's
      own reasons; `taken(draft, part, text, previous) -> (text, draft)` takes something
      the text carries apart (Blog Studio: pasted image data), `fitted(draft, before)`
      checks the draft against the record it came from, `landed(draft, before, text)` is a
      job's result as it lands, and `shown(text)` a kept version as the page shows it.
    """

    def __init__(
        self,
        *,
        fixed=('title', 'opening'),
        single=('title',),
        part=PART,
        thing='draft',
        noun='section',
        split=split,
        join=join,
        deepest=limit,
        heading_in=heading_in,
        break_message=heading_problem,
        added_message=added_problem,
        vet=None,
        taken=None,
        fitted=None,
        landed=None,
        shown=None,
    ):
        self.fixed, self.single, self.part = tuple(fixed), tuple(single), part
        self.thing, self.noun = thing, noun
        self.split, self.join, self.deepest = split, join, deepest
        self.heading_in, self.break_message, self.added_message = (
            heading_in,
            break_message,
            added_message,
        )
        self.vet = vet
        self.taken = taken
        self.fitted = fitted or _identity
        self.landed = landed or (lambda draft, before, text: text)
        self.shown = shown or (lambda text: text)

    def replace(self, **changes):
        """This codec with some of its names or hooks changed."""
        names = (
            'fixed', 'single', 'part', 'thing', 'noun', 'split', 'join', 'deepest',
            'heading_in', 'break_message', 'added_message', 'vet', 'taken', 'fitted',
            'landed', 'shown',
        )
        kept = {name: getattr(self, name) for name in names}
        return Codec(**{**kept, **changes})

    def known(self, part):
        """Whether `part` could name a part of an item: a fixed one or a section id."""
        return isinstance(part, str) and (part in self.fixed or bool(self.part.fullmatch(part)))

    def breaks(self, text, deepest=2):
        """Whether `text` holds a heading that would start a new part."""
        return bool(self.heading_in(text, deepest))

    def section(self, draft, part):
        """The section a part names, or None for a fixed part."""
        if part in self.fixed:
            return None
        for section in draft['sections']:
            if section['id'] == part:
                return section
        raise ValueError('Choose a part of this ' + self.thing + '.')

    def text_of(self, draft, part):
        section = self.section(draft, part)
        return draft[part] if section is None else section['text']

    def set_text(self, draft, part, text):
        section = self.section(draft, part)
        if section is None:
            draft[part] = text.strip()
        else:
            section['text'] = text.strip()


MARKDOWN = Codec()
