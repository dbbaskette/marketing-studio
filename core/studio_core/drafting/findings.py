"""Review findings as proposals: Apply is a note on the finding's part, never a text swap.

A reviewer, or a check made in process, finds something on one part of an item: a slide of a
deck, say. Each finding is kept as a proposal (`items`), in the shared proposals' sets
(`proposals.Proposals`), so it waits on this computer only and nothing changes until the
person applies it. Apply hands the finding's own words, its note and its fix, or the words
the person edited, to the studio's `note(ident, item, words)`, which notes the part for its
next redraw: it keeps the part's version first, and raises ValueError, in a sentence, where
the part cannot take a note now. Once every chosen finding is noted, `noted(ident, applied)`
is told, so a studio may start what draws them in one go; only then are they marked applied.
Skip keeps a finding as read (`skipped`), and changes nothing.

Nothing here knows what a part is or how it is redrawn: the studio passes `note`, `noted`
and `present(draft, item)`, whether the finding still fits its part: the part is in the
item, and has not been drawn again since the finding was made.
"""

from .proposals import ITEMS, Proposals

FIELDS = ('number', 'severity', 'about', 'question', 'note', 'fix', 'source')
NOTE_LIMIT = 4000  # characters in one note made from a finding
EMPTY = 'Write the note to make, then apply it.'
LONG = 'Keep a note to ' + format(NOTE_LIMIT, ',') + ' characters.'
NONE_NOTED = 'None of these could be noted now, so nothing was applied.'


def words_of(finding):
    """The note a finding makes: its note, then its fix, as one line."""
    said = ' '.join(str(finding.get(key) or '') for key in ('note', 'fix'))
    return ' '.join(said.split())


def items(findings, part, words=words_of, fields=()):
    """Each finding on a part, as a proposal: the part it names (the finding's key `part`),
    what it found (FIELDS, and the studio's own `fields`), and `after`, the note Apply makes
    (`words(finding)`). A finding that names no part is left out: there is nothing to note
    it on."""
    made = []
    for finding in findings or ():
        if not isinstance(finding, dict) or not isinstance(finding.get(part), str):
            continue
        made.append({
            'part': finding[part],
            **{key: finding[key] for key in (*FIELDS, *fields) if finding.get(key) is not None},
            'after': words(finding),
        })
    return made[:ITEMS]


def anywhere(draft, item):
    """The default `present`: every finding can still be noted."""
    return True


class Noted(Proposals):
    """Proposals whose Apply notes the finding's part through the studio's `note`, and whose
    Skip keeps it as read."""

    def __init__(self, store, desk, tools, note, owner='item', present=None, noted=None):
        super().__init__(store, desk, tools, owner=owner, present=present or anywhere)
        self.note, self.noted = note, noted

    def act(self, ident, job, found, draft, picks, every, named, left=()):
        """Note each chosen finding on its part. One finding that cannot be noted is refused
        with nothing changed; several at once note every one that can, and leave the rest
        open, counted in `left`."""
        single = len(named) == 1 and not every
        applied, left = [], list(left)
        for item, words in picks:
            words = ' '.join(str(words).split())
            try:
                if not words:
                    raise ValueError(EMPTY)
                if len(words) > NOTE_LIMIT:
                    raise ValueError(LONG)
                if not self.present(draft, item):
                    # Gone from the item, or drawn again since the finding was made.
                    raise ValueError(
                        'This ' + self.codec.noun + ' changed since this was found, so it '
                        'was not noted. Skip it.'
                    )
                self.note(ident, item, words)
            except ValueError:
                if single:
                    raise
                left.append(item['id'])
                continue
            applied.append(item)
        if not applied:
            if every:
                return {'applied': 0, 'left': left}
            raise ValueError(NONE_NOTED)
        if self.noted is not None:
            self.noted(ident, applied)
        # Only once every note is made are the findings marked applied.
        for item in applied:
            item['state'] = 'applied'
        self.store.write_json(self.path(ident, job), found)
        return {'applied': len(applied), 'left': left}
