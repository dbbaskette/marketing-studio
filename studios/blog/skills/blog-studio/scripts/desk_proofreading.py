"""The desk's Quick check (proofread): mechanical checks in process, no job.

Part of desk_finish, which keeps every name its callers use.
"""

import desk
from studio_core.drafting import proofread as quick
from desk_proposals import (
    json_text,
)


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

    draft = desk.read(root, ident)
    found = quick.check(
        draft,
        proof_rules(),
        _listed('sentence-starters.txt'),
        ident,
        join=lambda draft: desk.join(draft, images=False),
        lint=text_checks.lint,
    )
    import desk_jobs

    extra, _ = desk_jobs._context(root, draft)
    research, _ = desk_jobs._research_extra(root, ident)
    allowed = [source['text'] for source in extra.get('sources', [])]
    allowed += [str(value) for value in (draft.get('brief') or {}).values()]
    allowed += [draft['title'], draft.get('opening_brief', ''), json_text(research)]
    allowed += [s.get('brief', '') for s in draft['sections']]
    start = desk.read_start(root, ident) or {}
    allowed += [start.get('notes', '')]
    hits = []
    for part, _, text in quick.offsets(draft):
        for hit in text_checks.reader_facing_notes(text):
            target = hit['target']
            at = hit['start']
            if at >= 0:
                item = quick.finding(part, text, 'reader-facing-note', at, target)
                item.update(
                    label='Source ID or editorial note in the writing.',
                    fix='Keep source IDs and editorial notes outside reader-facing text.',
                )
                hits.append(item)
        copied = text_checks.carried_over(text, extra.get('examples', []), allowed)['findings']
        for hit in copied:
            target = hit['target']
            at = hit['start']
            if at >= 0:
                item = quick.finding(part, text, 'from-example', at, target)
                item.update(
                    label='Passage carried over from an example.',
                    fix='Use the example for shape; support claims with your sources.',
                )
                hits.append(item)
    findings = found['findings'] + hits
    order = {part: number for number, (part, _, _) in enumerate(quick.offsets(draft))}
    findings.sort(key=lambda item: (order.get(item['part'], 0), item['at'], item['rule']))
    found.update(
        findings=findings[:PROOF_LIMIT], more=found['more'] + max(0, len(findings) - PROOF_LIMIT)
    )
    return found
