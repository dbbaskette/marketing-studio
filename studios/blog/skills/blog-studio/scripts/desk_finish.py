"""Finishing on the desk: tools that propose changes the person previews, then applies,
edits or skips.

Nothing changes until Apply. A proposal set waits on this computer only, in
.blog-runs/desk-proposals/<blog id>/<job id>.json, never in the blog's own folder, so a team
workspace records only what Apply writes, as a decision. Each Apply keeps a `finishing`
version of every part it changes first. Like desk.py, every function expects the caller to
hold the studio lock.
"""

import re

import desk
import desk_images
import studio
from studio_core.drafting import guards
from studio_core.drafting import proposals as shared
from studio_core.drafting import proofread as quick

# The finishing job kinds and the tool each one is in the panel.
TOOLS = {
    'finish-copyedit': 'copyedit',
    'finish-humanize': 'humanize',
    'finish-facts': 'facts',
    'finish-headline': 'headline',
    'finish-feedback': 'feedback',
    'finish-voice': 'voice',
}
KINDS = tuple(TOOLS)
# The proposals are kept, applied and skipped by the shared desk
# (studio_core.drafting.proposals), with Blog Studio's store and desk record.
JOB = shared.JOB
ITEMS = shared.ITEMS  # proposals in one set
DAY = shared.DAY  # an older set no longer shown is let go after this long
LATEST = shared.LATEST  # the newest set for each tool, so a poll reads only those
GONE = shared.GONE
NONE_LEFT = shared.NONE_LEFT
SAME = shared.SAME
EMPTY = shared.EMPTY
OVERLAP = shared.OVERLAP
RETIRED = shared.RETIRED
FLAGGED = shared.FLAGGED


def _require_lock():
    if not studio.lock_held():
        raise RuntimeError('Desk writes run under the studio lock.')


class _BlogProposals(shared.Proposals):
    def sets(self, ident):
        return sets(self.store.root, ident)  # This module's, looked up when called.


def _proposals(root):
    """Blog Studio's waiting proposals: sets keyed `blog`, in .blog-runs/desk-proposals."""
    return _BlogProposals(
        desk.BlogStore(root), desk._drafting(root), TOOLS, owner='blog', together=SENTENCES
    )


def _folder(root, ident):
    return _proposals(root).folder(ident)


def _path(root, ident, job):
    return _proposals(root).path(ident, job)


def keep(root, ident, job, kind, items, **extra):
    """Keep a set of proposals for the person to preview; nothing in the draft changes."""
    return _proposals(root).keep(ident, job, kind, items, **extra)


def _latest(root, ident):
    """{tool: job} for the newest set of each tool, rebuilt from the sets when missing."""
    return _proposals(root).latest(ident)


def _prune(root, ident, shown):
    """Let go of sets no longer shown once nothing in them is open, or after a day."""
    _proposals(root).prune(ident, shown)


def read(root, ident, job):
    return _proposals(root).read(ident, job)


def sets(root, ident):
    """Every set kept for this blog, oldest first."""
    return shared.Proposals.sets(_proposals(root), ident)


def forget(root, ident):
    """Let a deleted blog's waiting suggestions go: they hold its text."""
    _proposals(root).forget(ident)


_once = shared.once


def present(draft, item):
    """Whether a proposal still fits the draft: its text is in its part, once, or the whole
    part is as it was for an alternative to the whole part. A comment needs only its part."""
    return shared.text_present(desk.CODEC)(draft, item)


def summary(root, ident, draft):
    """The newest set for each tool, as the panel shows it. Only those sets are read."""
    return _proposals(root).summary(ident, draft)


def _busy_parts(root, ident):
    """The parts a desk job under way may change, so an Apply never races it."""
    import desk_jobs

    parts = set()
    for job in desk_jobs.jobs(root, ident):
        if desk_jobs.busy(job):
            parts.add(((job.get('metadata') or {}).get('desk') or {}).get('part'))
    return parts


def apply(root, ident, seen, job, chosen, every=False):
    """Apply chosen proposals, each with its suggested text or the person's own (Edit).

    One proposal that no longer fits is refused with nothing changed. Several at once
    (Apply all) apply every one that still fits and leave the rest open, counted in `left`;
    one retired meanwhile is left out too. `every` is Review mode's Accept all: a suggestion
    that covers words a flagged one from Copy edit or Humanize still waits on is left out,
    so the flagged one is never retired without the person deciding on it. Each part
    changed keeps one `finishing` version first."""
    return _proposals(root).apply(
        ident, seen, job, chosen, every, working=lambda: _busy_parts(root, ident)
    )


def _sentence_sets(root, ident, job, found):
    """[(job, set)] for the waiting Copy edit and Humanize sets, this one as it is held."""
    return _proposals(root)._together_sets(ident, job, found)


def _flagged_spans(root, ident, job, found, originals, named):
    return _proposals(root)._flagged_spans(ident, job, found, originals, named)


_span = shared.span
_covers = shared.covers


# The tools whose sentence rewrites Review mode shows together; accepting one retires the
# others, from either tool, that covered the same words.
SENTENCES = ('finish-copyedit', 'finish-humanize')


def _retire(root, ident, job, found, originals, spans):
    _proposals(root)._retire(ident, job, found, originals, spans)


def skip(root, ident, job, ids):
    """Set proposals aside. Only this computer's waiting set changes."""
    return _proposals(root).skip(ident, job, ids)


# Quick check (the route and functions keep the name proofread): mechanical checks in
# process, no job. Advisory, never an authorship verdict.
AI_TELLS = ('blogforge', 'voice', 'assets', 'ai-tells')
# The checks themselves are the shared desk's (studio_core.drafting.proofread).
COMMON_STARTS = quick.COMMON_STARTS
PROOF_LIMIT = quick.PROOF_LIMIT  # findings shown at once
BOUNDARY = quick.BOUNDARY
WORD = quick.WORD
SENTENCE_MAX = quick.SENTENCE_MAX  # a passage Fix rewrites; a longer run is cut to its line


