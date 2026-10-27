"""The words a desk job is asked with, shared so every studio's desk asks the same way.

`edit_rule(thing)` is the surgical-edit rule a note, a selection or a whole-draft note is
sent with: Blog Studio's `references/modules/desk-edit.md` as it was, with the thing edited
named ("blog draft", "training guide"). The scope sentences and `request` frame the
author's own words as an instruction from the author, never as document data. Each studio
keeps its writing context: guides, kinds of post, tone and sources.
"""

ACTIONS = {
    'rephrase': 'Rewrite the passage in fresh words with the same meaning.',
    'shorten': 'Tighten the passage; use noticeably fewer words.',
    'expand': 'Develop the passage further with one concrete detail, example or consequence '
    'from the sources.',
    'fix': 'Fix grammar, clarity and flow only.',
}
ASK = 'Do what the author asks below with the passage.'
WHOLE = (
    'Revise every section in sections for this pass, with the full draft as context. Return '
    'JSON in content: a list of {"id": ..., "text": ...} for every section in sections, in '
    'order, ids unchanged, each text without its heading. Return a section the pass does not '
    'touch exactly as it was.'
)
REVISE_ONE = (
    'The author left a note for the whole draft. The draft is revised one section at a time, '
    'in order: revise part.text, this section only, for the note. The whole draft is in '
    "sections for context; return only this section's text, without its heading."
)
# How far the author's words reach, for `request`.
SURGICAL = 'Apply it as a surgical edit of part.text and change nothing it does not require.'
SURGICAL_PART = 'Apply it to part.text as a surgical edit and change nothing it does not require.'
FOLLOW = 'Follow it as you write the section.'
ONLY_PASSAGE = 'Apply it to the passage only.'
ALSO_FIX = 'Fix this in the passage as well, and change nothing else.'
EDIT_RULE = (
    '# Desk edits\n'
    '\n'
    'You are editing one part of a {thing} for its author.\n'
    '\n'
    "- Change only what the author's note requires. Reproduce every part the note does not\n"
    '  require changing verbatim, word for word.\n'
    '- Do not restructure, reorder, rephrase, tighten or otherwise improve parts the note does\n'
    "  not mention. Keep the part's length and shape unless the note requires otherwise.\n"
    '- Keep facts, numbers, names, quotations and links. Never invent experience, customers or\n'
    '  results. Where the note asks for something the sources cannot support, write what they\n'
    '  support and add the gap to gaps.\n'
    '- Return only the rewritten part in `content`: no heading, no commentary, no source IDs,\n'
    '  no editorial placeholders. Put each thing the author must supply before publishing in\n'
    '  `gaps`, and each material claim with its source ID and exact passage in `evidence`.'
)


def edit_rule(thing):
    """The surgical-edit rule for one part of `thing` ("blog draft", "training guide")."""
    return EDIT_RULE.replace('{thing}', thing)


def passage_task(line):
    """What a selection job does with its passage: `line`, then return only the passage."""
    return (
        '\n\nAct on the passage only: '
        + line
        + ' Return only the replacement for passage in content; around is its context and '
        'is not returned.\n\n'
    )


def request(label, text, scope, product):
    """The author's words as an instruction from the author, through `product`, fenced so
    they are never read as document data. `scope` says how far they reach."""
    return (
        '\n\nAUTHOR’S '
        + label
        + ', from the author through '
        + product
        + '. '
        + scope
        + '\n"""\n'
        + text
        + '\n"""'
    )
