#!/usr/bin/env python3
"""Rebuild the studio workflow diagrams with Python's standard library.

Run from any directory: python3 scripts/workflow_diagrams.py [--check]
Each diagram is drawn from what its studio does now. Box titles are the studio's own
button and screen names, or say plainly what a step does; every subtitle is short.
"""
import argparse
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The shared identity tokens from ui-kit/style.css: (colour, wash) in light, then dark.
STUDIOS = {
    'blog': ('Blog Studio', ('#175fba', '#e8f1ff'), ('#9cc4ff', '#213653')),
    'presentation': ('Presentation Studio', ('#ac421d', '#fff0e8'), ('#ffb493', '#452c24')),
    'training': ('Training Studio', ('#7140b4', '#f2eaff'), ('#d2b1ff', '#342947')),
    'infographic': ('Infographic Studio', ('#146970', '#e5f4f3'), ('#8cdedb', '#1c383b')),
}
ROLES = (('you', 'You decide or give input'), ('assistant', 'Assistant work'),
         ('studio', 'Studio step'))

# Layout, in SVG units. No text is smaller than 12.
PAD, MAIN, SIDE, GAP, ROW_GAP = 20, 236, 156, 36, 40
TITLE, SUB, SMALL = 15, 13, 12
TITLE_LINE, SUB_LINE = 19, 17
CORNER = 8

# Advance widths per 1000 units of Helvetica, regular then bold, used to wrap text
# conservatively for the system fonts the diagrams name.
_REGULAR = dict(zip(
    ' abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,.&’\'-():;?/·',
    (278, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556,
     556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 667, 667, 722, 722, 667, 611, 778,
     722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
     667, 611) + (556,) * 10 + (278, 278, 667, 222, 191, 333, 333, 333, 278, 278, 556, 278,
                                278)))
_BOLD = dict(zip(
    ' abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,.&’\'-():;?/·',
    (278, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611,
     611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 722, 722, 722, 722, 667, 611, 778,
     722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
     667, 611) + (556,) * 10 + (278, 278, 722, 278, 238, 333, 333, 333, 333, 333, 611, 278,
                                278)))


def width(value, size, bold=False):
    table = _BOLD if bold else _REGULAR
    return sum(table.get(ch, 667) for ch in value) * size / 1000 * 1.03


def greedy(value, size, room, bold):
    lines, line = [], ''
    for word in value.split():
        trial = f'{line} {word}'.strip()
        if line and width(trial, size, bold) > room:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def wrap(value, size, room, bold=False):
    """Lines no wider than `room`, as even as the same number of lines allows."""
    lines = greedy(value, size, room, bold)
    for line in lines:
        if width(line, size, bold) > room:
            raise ValueError(f'"{line}" does not fit in {room} units')
    narrow = room
    while narrow > 20 and len(greedy(value, size, narrow - 1, bold)) == len(lines):
        narrow -= 1
    return greedy(value, size, narrow, bold)


# --- The diagrams -----------------------------------------------------------------
# A node is (id, column, row, role, title, subtitle): column 0 is the main flow, -1 and
# 1 the branches beside it. An edge is (from, to, how, label). How is "down" (straight,
# one column), "side" (along one row), "both" (there and back along one row), "back"
# (vertical, then into the target's side) or "over" (along the row, then into the
# target's top). A label belongs to a "down" edge and sits beside it.

def flow(steps, extra=(), edges=()):
    """The main column from `steps` as (id, role, title, subtitle[, label to next])."""
    nodes, links = [], []
    for row, step in enumerate(steps):
        nodes.append((step[0], 0, row, *step[1:4]))
        if row:
            before = steps[row - 1]
            links.append((before[0], step[0], 'down', before[4] if len(before) > 4 else ''))
    return nodes + list(extra), links + list(edges)