def _listed(name):
    import blog_runner

    path = blog_runner.REFERENCES.joinpath(*AI_TELLS, name)
    return [
        line.strip()
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]


def proof_rules():
    """The desk's mechanical rules: no em dashes or double hyphens, and the words and
    phrases BlogForge listed as reading machine-written. A desk blog has no voice rules."""
    return {
        'no_em_dashes': True,
        'no_ascii_double_hyphen': True,
        'banished_words': _listed('words.txt'),
        'banished_phrases': _listed('phrases.txt'),
    }


_sentences = quick.sentences
_sentence = quick.sentence
_offsets = quick.offsets
_label = quick.label
_finding = quick.finding
LIST_LINE = quick.LIST_LINE
_mask_indented = quick.mask_indented
_clean = quick.clean
_units = quick.units
_openers = quick.openers


def _repetition(part, text):
    """Within one part: an AI-tell sentence opener, two sentences in a row with the same
    first word, and a long word three times in one paragraph."""
    return quick.repetition(part, text, _listed('sentence-starters.txt'))


def proofread(root, ident):
    """Mechanical findings for each part, in draft order, each with the sentence Fix would
    rewrite. Reading only: nothing is written and no job starts."""
    import text_checks

    return quick.check(
        desk.read(root, ident),
        proof_rules(),
        _listed('sentence-starters.txt'),
        ident,
        join=lambda draft: desk.join(draft, images=False),
        lint=text_checks.lint,
    )


# The tools that propose through a job: what each asks for, and how its result is read.
UNREADABLE = 'The suggestions came back in a shape Blog Studio cannot read. Run it again.'
NO_TEXT = 'Write the draft first: Finishing works on written text.'
NO_SOURCES = 'Add a source first: facts are checked against your sources.'
LEVELS = {
    'light': 'Intensity: light. Smooth the flow and replace formulaic wording only; keep each '
    'sentence’s structure where you can.',
    'medium': 'Intensity: medium. Also vary rhythm and sentence openings, and let the point of '
    'view come through.',
    'strong': 'Intensity: strong. Rework sentences that read as generic so they sound like a '
    'person explaining their own work, keeping every fact.',
}
COPYEDIT = (
    'Copy edit this draft and its title: spelling, grammar, punctuation, consistency (a name, '
    'term, number style or capitalisation written two ways), clarity and concision only. Find '
    'the sentences that need such a fix and suggest the corrected sentence for each, changing '
    'only what the fix needs. Never change a claim, a qualifier or the argument, and never add, '
    'move or cut a point. Preserve the author’s voice and stance, every fact, number and name, '
    'each quotation and link exactly, and every image reference where it is; never change '
    'code. Leave sentences that are already correct alone. Do not research.'
)
COPYEDIT_JSON = (
    'Return JSON in content: {"suggestions": [{"part": ..., "kind": ..., "before": ..., '
    '"after": ..., "why": ...}]}, at most 60. part is "title", "opening" or the id of a section '
    'in sections; kind is "spelling", "grammar", "punctuation", "consistency" or "wording" '
    '(clarity and concision); before is one or two whole sentences copied exactly from that '
    'part, character for character (for the title, the words to change); after replaces '
    'before, on one line for the title; why names the fix in a few words, such as "Subject and '
    'verb agree". A wording suggestion may also have "alternatives": up to three other '
    'replacements for the same before, each a different way to say it. Spelling, grammar, '
    'punctuation and consistency fixes have one right answer and no alternatives.'
)
# The kinds of fix a copy edit names; anything else is read as grammar.
COPYEDIT_KINDS = ('spelling', 'grammar', 'punctuation', 'consistency', 'wording')
ALTERNATIVES = 3  # at most, for one wording suggestion
# The copy-editing guide's lenses a copy edit uses; the others (evidence, structure,
# persuasion and the rest) belong to a fuller edit.
COPYEDIT_LENSES = ('Clarity', 'Voice')
HUMANIZE = (
    'Find the sentences in this draft that read as machine-written: formulaic or stock '
    'wording, monotonous rhythm, repeated entrances, generic stance. Suggest a rewrite for each. '
    'Keep every number, name, quotation and link exactly. Never invent an opinion, experience, '
    'hesitation or anecdote. Leave sentences that already read well alone.'
)
HUMANIZE_JSON = (
    'Return JSON in content: {"suggestions": [{"part": ..., "before": ..., "after": ..., '
    '"why": ...}]}, at most 40. part is "opening" or the id of a section in sections; before is '
    'one or two whole sentences copied exactly from that part, character for character; after '
    'replaces before; why says in a few words what reads as machine-written.'
)
FACTS = (
    'Check each factual claim in the draft against sources and any research. A claim is '
    'supported when a source passage says it, not-in-sources when no source says it, and '
    'contradicted when a source says otherwise. Judge only from what is supplied; do not '
    'research.'
)
FACTS_JSON = (
    'Return JSON in content: {"claims": [{"part": ..., "before": ..., "verdict": ..., '
    '"passage": ..., "source": ..., "after": ..., "why": ...}]}, at most 40. part is "opening" '
    'or the id of a section in sections; before is the claim, copied exactly from that part; '
    'verdict is "supported", "not-in-sources" or "contradicted"; passage is the source passage '
    'it rests on, copied exactly ("" when none); source names that source; after is a rewording '
    'the sources support, for a claim that is not supported ("" when none fits); why says why.'
)
HEADLINE = (
    'Suggest alternatives for the title and the opening of this draft, from the draft itself, '
    'its brief and its sources. The title promises the topic; the opening pulls the reader into '
    'the argument. Make the alternatives meaningfully different from each other and from what '
    'is there. No clickbait, no promise the post cannot keep, no number the draft does not have.'
)
HEADLINE_JSON = (
    'Return JSON in content: {"titles": [{"text": ..., "why": ...}], "openings": [{"text": ..., '
    '"why": ...}]}, with up to five titles of one line each and up to three openings, each a '
    'whole replacement for the opening with no heading; why names what it does differently.'
)
FEEDBACK = (
    'Give editorial feedback on this draft without rewriting it: its shape, its argument, '
    'whether it serves its audience, and claims that need evidence. Quote the passage each '
    'comment is about and say the reader’s difficulty and a specific move. Nothing you say is '
    'applied to the text.'
)
FEEDBACK_JSON = (
    'Return JSON in content: {"summary": ..., "comments": [{"part": ..., "quote": ..., '
    '"aspect": ..., "comment": ...}]}, at most 30 comments. part is "title", "opening", the id '
    'of a section in sections, or "whole" for the draft as a whole; quote is a short passage '
    'copied exactly from that part ("" for none); aspect is "shape", "argument", "audience" or '
    '"claims"; summary is two or three sentences on the draft overall.'
)
VOICE = (
    'Rewrite this draft in the voice described in voice_guide, part by part. Change how it '
    'sounds, never what it says: keep the structure (the same paragraphs, lists, tables and code '
    'in the same order), every fact, number, name, quotation and link exactly, and the author’s '
    'stance. Apply only the supplied voice; preserve the facts and their uncertainty, and invent '
    'no experience, opinion or anecdote. Where the guide and the tone differ, follow the guide. '
    'Leave a part that already reads in this voice as it is.'
)
VOICE_JSON = (
    'Return JSON in content: {"parts": [{"part": ..., "text": ..., "why": ...}]}, one row for '
    'the opening and for each section in sections that has text. part is "opening" or the id of '
    'a section; text is the whole part rewritten, without its heading; why says in a few words '
    'what changed.'
)
NO_GUIDE = 'Choose a voice guide that is not retired.'
VERDICTS = {
    'supported': 'supported',
    'not-in-sources': 'not-in-sources',
    'unsupported': 'not-in-sources',
    'contradicted': 'contradicted',
}
ASPECTS = ('shape', 'argument', 'audience', 'claims')
NAME = guards.NAME


