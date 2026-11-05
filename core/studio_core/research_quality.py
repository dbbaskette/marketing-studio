"""Small preflight checks and explicit bounds; never a substitute for source review."""
import re


FOCUSED = {'schema': 1, 'outline_sections': 4, 'facts_per_area': 8, 'sources_per_area': 5, 'section_words': 500}
FOCUSED_GUIDANCE = (
    'Make a focused first teaching draft at the depth the person requested. '
    'Research only claims needed for the approved learning objectives. Prefer supplied '
    'sources and a small set of authoritative originals. Stop when those claims are '
    'supported; do not survey the whole ecosystem. Do not expand introductory scope '
    'into exact operational runbooks, vendor maturity rankings, compliance audits or '
    'quantified cost studies unless explicitly requested. Record unavailable detail '
    'as a gap; do not chase it indefinitely. Practice examples are teaching design, '
    'not a reason to research additional products or personas. '
    'Within the same source and fact budget, look for an existing introductory tutorial, '
    'course, lab or worked example relevant to the assigned objective, first in supplied '
    'material and then on permitted public sites when web research is allowed. Prefer '
    'official or clearly maintained teaching material matching the audience and version. '
    'Stop after finding a suitable example; do not build an exhaustive course catalog. '
    'Explain what it helps teach and its prerequisites. Treat teaching structure and '
    'examples separately from product evidence: check technical claims against authoritative '
    'references. Attribute sources, link to useful lessons, and paraphrase or create original '
    'examples; do not reproduce substantial course content or assume permission to reuse assets. '
)


def valid_policy(value):
    return isinstance(value, dict) and value == FOCUSED and all(type(v) is int for v in value.values())


def evidence(value, policy):
    if not policy:
        return
    if not valid_policy(policy):
        raise ValueError('Restore the saved focused research policy before continuing.')
    for key, limit in (('facts', 'facts_per_area'), ('sources', 'sources_per_area')):
        if isinstance(value.get(key), list) and len(value[key]) > policy[limit]:
            raise ValueError(f'This focused area allows at most {policy[limit]} {key}. '
                             'Keep the essential teaching claims and their complete citations; '
                             'record optional detail as gaps. Do not truncate citations.')


def prose(value, policy=None):
    """Reject whole placeholder blocks, not legitimate uses of words like 'test'."""
    words = 0
    for key in ('sections', 'brief'):
        sections = value.get(key) or []
        if not isinstance(sections, list):
            raise ValueError(f'Return {key} as an array of sections.')
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get('blocks'), list):
                raise ValueError('Return each prose section as an object with a blocks array.')
            for block in section['blocks']:
                if not isinstance(block, dict):
                    raise ValueError('Return each prose block as an object.')
                text = block.get('text')
                if not isinstance(text, str):
                    continue  # Schema validation owns malformed values.
                token = re.sub(r'[\W_]+', ' ', text.casefold()).strip()
                if token in ('test', 'todo', 'tbd', 'placeholder', 'lorem ipsum',
                             'insert text here', 'insert content here', 'coming soon'):
                    raise ValueError('Replace placeholder prose with an authored, cited explanation before submitting.')
                words += len(text.split())
    if policy:
        if not valid_policy(policy):
            raise ValueError('Restore the saved focused research policy before continuing.')
        if words > policy['section_words']:
            raise ValueError(f'Keep this focused contribution within {policy["section_words"]} words. '
                             'Explain the essentials and preserve important limitations; leave optional depth out.')


def coverage(review):
    originals = review.get('originals') or []
    read = sum(item.get('read_original') is True for item in originals)
    return {'read': read, 'total': len(originals), 'unread': len(originals) - read}


class IncompleteCheck(ValueError):
    def __init__(self, coverage):
        self.coverage = coverage
        super().__init__(f'The independent check read {coverage["read"]} of '
                         f'{coverage["total"]} required sources and could not finish. '
                         'Unread does not mean incorrect. Evidence, section drafts and the '
                         'review notes are kept; no new investigation or rewrite was started. '
                         'Retry the independent check after resolving its time, allowance or source-access limit.')