TRAINING_PLAN = flow(
    (('open', 'studio', 'Open Training Studio', 'Shared setup the first time'),
     ('new', 'you', 'New training', 'Goal, materials, sources'),
     ('research', 'assistant', 'Research', 'Harness Research, independent check'),
     ('plan', 'assistant', 'Teaching plan', 'Topics, order, depth, timing'),
     ('check', 'you', 'Check the topics', 'What this training will cover'),
     ('build', 'you', 'Build the training', 'Makes the selected materials')),
    (('changes', 1, 4, 'you', 'Ask for changes', 'Research is kept'),),
    (('check', 'changes', 'side', ''), ('changes', 'plan', 'back', '')))

TRAINING_BUILD = flow(
    (('make', 'assistant', 'Build the materials', 'Guide, brief, practice, Yoodli'),
     ('text', 'you', 'Review slide text', 'When a deck is chosen',
      'Approve text & design deck'),
     ('design', 'assistant', 'Design the deck', 'Harness Slides, in your brand'),
     ('desk', 'you', 'Refine on the desk', 'Edit, notes, Finishing'),
     ('ready', 'you', 'Mark ready', 'Each material or a level'),
     ('index', 'studio', 'Index written', 'Once every material is ready'),
     ('share', 'you', 'Share it, if you choose', 'Download, Google Doc, Publish')),
    (('rewrite', 1, 1, 'you', 'Ask for changes', 'Slide text rewritten'),
     ('held', 1, 3, 'you', 'Needs updating', 'Update or Keep as it is'),
     ('draft', -1, 4, 'you', 'Return to draft', 'After an edit or Undo')),
    (('text', 'rewrite', 'both', ''), ('desk', 'held', 'both', ''),
     ('ready', 'draft', 'side', ''), ('draft', 'desk', 'back', '')))

BLOG_WRITE = flow(
    (('open', 'studio', 'Open Blog Studio', 'Shared setup the first time'),
     ('new', 'you', 'New blog', 'Idea and sources'),
     ('prefs', 'you', 'Writing preferences', 'Length, tone, GEO review'),
     ('write', 'assistant', 'Research, outline, draft', 'Nothing needed from you'),
     ('geo', 'assistant', 'GEO review', 'Only if you included it'),
     ('desk', 'you', 'The desk', 'Read, Edit section, Full desk')),
    (('polish', 1, 1, 'you', 'Edit or polish a draft', 'Paste, upload, Doc or link'),
     ('first', 1, 2, 'you', 'What should happen first', 'Choose the first pass'),
     ('pass', 1, 3, 'assistant', 'First pass', 'Spelling, feedback, GEO, reshape')),
    (('open', 'polish', 'over', ''), ('polish', 'first', 'down', ''),
     ('first', 'pass', 'down', ''), ('pass', 'desk', 'back', '')))

BLOG_FINISH = flow(
    (('desk', 'you', 'The desk', 'Edit, notes, select a passage'),
     ('finishing', 'assistant', 'Finishing', 'Copy edit, facts, reader aids'),
     ('decide', 'you', 'Apply, Edit or Skip', 'Each proposal waits for you'),
     ('check', 'studio', 'Pre-publish check', 'Headings, links, evidence'),
     ('geo', 'assistant', 'Run GEO review', 'Says when it is out of date'),
     ('send', 'you', 'Send to Google Doc', 'As suggestions, or copy it'),
     ('published', 'you', 'Mark as published', 'Records where it went')),
    (('revise', 1, 0, 'you', 'Revise the draft', 'A section or the whole'),
     ('bring', -1, 5, 'you', 'Bring accepted changes', 'Back onto the desk')),
    (('desk', 'revise', 'both', ''), ('send', 'bring', 'side', ''),
     ('bring', 'desk', 'back', '')))

BLOG_GEO = flow(
    (('start', 'you', 'Get a GEO report for a published post', 'From Home or New blog'),
     ('link', 'you', 'Link to the published post', 'Then Read the page'),
     ('report', 'assistant', 'Get the GEO report', 'One job; nothing else changes'),
     ('use', 'you', 'Use the report', 'Download, Google Doc or desk')),
    (('again', 1, 3, 'you', 'Run again', 'Says what changed since'),),
    (('use', 'again', 'side', ''), ('again', 'report', 'back', '')))