def _reference(*path):
    import blog_runner

    return blog_runner.REFERENCES.joinpath(*path).read_text(encoding='utf-8').rstrip()


def _lenses():
    """The copy-editing guide's clarity and voice lenses, as the guide words them."""
    lines, keeping = [], False
    for line in _reference('modules', 'copy-editing.md').splitlines():
        if line.startswith('- **'):
            keeping = any(line.startswith('- **' + name + ':**') for name in COPYEDIT_LENSES)
        elif not line.startswith('  '):
            keeping = False
        if keeping:
            lines.append(line)
    return 'Editing lenses for this copy edit:\n' + '\n'.join(lines)


def _payload(draft, extra):
    return {
        'title': draft['title'],
        'brief': draft.get('brief') or {},
        'opening': draft['opening'],
        'sections': [
            {'id': s['id'], 'heading': s['heading'], 'text': s['text']} for s in draft['sections']
        ],
        **extra,
    }


def _guide(root, guide):
    """A saved voice guide that is not retired: {id, name, revision, guide}."""
    import article_tools

    if not isinstance(guide, str) or not guide:
        raise ValueError(NO_GUIDE)
    try:
        chosen = article_tools.profile(root, guide)
    except (ValueError, OSError):
        raise ValueError(NO_GUIDE) from None
    if chosen.get('status') == 'retired':
        raise ValueError(NO_GUIDE)
    if not chosen['guide'].strip():
        raise ValueError('This voice guide has no text yet. Write it on the Voice guides screen.')
    return chosen


def request(root, ident, draft, tool, level=None, guide=None):
    """The kind, payload, guidance and job details for one finishing tool on this draft."""
    import blog_runner
    import desk_jobs
    import manuscript_editor

    kinds = {tool: kind for kind, tool in TOOLS.items()}
    if tool not in kinds:
        raise ValueError('Choose a finishing tool.')
    written = draft['opening'].strip() or any(s['text'].strip() for s in draft['sections'])
    if tool != 'headline' and not written:
        raise ValueError(NO_TEXT)
    extra, shared = desk_jobs._context(root, draft)
    extra.pop('response_kind', None)  # The suggestions are JSON in content.
    extra.pop('gaps', None)
    meta = {}
    if tool == 'copyedit':
        # Only the draft and its tone: no sources, examples or kind of post to edit towards.
        payload = _payload(draft, {'tone': extra.get('tone', '')})
        guidance = COPYEDIT + ' ' + desk_jobs.desk_check('copyedit') + ' '
        guidance += desk_jobs.desk_check('proofread') + '\n\n' + _lenses() + '\n\n'
        guidance += blog_runner.shared_guidance(None, draft.get('tone', ''))
        if draft.get('images'):
            guidance += '\n' + desk_images.GUIDANCE
        guidance += '\n' + COPYEDIT_JSON
    elif tool == 'humanize':
        if level not in LEVELS:
            raise ValueError('Choose light, medium or strong.')
        meta['level'] = level
        payload = {**_payload(draft, extra), 'level': level}
        guidance = (
            HUMANIZE + ' ' + LEVELS[level] + '\n\n' + _reference('modules', 'blog-humanize.md')
        )
        guidance += '\n\n' + shared + '\n' + HUMANIZE_JSON
    elif tool == 'facts':
        research, said = desk_jobs._research_extra(root, ident)
        if not extra['sources'] and not research:
            raise ValueError(NO_SOURCES)
        payload = {**_payload(draft, extra), **research}
        guidance = manuscript_editor.CHECKS['factual-support'] + ' ' + FACTS + '\n\n'
        guidance += _reference('modules', 'blog-fact-check.md') + '\n\n'
        guidance += _reference('review', 'evidence.md') + '\n\n' + shared + said
        guidance += '\nThe sources are in sources, with their names and stance.\n' + FACTS_JSON
    elif tool == 'voice':
        # The guide's text is put in the payload: the desk's own context stays tone-only.
        chosen = _guide(root, guide)
        meta.update(
            guide=chosen['id'], guide_name=chosen['name'], guide_revision=chosen['revision']
        )
        payload = {
            **_payload(draft, extra),
            'voice_guide': {'name': chosen['name'], 'text': chosen['guide']},
        }
        guidance = VOICE + '\n\n' + shared + '\n' + VOICE_JSON
    elif tool == 'headline':
        payload = _payload(draft, extra)
        guidance = HEADLINE + '\n\n' + _reference('headline-lab.md') + '\n\n' + shared
        guidance += '\n' + HEADLINE_JSON
    else:
        payload = _payload(draft, extra)
        guidance = FEEDBACK + '\n\n' + blog_runner.STAGES['review'][2] + ' '
        guidance += manuscript_editor.CHECKS['shape'] + '\n\n' + _reference('review', 'shape.md')
        guidance += '\n\n' + shared + '\n' + FEEDBACK_JSON
    return kinds[tool], payload, guidance, meta


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


