"""Validated story proposals: preserve requirements before any image work."""
from __future__ import annotations

from copy import deepcopy

from . import evidence
from .contracts import Invalid
from .validation import KINDS, records, require, text, validate_project


def verify(project: dict, proposals: list[dict]) -> list[dict]:
    stories = records(proposals, 'Stories')
    require(1 <= len(stories) <= (1 if project['brief']['direction'] == 'direct' else 3),
            'Directed work needs one faithful story; other modes offer one to three useful alternatives.')
    requirements = {item['id'] for item in project['brief']['must_show']}
    facts = {fact['id']: fact for fact in project['facts']}
    signatures = set()
    for story in stories.values():
        require(all(text(story.get(k)) for k in ('headline', 'takeaway', 'rationale')),
                'Explain the story, takeaway and choice of visual form.')
        blocks = records(story.get('blocks'), 'Story blocks')
        require(1 <= len(blocks) <= 5, 'Use one to five primary blocks; prioritize required material before building.')
        require(isinstance(story.get('qualifications'), list) and all(text(q) for q in story['qualifications']),
                'Record source qualifications, including unresolved factual gaps.')
        covered, visual_signature, words = set(), [], [story['headline'], story['takeaway']]
        for block in blocks.values():
            require(text(block.get('title')) and text(block.get('text')), 'Give every story block a title and content.')
            require(block.get('kind') in KINDS, 'Choose a supported visual explanation.')
            require(isinstance(block.get('fact_ids'), list) and bool(block['fact_ids'])
                    and all(key in facts for key in block['fact_ids']), 'Each story block needs captured evidence.')
            require(isinstance(block.get('required_ids'), list) and all(key in requirements for key in block['required_ids']),
                    'Map required content to existing requirement IDs.')
            require(type(block.get('illustration')) is bool and text(block.get('illustration_role'), empty=True),
                    'Say whether artwork helps and describe its explanatory role.')
            if block['illustration']:
                require(bool(block['illustration_role'].strip()), 'Describe what the illustration should explain.')
            used = [facts[key] for key in block['fact_ids']]
            if evidence.quantitative(block, used):
                evidence.comparable(used)
            if block['kind'] == 'timeline':
                require(all(text(facts[key].get('period')) for key in block['fact_ids']),
                        'A timeline needs supplied dates or periods, not invented chronology.')
            covered.update(block['required_ids'])
            words.extend((block['title'], block['text']))
            visual_signature.append((block['kind'], tuple(block['fact_ids']), block['text']))
        omissions = story.get('omissions', [])
        require(set(omissions) == requirements - covered, 'List every omitted required idea before building.')
        if project['brief']['direction'] == 'hybrid':
            require(not omissions, 'Hybrid suggestions must retain the required ideas; ask the user to prioritize first.')
        combined = '\n'.join(words)
        require(all(exact in combined for exact in project['brief']['locked_words']),
                'Preserve every locked phrase exactly in the proposed story.')
        require(not any(excluded.casefold() in combined.casefold() for excluded in project['brief']['exclusions']),
                'The story contains content the brief excludes.')
        require(len(combined.split()) <= 250, 'This story will crowd one page. Ask which content to combine or remove.')
        signature = tuple(visual_signature)
        require(signature not in signatures, 'Offer a different explanation or structure, not a palette-only alternative.')
        signatures.add(signature)
    candidate = deepcopy(project)
    candidate.update(stories=proposals, selected_story=None, scene=None, image_briefs=[],
                     attempts=[], checks=[], approval=None)
    validate_project(candidate)
    return deepcopy(proposals)


def usable_proposals(project: dict, proposals: list[dict]) -> list[dict]:
    """Keep useful generated alternatives when another fails native validation.

    Manual authoring remains strict. Every accepted proposal passes the complete
    checks, including requirements and uniqueness, without another assistant call.
    """
    records(proposals, 'Stories')
    require(1 <= len(proposals) <= (1 if project['brief']['direction'] == 'direct' else 3),
            'Directed work needs one faithful story; other modes offer one to three useful alternatives.')
    accepted, problems = [], []
    for proposal in proposals:
        try:
            verified = verify(project, accepted + [proposal])
        except Invalid as failure:
            problems.append(str(failure))
        else:
            accepted = verified
    require(bool(accepted), problems[0] if problems else 'No usable story was proposed.')
    return accepted


def adopt(store, ident: str, proposals: list[dict], *, expected_revision: int) -> dict:
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        return store.change_locked(project, {'stories': verify(project, proposals)})


def select(store, ident: str, story_id: str, *, expected_revision: int) -> dict:
    with store.locked():
        project = store.read(ident)
        store.expect(project, expected_revision)
        story = next((s for s in project['stories'] if s['id'] == story_id), None)
        require(story is not None, 'Choose an existing proposed story.')
        require(not story.get('omissions'), 'Resolve required omissions or explicitly change the brief before building.')
        return store.change_locked(project, {'selected_story': story_id})