PRESENTATION_TEXT = flow(
    (('open', 'studio', 'Open Presentation Studio', 'Shared setup the first time'),
     ('new', 'you', 'New deck', 'Idea, document or existing deck'),
     ('research', 'assistant', 'Read and research', 'Research first, if ticked'),
     ('draft', 'assistant', 'Draft the slide text', 'Titles, words, speaker notes'),
     ('text', 'you', 'Review slide text', 'Fix words where they are'),
     ('approve', 'you', 'Approve text & design deck', 'Design starts from this text')),
    (('changes', 1, 4, 'you', 'Ask for changes', 'Slide text redrafted'),),
    (('text', 'changes', 'both', ''),))

PRESENTATION_DECK = flow(
    (('looks', 'studio', 'Draw look samples', 'One slide in each look'),
     ('pick', 'you', 'Pick the look', 'Only if you chose to', 'Draw the deck in this look'),
     ('design', 'assistant', 'Design the deck', 'Harness Slides, in your brand'),
     ('desk', 'you', 'On the desk', 'Words, notes, Finishing'),
     ('deliver', 'you', 'Deliver', 'Google Slides or PowerPoint'),
     ('done', 'studio', 'Delivered', 'Open or download revision N')),
    (('redraw', 1, 3, 'you', 'Redraw slide N', 'Its section is redrawn'),
     ('next', -1, 5, 'you', 'A note or an edit', 'Makes the next revision')),
    (('desk', 'redraw', 'both', ''), ('done', 'next', 'side', ''),
     ('next', 'desk', 'back', '')))

INFOGRAPHIC_STORY = flow(
    (('open', 'studio', 'Open Infographic Studio', 'Shared setup the first time'),
     ('new', 'you', 'New infographic', 'Add information, set direction', 'Save brief'),
     ('find', 'assistant', 'Find the story', 'Source-backed stories proposed'),
     ('choose', 'you', 'Choose the story', 'Use this story'),
     ('build', 'assistant', 'Build page', 'Composed with your brand'),
     ('preview', 'studio', 'Update preview', 'Rendered on this computer')),
    (('revise', 1, 3, 'you', 'Ask for a revision', 'A revised story to choose'),),
    (('choose', 'revise', 'both', ''),))

INFOGRAPHIC_APPROVE = flow(
    (('words', 'you', 'Edit words', 'Each save, a new revision'),
     ('review', 'you', 'Review page', 'Record what you inspected',
      'Record review and run checks'),
     ('checks', 'studio', 'Run checks', 'Checks on this computer'),
     ('approve', 'you', 'Approve revision N', 'This checked revision only'),
     ('files', 'studio', 'Prepare approved files', 'PNG, PDF, SVG and text'),
     ('deliver', 'you', 'Deliver approved page', 'Optional: Google Doc, PDF')),
    (('repair', 1, 2, 'you', 'Repair findings', 'Then Review page again'),
     ('later', -1, 3, 'you', 'A later change', 'Withdraws the approval')),
    (('checks', 'repair', 'side', ''), ('repair', 'review', 'back', ''),
     ('approve', 'later', 'side', ''), ('later', 'words', 'back', '')))

# (studio, file stem, part, parts, heading, diagram)
DIAGRAMS = (
    ('training', 'plan', 1, 2, 'Plan', TRAINING_PLAN),
    ('training', 'build', 2, 2, 'Build and finish', TRAINING_BUILD),
    ('blog', 'write', 1, 3, 'Start and write', BLOG_WRITE),
    ('blog', 'finish', 2, 3, 'Finish and send', BLOG_FINISH),
    ('blog', 'geo-report', 3, 3, 'GEO report for a published post', BLOG_GEO),
    ('presentation', 'text', 1, 2, 'Start and slide text', PRESENTATION_TEXT),
    ('presentation', 'deck', 2, 2, 'Design, refine and deliver', PRESENTATION_DECK),
    ('infographic', 'story', 1, 2, 'Story and build', INFOGRAPHIC_STORY),
    ('infographic', 'approve', 2, 2, 'Review, approve and prepare', INFOGRAPHIC_APPROVE),
)


# --- Layout -------------------------------------------------------------------------