# Whether a proposal keeps the facts and the part's structure: the shared guards, with an
# image reference read as desk_images reads it.
def _names(text):
    """Capitalised words that are not the first word of a sentence: likely names. An image
    reference is not text: its alt and label are left out, and a word after it starts afresh."""
    return guards.names(text, desk_images.REFERENCE)


_named = guards.named


def changes_facts(before, after, anywhere=False):
    """What a rewrite changes that it should keep: numbers, links, quotes or names."""
    return guards.changes_facts(before, after, anywhere, desk_images.REFERENCE)


STRUCTURE = guards.STRUCTURE
FENCE = guards.FENCE
INLINE_CODE = guards.INLINE_CODE
TABLE_LINE = guards.TABLE_LINE
QUOTE_LINE = guards.QUOTE_LINE


def _shape(text, paragraphs=True):
    return guards.shape(text, paragraphs, desk_images.REFERENCE)


def changes_structure(before, after, paragraphs=True):
    """STRUCTURE when a rewrite changes code, an image reference or the part's blocks."""
    return guards.changes_structure(before, after, paragraphs, desk_images.REFERENCE)


def _flags(before, after, anywhere=False, paragraphs=True):
    """Every reason a proposal waits to be checked one by one, as one line."""
    return guards.flags(before, after, anywhere, paragraphs, desk_images.REFERENCE)


def _located(draft, part, before):
    """`before` as it occurs once in its part, or None."""
    return shared.located(draft, part, before, desk.CODEC)


def _prose_parts(draft):
    return {'opening'} | {s['id'] for s in draft['sections']}


def _rows(found, key, fields):
    """The result's rows, each a dict whose named fields are text. A row of another shape is
    dropped; a result made only of such rows cannot be read."""
    return shared.rows(found, key, fields, UNREADABLE)


def _replacement(draft, part, before, after):
    """`after` as a replacement for `before` in its part, stripped, or None when it is not
    one: empty, the same, adding a heading, or more than one line in the title."""
    if not isinstance(after, str) or not after.strip() or len(after) > desk.LIMIT:
        return None
    after = after.strip()
    if (
        after == before
        or desk.has_heading(after, desk.limit(draft))
        or (part == 'title' and '\n' in after)
    ):
        return None
    return after


def _alternatives(draft, part, before, after, found):
    """A wording suggestion's other replacements, read strictly: a list of at most three
    strings, each a replacement for the same `before` that differs from it and from the ones
    before; another shape gives none. Each is flagged as a suggestion is."""
    if not isinstance(found, list) or not found or len(found) > ALTERNATIVES:
        return []
    kept, taken = [], {after}
    for value in found:
        text = _replacement(draft, part, before, value)
        if text is None or text in taken:
            continue
        taken.add(text)
        kept.append({'after': text, 'flag': _flags(before, text)})
    return kept


def _read_humanize(draft, found, title=False, kinds=False):
    """Sentence rewrites (Humanize, and Copy edit with the title too): each `before` found
    once in its part, and an `after` that changes it without adding a heading, on one line
    for the title. Any other row is dropped. With `kinds` (Copy edit), each fix names its
    kind, grammar when it names none it may, and a wording fix may bring alternatives."""
    rows, dropped = _rows(found, 'suggestions', ('part', 'before', 'after'))
    parts = _prose_parts(draft) | ({'title'} if title else set())
    items, seen = [], set()
    for row in rows:
        part = row.get('part')
        before = _located(draft, part, row.get('before')) if part in parts else None
        after = None if before is None else _replacement(draft, part, before, row.get('after'))
        if after is None or (part, before) in seen:
            dropped += 1
            continue
        seen.add((part, before))
        item = {
            'part': part,
            'before': before,
            'after': after,
            'note': _text(row.get('why'), 500),
            'flag': _flags(before, after),
        }
        if kinds:
            kind = row.get('kind')
            item['kind'] = kind if isinstance(kind, str) and kind in COPYEDIT_KINDS else 'grammar'
            others = (
                _alternatives(draft, part, before, after, row.get('alternatives'))
                if item['kind'] == 'wording'
                else []
            )
            if others:
                item['alternatives'] = others
        items.append(item)
    return items, dropped, {}


def _read_facts(draft, found):
    rows, dropped = _rows(found, 'claims', ('part', 'before', 'verdict'))
    items = []
    for row in rows:
        part, verdict = row.get('part'), VERDICTS.get(row.get('verdict'))
        before = _located(draft, part, row.get('before')) if part in _prose_parts(draft) else None
        if before is None or verdict is None:
            dropped += 1
            continue
        item = {
            'part': part,
            'before': before,
            'verdict': verdict,
            'passage': _text(row.get('passage'), 2000),
            'source': _text(row.get('source'), 300),
            'note': _text(row.get('why'), 500),
        }
        after = _text(row.get('after'), desk.LIMIT)
        if (
            verdict != 'supported'
            and after
            and after != before
            and not desk.has_heading(after, desk.limit(draft))
        ):
            item['after'] = after
            item['flag'] = changes_structure(before, after)
        items.append(item)
    order = {'contradicted': 0, 'not-in-sources': 1, 'supported': 2}
    items.sort(key=lambda item: order[item['verdict']])
    return items, dropped, {}


def _read_headline(draft, found):
    if not isinstance(found, dict):
        raise ValueError(UNREADABLE)
    titles, openings = found.get('titles') or [], found.get('openings') or []
    if not isinstance(titles, list) or not isinstance(openings, list) or not titles + openings:
        raise ValueError(UNREADABLE)
    items, dropped = [], 0
    for part, rows, limit in (('title', titles[:5], 500), ('opening', openings[:3], 20_000)):
        for row in rows:
            row = row if isinstance(row, dict) else {}
            text = row.get('text')
            text = text.strip() if isinstance(text, str) else ''
            if part == 'title':
                text = text.lstrip('#').strip()
            if (
                not text
                or len(text) > limit
                or (part == 'title' and '\n' in text)
                or (part == 'opening' and desk.has_heading(text, desk.limit(draft)))
                or text == draft[part]
            ):
                dropped += 1
                continue
            shown = desk_images.scrub(draft[part])
            items.append(
                {
                    'part': part,
                    'before': shown,
                    'after': text,
                    'note': _text(row.get('why'), 500),
                    # An alternative opening may reshape its paragraphs; code and lists stay.
                    'flag': changes_structure(shown, text, paragraphs=False),
                    'whole': True,
                    'group': part,
                }
            )
    return items, dropped, {}


def _read_feedback(draft, found):
    rows = found.get('comments') if isinstance(found, dict) else None
    if not isinstance(rows, list):
        raise ValueError(UNREADABLE)
    parts = _prose_parts(draft) | {'title'}
    items = []
    for row in rows[:40]:
        row = row if isinstance(row, dict) else {}
        comment = _text(row.get('comment'), 2000)
        if not comment:
            continue
        part = row.get('part')
        part = part if isinstance(part, str) and part in parts else 'whole'
        quote = _located(draft, part, row.get('quote')) if part != 'whole' else None
        aspect = row.get('aspect')
        aspect = aspect if isinstance(aspect, str) and aspect in ASPECTS else 'shape'
        items.append({'part': part, 'quote': quote or '', 'aspect': aspect, 'comment': comment})
    summary = _text(found.get('summary'), 2000)
    if not items and not summary:
        raise ValueError(UNREADABLE)
    return items, 0, {'summary': summary}


def _read_voice(draft, found):
    """One proposal per part the voice rewrote: the whole part, before and after. A part the
    guide left as it was is counted as kept; an unknown part, a heading, or a second row for
    one part is dropped."""
    rows, dropped = _rows(found, 'parts', ('part', 'text'))
    order = ['opening'] + [s['id'] for s in draft['sections']]
    items, seen, kept = [], set(), 0
    for row in rows:
        part = row.get('part')
        if part not in _prose_parts(draft) or part in seen:
            dropped += 1
            continue
        seen.add(part)
        before, after = desk_images.scrub(desk.text_of(draft, part)), row['text'].strip()
        if not before.strip():
            dropped += 1
            continue
        if after == before.strip():
            kept += 1
            continue
        try:
            desk_images.restored(desk.text_of(draft, part), after)
        except ValueError:
            dropped += 1  # It lost or changed image data the part keeps as text.
            continue
        if not after or desk.has_heading(after, desk.limit(draft)):
            dropped += 1
            continue
        items.append(
            {
                'part': part,
                'before': before,
                'after': after,
                'note': _text(row.get('why'), 500),
                'flag': _flags(before, after, anywhere=True),
                'whole': True,
            }
        )
    items.sort(key=lambda item: order.index(item['part']))
    return items, dropped, {'kept': kept}


def _read_copyedit(draft, found):
    """Located sentence fixes, read as Humanize's are, and the title's too, each with its
    kind and a wording fix with any alternatives."""
    return _read_humanize(draft, found, title=True, kinds=True)


READERS = {
    'finish-copyedit': _read_copyedit,
    'finish-humanize': _read_humanize,
    'finish-facts': _read_facts,
    'finish-headline': _read_headline,
    'finish-feedback': _read_feedback,
    'finish-voice': _read_voice,
}


def settle(root, ident, draft, job):
    """Read a finishing tool's result strictly and keep its proposals for the person. The
    draft is not changed; a result Blog Studio cannot read is refused readably."""
    found = shared.read_result((job.get('result') or {}).get('content'), UNREADABLE)
    try:
        items, dropped, extra = READERS[job['kind']](draft, found)
    except (TypeError, AttributeError, KeyError):
        raise ValueError(UNREADABLE) from None  # A shape no reader expects, said plainly.
    meta = (job.get('metadata') or {}).get('desk') or {}
    if meta.get('level'):
        extra['level'] = meta['level']
    if meta.get('guide_name'):
        extra['guide_name'] = meta['guide_name']  # Which voice guide the set applies.
    return keep(root, ident, job['id'], job['kind'], items, dropped=dropped, **extra)