class Box:
    def __init__(self, node, x, w):
        self.id, self.col, self.row, self.role, self.title, self.sub = node
        self.x, self.w = x, w
        self.titles = wrap(self.title, TITLE, w - 24, bold=True)
        self.subs = wrap(self.sub, SUB, w - 24)
        self.need = 12 + len(self.titles) * TITLE_LINE + 2 + len(self.subs) * SUB_LINE + 10
        self.y = self.h = 0

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def side(self, toward):
        return self.x + self.w if toward > self.cx else self.x

    def contains(self, x, y, inset=0.5):
        return (self.x + inset < x < self.x + self.w - inset
                and self.y + inset < y < self.y + self.h - inset)


def layout(nodes, edges):
    left = any(node[1] < 0 for node in nodes)
    right = any(node[1] > 0 for node in nodes)
    main_x = PAD + (SIDE + GAP if left else 0)
    places = {-1: (PAD, SIDE), 0: (main_x, MAIN), 1: (main_x + MAIN + GAP, SIDE)}
    total = main_x + MAIN + (GAP + SIDE if right else 0) + PAD
    boxes = {node[0]: Box(node, *places[node[1]]) for node in nodes}
    rows = max(box.row for box in boxes.values()) + 1
    heights = [max(box.need for box in boxes.values() if box.row == row) for row in range(rows)]
    top = 104
    y = top
    for row in range(rows):
        for box in boxes.values():
            if box.row == row:
                box.y, box.h = y, heights[row]
        y += heights[row] + ROW_GAP
    return boxes, max(total, 480), y - ROW_GAP + PAD


def corner_path(points):
    """An axis-aligned polyline with softened corners."""
    out = [f'M{points[0][0]:g} {points[0][1]:g}']
    for n in range(1, len(points) - 1):
        (ax, ay), (bx, by), (cx, cy) = points[n - 1], points[n], points[n + 1]
        r = min(CORNER, abs(bx - ax) / 2 or CORNER, abs(by - ay) / 2 or CORNER,
                abs(cx - bx) / 2 or CORNER, abs(cy - by) / 2 or CORNER)
        sx = bx - (r if bx > ax else -r if bx < ax else 0)
        sy = by - (r if by > ay else -r if by < ay else 0)
        ex = bx + (r if cx > bx else -r if cx < bx else 0)
        ey = by + (r if cy > by else -r if cy < by else 0)
        out.append(f'L{sx:g} {sy:g}Q{bx:g} {by:g} {ex:g} {ey:g}')
    out.append(f'L{points[-1][0]:g} {points[-1][1]:g}')
    return ''.join(out)


def head(x, y, dx, dy):
    """A filled arrowhead whose tip is at x, y, pointing along dx, dy."""
    if dx:
        return f'M{x:g} {y:g}l{-7 * dx:g} -4v8z'
    return f'M{x:g} {y:g}l-4 {-7 * dy:g}h8z'


def route(a, b, how):
    """Polylines, each ending in an arrowhead, for one edge."""
    if how == 'down':
        return [[(a.cx, a.y + a.h), (b.cx, b.y)]]
    if how == 'side':
        return [[(a.side(b.cx), a.cy), (b.side(a.cx), b.cy)]]
    if how == 'both':
        out, back = (a.side(b.cx), b.side(a.cx))
        return [[(out, a.cy - 6), (back, a.cy - 6)], [(back, a.cy + 6), (out, a.cy + 6)]]
    if how == 'back':
        start = (a.cx, a.y if b.cy < a.cy else a.y + a.h)
        return [[start, (a.cx, b.cy), (b.side(a.cx), b.cy)]]
    if how == 'over':
        end = (b.cx, b.y if b.cy > a.cy else b.y + b.h)
        return [[(a.side(b.cx), a.cy), (b.cx, a.cy), end]]
    raise ValueError(how)


def label_box(a, b, value):
    x, y = a.cx + 10, (a.y + a.h + b.y) / 2
    return (x, y - 8, width(value, SMALL), 16)