# Before publishing: repurpose into new desk blogs, and send the desk's wording to the
# blog's Google Doc as suggestions. The pre-publish check reads DRAFT.md, which every desk
# write keeps in step.
MARKS = frozenset('[]*`<>#')
NO_DOC = (
    'This blog has no Google Doc to send suggestions to. A blog started from a Google Doc can '
    'send its desk changes back to that Doc.'
)


ESCAPED = re.compile(r'\\([\\`*_{}\[\]()#+\-.!<>|~])')
VISIBLE = (
    (re.compile(r'^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+]\s+|\d{1,3}[.)]\s+)'), ''),  # line markers
    (re.compile(r'!\[[^\]]*\]\([^)]*\)'), ''),  # images
    (re.compile(r'!\[[^\]\n]*\]\[[^\]\n]*\]'), ''),  # images by reference, as Google exports
    (re.compile(r'\[\^[^\]]+\]'), ''),  # footnote markers
    (re.compile(r'\[([^\]]*)\]\([^)]*\)'), r'\1'),  # links show their text, not their target
    (re.compile(r'<(https?://[^>\s]+)>'), r'\1'),
    (re.compile(r'[*`]+'), ''),  # emphasis and code marks
)


def _visible(line):
    """A Markdown line as the Doc's body paragraph shows it, or None for a line that is not
    one (a table row, a fence, a footnote's own text)."""
    bare = line.strip()
    if bare.startswith('|') or bare.startswith(('```', '~~~')) or re.match(r'\[[^\]]+\]:', bare):
        return None  # Also a footnote's or a link's definition, such as an image's data.
    # An escaped mark is the character itself, as Google's Markdown export writes it.
    line = ESCAPED.sub(lambda found: '\x00' + str(ord(found.group(1))) + '\x00', line)
    for pattern, replacement in VISIBLE:
        line = pattern.sub(replacement, line)
    return re.sub('\x00([0-9]+)\x00', lambda found: chr(int(found.group(1))), line)


def _hidden_spans(line):
    """Where a line holds what the Doc shows no text for: link targets and whole images."""
    return [m.span(1) for m in re.finditer(r'\]\(([^)]*)\)', line)] + [
        m.span()
        for m in re.finditer(
            r'!\[[^\]]*\]\([^)]*\)|!\[[^\]\n]*\]\[[^\]\n]*\]|<https?://[^>\s]+>', line
        )
    ]


def _touches(spans, start, end):
    return any(start < b and a < max(end, start + 1) for a, b in spans)


def _shown(lines):
    return [shown for shown in (_visible(line) for line in lines) if shown is not None]


def _aligned(before, opcodes):
    """Opcodes with a change among repeated paragraphs kept in place. Where copies of one
    paragraph repeat, the diff may read an edit to one copy as a line added before them and
    one removed after; the same lines read as that copy replaced."""
    out, at = [], 0
    while at < len(opcodes):
        three = opcodes[at : at + 3]
        if len(three) == 3 and [op[0] for op in three] == ['insert', 'equal', 'delete']:
            (_, a, _, c, d), (_, _, e, _, g), (_, _, f, _, _) = three
            k = d - c
            if f - e == k and before[a:f] == before[e:f] + before[a:e]:
                out += [('replace', a, a + k, c, d), ('equal', a + k, f, d, g)]
                at += 3
                continue
        if len(three) == 3 and [op[0] for op in three] == ['delete', 'equal', 'insert']:
            (_, a, b, c, _), (_, _, e, _, g), (_, _, _, h, i) = three
            k = b - a
            if i - h == k and before[a:e] == before[b:e] + before[a:b]:
                out += [('equal', a, a + (e - b), c, g), ('replace', a + (e - b), e, h, i)]
                at += 3
                continue
        out.append(opcodes[at])
        at += 1
    return out