def problems(boxes, edges):
    """Reasons a diagram would read badly: overlaps, or a line through a box."""
    found = []
    shapes = list(boxes.values())
    for n, one in enumerate(shapes):
        for other in shapes[n + 1:]:
            if (one.x < other.x + other.w and other.x < one.x + one.w
                    and one.y < other.y + other.h and other.y < one.y + one.h):
                found.append(f'{one.id} overlaps {other.id}')
    for source, target, how, value in edges:
        a, b = boxes[source], boxes[target]
        for line in route(a, b, how):
            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                steps = int(max(abs(x2 - x1), abs(y2 - y1)))
                for k in range(1, steps):
                    x, y = x1 + (x2 - x1) * k / steps, y1 + (y2 - y1) * k / steps
                    for box in shapes:
                        if box.contains(x, y):
                            found.append(f'{source} to {target} crosses {box.id}')
                            break
        if value:
            lx, ly, lw, lh = label_box(a, b, value)
            for box in shapes:
                if lx < box.x + box.w and box.x < lx + lw and ly < box.y + box.h and box.y < ly + lh:
                    found.append(f'label "{value}" overlaps {box.id}')
            if lx + lw > max(box.x + box.w for box in shapes) + PAD:
                found.append(f'label "{value}" runs off the page')
    return sorted(set(found))


# --- Drawing ------------------------------------------------------------------------

def style(studio):
    (colour, wash), (dark, dark_wash) = STUDIOS[studio][1:]

    def rules(paper, line, ink, quiet, solid, solid_line, arrow, accent, on_accent, tint):
        return (f'.page{{fill:{paper};stroke:{line}}}'
                f'.ink{{fill:{ink}}}.quiet{{fill:{quiet}}}.accent-text{{fill:{accent}}}'
                f'.you{{fill:{accent};stroke:{accent}}}.you-text{{fill:{on_accent}}}'
                f'.assistant{{fill:{tint};stroke:{accent}}}'
                f'.studio{{fill:{solid};stroke:{solid_line}}}'
                f'.wire{{fill:none;stroke:{arrow}}}.tip{{fill:{arrow}}}')

    light = rules('#ffffff', '#d9dee6', '#1c1d22', '#565a69', '#eef1f5', '#a9b1bf',
                  '#6b7080', colour, '#ffffff', wash)
    night = rules('#191f29', '#39404d', '#f3f4f8', '#abb0c0', '#262d39', '#5d6576',
                  '#9aa0b0', dark, '#151c29', dark_wash)
    return ('<style>'
            'svg{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",'
            'Helvetica,Arial,sans-serif}'
            '.title{font-weight:600}.bold{font-weight:700}'
            '.page,.you,.assistant,.studio{stroke-width:0.5}.wire{stroke-width:1.1}'
            f'{light}@media (prefers-color-scheme:dark){{{night}}}</style>')


def text(x, y, value, size, cls, anchor='middle', weight=''):
    weight = f' {weight}' if weight else ''
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" class="{cls}{weight}" '
            f'text-anchor="{anchor}">{escape(value)}</text>')


def draw_box(box):
    fill = 'you-text' if box.role == 'you' else 'ink'
    quiet = 'you-text' if box.role == 'you' else 'quiet'
    out = [f'<rect x="{box.x:g}" y="{box.y:g}" width="{box.w:g}" height="{box.h:g}" '
           f'rx="10" class="{box.role}"/>']
    block = len(box.titles) * TITLE_LINE + 2 + len(box.subs) * SUB_LINE
    y = box.y + (box.h - block) / 2 + 14
    for line in box.titles:
        out.append(text(box.cx, y, line, TITLE, fill, weight='bold'))
        y += TITLE_LINE
    y += 2
    for line in box.subs:
        out.append(text(box.cx, y, line, SUB, quiet))
        y += SUB_LINE
    return '\n'.join(out)


def draw_edge(boxes, source, target, how, value):
    a, b = boxes[source], boxes[target]
    out = []
    for line in route(a, b, how):
        (x1, y1), (x2, y2) = line[-2], line[-1]
        dx = (x2 > x1) - (x2 < x1)
        dy = (y2 > y1) - (y2 < y1)
        shaft = line[:-1] + [(x2 - 6 * dx, y2 - 6 * dy)]
        out += [f'<path d="{corner_path(shaft)}" class="wire"/>',
                f'<path d="{head(x2, y2, dx, dy)}" class="tip"/>']
    if value:
        lx, ly, _, _ = label_box(a, b, value)
        out.append(text(lx, ly + 12, value, SMALL, 'quiet', 'start', 'title'))
    return '\n'.join(out)