def google_changes(baseline, body):
    """The desk's wording changes against the Google Doc as quoted suggestions, how many
    changed paragraphs cannot be one (added, removed, split or formatted), and the Doc
    paragraph each suggestion is in with how many times the Doc should show what locates it.
    A suggestion's id stays the same wherever its paragraph moves, so one sent before is known
    again. Copies are counted in the text a reader of the Doc sees, as Google's own search
    finds it: link targets, images, table rows and footnote markers are not part of it."""
    import difflib
    import json

    import manuscript_editor

    # Paragraphs, without the blank lines between them, so the diff aligns on text.
    before = [line for line in baseline.splitlines() if line.strip()]
    after = [line for line in body.splitlines() if line.strip()]
    found, left, paragraphs = [], 0, {}
    opcodes = _aligned(
        before, difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    )
    for tag, a, b, c, d in opcodes:
        if tag == 'equal':
            continue
        olds, news = before[a:b], after[c:d]
        if len(olds) * len(news) > 40_000:
            left += max(len(olds), len(news))  # Too much moved at once to pair safely.
            continue
        # Pair Doc paragraphs with desk lines, the closest pairs first, never two pairs that
        # cross: a paragraph deleted next to an edited one is never rewritten into it.
        ratios = sorted(
            (
                (difflib.SequenceMatcher(None, old, new).ratio(), i, j)
                for i, old in enumerate(olds)
                for j, new in enumerate(news)
            ),
            key=lambda found: (-found[0], found[1], found[2]),
        )
        pairs = []
        for ratio, i, j in ratios:
            if ratio < 0.6:
                break
            if all(i != pi and j != pj and (i < pi) == (j < pj) for pi, pj in pairs):
                pairs.append((i, j))
        pairs.sort()
        left += max(len(olds), len(news)) - len(pairs)
        for i, j in pairs:
            old, new, at = olds[i], news[j], a + i
            if old == new:
                continue
            # A link's address, an image or formatting changed only: the Doc shows no words
            # for it, so it is made in the Doc by hand. Otherwise the change is found in the
            # words the Doc shows, and every count is taken from those words.
            shown, now = _visible(old), _visible(new)
            raw_left, raw_tail = manuscript_editor.changed_bounds(old, new)
            raw_quoted, raw_replacement = manuscript_editor.changed_span(old, new)
            if (
                shown is None
                or now is None
                or shown == now
                or not now.strip()
                or any(mark in raw_quoted + raw_replacement for mark in MARKS)
                or _touches(_hidden_spans(old), raw_left, len(old) - raw_tail)
                or _touches(_hidden_spans(new), raw_left, len(new) - raw_tail)
            ):
                left += 1  # A link or formatting change, made in the Doc by hand.
                continue
            start, _ = manuscript_editor.changed_bounds(shown, now)
            quoted, replacement = manuscript_editor.changed_span(shown, now)
            if not quoted.strip() or any(mark in quoted + replacement for mark in MARKS):
                left += 1
                continue
            # Which copy this is of a paragraph the Doc repeats, so each copy is its own.
            shown_before, shown_after = _shown(before[:at]), _shown(before[at:])
            copy = sum(line.count(shown) for line in shown_before)
            copies = copy + sum(line.count(shown) for line in shown_after)
            quotes = sum(line.count(quoted) for line in shown_before + shown_after)
            item = {
                'id': 'desk-'
                + studio.digest(json.dumps([old, quoted, replacement, copy]).encode())[:16],
                'kind': 'edit',
                'before': quoted,
                'after': replacement,
                'reason': 'Wording changed on the writing desk.',
            }
            occurrence, needle, matches = None, quoted, quotes
            if shown.strip().count(quoted) == 1 and (copies > 1 or quotes > 1):
                item['context'] = shown.strip()  # The paragraph, so the quote is found in it.
                needle, matches = shown.strip(), copies
                occurrence = copy + 1 if copies > 1 else None
            elif quotes > 1:
                occurrence = (
                    sum(line.count(quoted) for line in shown_before)
                    + shown[:start].count(quoted)
                    + 1
                )
            item = manuscript_editor.proposal(item)
            if occurrence:
                item['occurrence'] = occurrence
            found.append(item)
            paragraphs[item['id']] = {
                'paragraph': studio.digest(old.encode()),
                'needle': needle,
                'matches': matches,
                'text': shown.strip(),  # The paragraph the change is meant for, as shown.
            }
    return found, left, paragraphs


def _sent_path(root, ident):
    return studio.inside(root, '.blog-runs', 'desk-google', studio.identifier(ident) + '.json')


def _sent(root, ident):
    """What this computer sent to the blog's Doc: {'plans': {token: rows}, 'sent': rows},
    each row {id, paragraph}. Kept beside the jobs, never in the blog's folder."""
    target = _sent_path(root, ident)
    try:
        found = studio.read_json(target) if target.is_file() and not target.is_symlink() else {}
    except (ValueError, OSError):
        found = {}
    found = found if isinstance(found, dict) else {}
    return {'plans': dict(found.get('plans') or {}), 'sent': list(found.get('sent') or [])}


def _delivered(root, document, ident):
    """Whether the Google ledger holds a reservation for this suggestion in this Doc."""
    import google_suggestions as suggestions

    marker = suggestions.contained(
        suggestions.ledger(root),
        suggestions.digest(suggestions.encoded([document, ident])) + '.finding',
    )
    return marker.is_file()


def _google_base(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    base = (record.get('google') or {}).get('baselines', {}).get('draft') or {}
    if not base.get('document') or not base.get('transfer'):
        raise ValueError(NO_DOC)
    return directory, record, base


def google_ready(record):
    base = (record.get('google') or {}).get('baselines', {}).get('draft') or {}
    return bool(base.get('document') and base.get('transfer'))


def _google_expected(root, ident):
    directory, record, base = _google_base(root, ident)
    import json

    body = (directory / 'DRAFT.md').read_bytes() if (directory / 'DRAFT.md').is_file() else b''
    return studio.digest(body + json.dumps(base, sort_keys=True).encode())


def google_plan(root, ident, mode):
    """Check the desk's latest wording against the Google Doc as suggestions; nothing is sent."""
    import google_drive as drive
    from google_workflow import snapshot_path

    import manuscript_editor

    directory, _, base = _google_base(root, ident)
    if mode not in ('auto', 'native', 'comments'):
        raise ValueError('Choose suggestions, comments or suggestions with comments fallback.')
    baseline = snapshot_path(directory, base['transfer'], 'document').read_text()
    proposals, left, paragraphs = google_changes(baseline, (directory / 'DRAFT.md').read_text())
    # A suggestion sent before stays in the Doc for its owner and is not sent again.
    record = _sent(root, ident)
    document = base['document'].get('document_id')
    sent = {row.get('id') for row in record['sent']} | {
        p['id'] for p in proposals if _delivered(root, document, p['id'])
    }
    before = sum(1 for p in proposals if p['id'] in sent)
    proposals = [p for p in proposals if p['id'] not in sent]
    client = drive.Client(drive.account_for(root))
    # A paragraph the Doc shows with a suggestion still waiting for its owner waits too; once
    # the owner accepts or rejects it, the paragraph can take another.
    waiting = unsure = 0
    if proposals:
        proposals, waiting, unsure = _not_pending(
            client, base['document'], proposals, paragraphs, mode
        )
        left += unsure
    if not proposals:
        said = []
        if before:
            said.append(
                str(before) + (' change was' if before == 1 else ' changes were') + ' sent before'
            )
        if waiting:
            said.append(
                str(waiting)
                + (' change is' if waiting == 1 else ' changes are')
                + ' in a paragraph that still has a suggestion waiting for the Doc’s owner to '
                'accept or reject'
            )
        if unsure:
            said.append(
                str(unsure)
                + (' change' if unsure == 1 else ' changes')
                + ' could not be placed in the Doc with certainty and '
                + ('stays' if unsure == 1 else 'stay')
                + ' on the desk'
            )
        if left - unsure:
            said.append('paragraphs added, removed or formatted cannot be suggestions')
        raise ValueError(
            'Nothing new to send'
            + (
                ': ' + '; '.join(said) + '.'
                if said
                else ': the desk’s wording matches the Google Doc.'
            )
        )
    if len(proposals) > 100:
        raise ValueError(
            'More than 100 wording changes to send at once. Send fewer, or share the draft.'
        )
    plan = manuscript_editor.google_plan(
        client, root, ident, proposals, mode, _google_expected(root, ident), base['document']['url']
    )
    record['plans'] = {
        **{token: rows for token, rows in record['plans'].items() if token != plan['plan']},
        plan['plan']: [
            {'id': p['id'], 'paragraph': paragraphs[p['id']]['paragraph']} for p in proposals
        ],
    }
    record['plans'] = dict(list(record['plans'].items())[-20:])
    studio.write_json(_sent_path(root, ident), record)
    return {**plan, 'left': left, 'sent_before': before, 'waiting': waiting}


def _not_pending(client, document, proposals, expected, mode):
    """The proposals that can go now, read from the Doc: how many wait for a pending
    suggestion in their paragraph, and how many could land somewhere other than the paragraph
    they are meant for (the Doc shows the quote a different number of times than the desk
    counted, or it resolves to a paragraph with other words), which stay on the desk."""
    import google_roundtrip as rt
    import google_suggestions as suggestions
    from google_drive import GoogleError

    inline, _, _ = suggestions.read_for_review(client, document['document_id'], mode)
    free, waiting, unsure = [], 0, 0
    for proposal in proposals:
        found = expected.get(proposal['id']) or {}
        if proposal.get('occurrence') or proposal.get('context'):
            seen = suggestions.quote_positions(
                inline, document['tab_ids'], proposal['before'], proposal.get('context')
            )
            if len(seen) != found.get('matches'):
                unsure += 1
                continue
        try:
            where = suggestions.locate(inline, proposal, document['tab_ids'])
            _, paragraph = rt.paragraph_at(inline, where['tab_id'], where['start_index'])
        except GoogleError:
            free.append(proposal)  # Planning says plainly why it cannot be found.
            continue
        meant = ' '.join((found.get('text') or '').split())
        if rt.suggestions(paragraph):
            waiting += 1
        elif meant and ' '.join(rt.paragraph_text(paragraph).split()) != meant:
            unsure += 1  # It would land in a paragraph with other words.
        else:
            free.append(proposal)
    return free, waiting, unsure


def google_send(root, ident, data):
    """Send a confirmed plan through the existing ledger, once, while the desk text is as
    it was when the plan was made."""
    import google_drive as drive

    import manuscript_editor

    expected = _google_expected(root, ident)
    client = drive.Client(drive.account_for(root))
    result = manuscript_editor.google_send(client, root, ident, data, expected)
    record = _sent(root, ident)
    rows = record['plans'].pop(data.get('plan'), None)
    if rows:
        known = {row.get('id') for row in record['sent']}
        record['sent'] = (record['sent'] + [row for row in rows if row.get('id') not in known])[
            -500:
        ]
        studio.write_json(_sent_path(root, ident), record)
    return result


def repurpose(root, ident, job_id, title, content):
    """Make a repurpose job's output a new desk blog, once: the job's receipt names it."""
    import tool_jobs

    job = tool_jobs.read(root, job_id)
    if job.get('kind') != 'repurpose' or (job.get('metadata') or {}).get('article') != ident:
        raise ValueError('Choose prepared copy from this blog.')
    if job.get('applied'):
        made = job['applied'].get('desk') if isinstance(job['applied'], dict) else None
        if made:
            return made
        raise ValueError('This copy was already saved. Prepare it again for a new blog.')
    if job.get('status') != 'ready':
        raise ValueError('Wait for the prepared copy before making it a blog.')
    if not isinstance(content, str) or not content.strip() or len(content) > desk.LIMIT:
        raise ValueError('Keep the prepared copy, up to 200,000 characters.')
    if not isinstance(title, str) or not title.strip() or '\n' in title.strip() or len(title) > 500:
        raise ValueError('Give the new blog a title of one line, up to 500 characters.')
    source = desk.read(root, ident)
    data = {'title': title.strip(), 'manuscript': content, 'tone': source.get('tone') or ''}
    if source.get('style'):
        try:
            studio.style_check(root, source['style']['style_id'])
            data['style'] = source['style']['style_id']
        except (ValueError, KeyError, TypeError):
            pass  # A retired kind of post: the copy is a blog of no particular kind.
    # The images the copy names come with it, so the new blog does not open without them.
    images = source.get('images') or {}
    if images and desk_images.REFERENCE.search(content):
        held = desk._data(root, ident)
        named = desk_images.written(
            {'title': '', 'opening': content, 'sections': [], 'images': images}
        )
        lines = desk_images.definitions(
            {
                'title': '',
                'opening': content,
                'sections': [],
                'images': {n: images[n] for n in named},
            },
            held,
        )
        if lines:
            data['manuscript'] = content.rstrip() + '\n\n' + '\n\n'.join(lines) + '\n'
    made = desk.create(root, data)
    job['applied'] = {'desk': {'id': made['id'], 'title': made['title']}, 'posted': False}
    job['saved_content'] = content
    tool_jobs.write(root, job)
    return job['applied']['desk']