def describe(boxes, edges):
    said = {box.id: f'{box.title} ({box.sub})' for box in boxes.values()}
    main = [box for box in sorted(boxes.values(), key=lambda box: box.row) if box.col == 0]
    out = ['Steps in order: ' + '; '.join(said[box.id] for box in main) + '.']
    for source, target, how, value in edges:
        a, b = boxes[source], boxes[target]
        if value:
            out.append(f'{value} leads from {a.title} to {b.title}.')
        if how == 'both':
            out.append(f'{a.title} can go to {said[target]} and come back.')
        elif how == 'back':
            out.append(f'{said[source]} returns to {b.title}.')
        elif how in ('over', 'side') and b.col and not a.col:
            out.append(f'{a.title} can lead to {said[target]}.')
        elif how == 'down' and a.col and b.col:
            out.append(f'{a.title} leads to {said[target]}.')
    return ' '.join(out)


def legend(x, y):
    out = []
    for role, words in ROLES:
        out += [f'<rect x="{x:g}" y="{y - 11:g}" width="22" height="14" rx="4" class="{role}"/>',
                text(x + 30, y, words, SMALL, 'quiet', 'start')]
        x += 30 + width(words, SMALL) + 22
    return '\n'.join(out), x


def render(studio, part, parts, heading, diagram):
    nodes, edges = diagram
    boxes, total, tall = layout(nodes, edges)
    wrong = problems(boxes, edges)
    if wrong:
        raise ValueError(f'{STUDIOS[studio][0]} {heading}: ' + '; '.join(wrong))
    name = STUDIOS[studio][0]
    title = f'{name} workflow, part {part} of {parts}: {heading}'
    key, end = legend(PAD + 4, 82)
    if end > total:
        raise ValueError(f'{title}: the legend does not fit')
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total:g}" height="{tall:g}" '
           f'viewBox="0 0 {total:g} {tall:g}" role="img" aria-labelledby="title desc">',
           f'<title id="title">{escape(title)}</title>',
           f'<desc id="desc">{escape(describe(boxes, edges))} Colours: filled boxes are '
           'your decisions or input, tinted boxes are assistant work and grey boxes are '
           'studio steps.</desc>',
           style(studio),
           f'<rect x="0.25" y="0.25" width="{total - 0.5:g}" height="{tall - 0.5:g}" '
           'rx="16" class="page"/>',
           text(PAD + 4, 34, f'{name} workflow · part {part} of {parts}', SUB,
                'accent-text', 'start', 'title'),
           text(PAD + 4, 58, heading, 19, 'ink', 'start', 'bold'),
           key]
    out += [draw_edge(boxes, *edge) for edge in edges]
    out += [draw_box(box) for box in boxes.values()]
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def built():
    """Every diagram's path, relative to the repository root, and its content."""
    return {f'studios/{studio}/docs/assets/{studio}-studio-workflow-{stem}.svg':
            render(studio, part, parts, heading, diagram)
            for studio, stem, part, parts, heading, diagram in DIAGRAMS}


def outdated(root=ROOT):
    """Paths under `root` whose diagram is missing or differs from its source."""
    found = []
    for path, content in built().items():
        file = Path(root) / path
        if not file.is_file() or file.read_text(encoding='utf-8') != content:
            found.append(path)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check without changing files')
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='the repository root to build or check (default: this checkout)')
    args = parser.parse_args()
    if args.check:
        stale = outdated(args.root)
        if stale:
            parser.exit(1, 'Rebuild workflow diagrams: ' + ', '.join(stale) + '\n')
        print(f'{len(DIAGRAMS)} workflow diagrams are current.')
        return
    for path, content in built().items():
        file = args.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')
    print(f'Built {len(DIAGRAMS)} workflow diagrams.')


if __name__ == '__main__':
    main()
