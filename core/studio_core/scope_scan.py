"""Bounded provisional scope shared by the two desk studios; never accepted evidence."""
import re
import hashlib
import math
from functools import lru_cache
from pathlib import Path

SCHEMA = 1
SECONDS, DOLLARS, INPUT_CHARS = 180, 0.25, 48_000


def budget(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - {'seconds', 'dollars', 'input_chars'}:
        raise ValueError('Use seconds, dollars and input_chars for the scan budget.')
    result = {}
    for key, default in (('seconds', SECONDS), ('dollars', DOLLARS), ('input_chars', INPUT_CHARS)):
        number = value.get(key, default)
        if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
            raise ValueError('Scan budgets need finite positive numbers.')
        if key != 'dollars' and (type(number) is not int):
            raise ValueError('Scan seconds and input characters need whole numbers.')
        result[key] = min(default, number)
    return result


@lru_cache(maxsize=256)
def _digest(path, identity):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(path):
    if not path.exists():
        return None
    stat = path.stat()
    return _digest(str(path), (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))


def excerpts(offered, limit=INPUT_CHARS):
    names, pieces, remaining = [], [], min(INPUT_CHARS, max(0, limit))
    for source in offered[:40]:
        name = str(source.get('title') or source.get('file') or 'Source')[:300]
        names.append(name)
        full = str(source.get('text') or '')
        snippet = full[:min(12_000, remaining)]
        remaining -= len(snippet)
        pieces.append({'source': name, 'excerpt': snippet, 'partial': len(snippet) < len(full)})
    return names, pieces


def research_scope(about, sections, field):
    """Bound helper metadata; complete approved scope is a separate host-task field."""
    intro = about.encode('utf-16-le', 'surrogatepass')[:2000].decode('utf-16-le', 'ignore')
    titles = '; '.join(section['title'] for section in sections)
    return intro + '\nApproved sections: ' + titles + '\nUse ' + field + ' for the complete approved scope.'


def text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} needs text of {limit} characters or fewer.')
    return value.strip()


def lines(value, name, most, limit, least=0):
    if not isinstance(value, list) or not least <= len(value) <= most:
        raise ValueError(f'{name} needs {least} to {most} entries.')
    return [text(item, name, limit) for item in value]


def checked(value, minimum=1):
    if not isinstance(value, dict) or set(value) != {'schema', 'overview', 'key_terms', 'coverage', 'gaps', 'sections', 'personal_questions'} or type(value['schema']) is not int or value['schema'] != SCHEMA:
        raise ValueError('Use the complete provisional outline format, schema 1.')
    found = {'schema': SCHEMA, 'overview': text(value['overview'], 'Overview', 2000),
             'key_terms': lines(value['key_terms'], 'Key terms', 20, 120),
             'gaps': lines(value['gaps'], 'Gaps', 20, 600),
             'personal_questions': lines(value['personal_questions'], 'Your questions', 8, 300)}
    coverage = value['coverage']
    if not isinstance(coverage, list) or len(coverage) > 40:
        raise ValueError('Describe at most 40 source coverage entries.')
    found['coverage'] = []
    for item in coverage:
        if not isinstance(item, dict) or set(item) != {'source', 'covers'}:
            raise ValueError('Each coverage entry names source and covers.')
        found['coverage'].append({'source': text(item['source'], 'Source', 300),
                                  'covers': text(item['covers'], 'Coverage', 800)})
    sections = value['sections']
    if not isinstance(sections, list) or not minimum <= len(sections) <= 8:
        raise ValueError(f'Keep {minimum} to 8 sections in the outline.')
    found['sections'], seen = [], set()
    for item in sections:
        if not isinstance(item, dict) or set(item) != {'id', 'title', 'objectives', 'questions'}:
            raise ValueError('Each section needs id, title, objectives and questions.')
        ident = item['id']
        if not isinstance(ident, str) or not re.fullmatch(r'section-[a-z0-9][a-z0-9-]{0,60}', ident) or ident in seen:
            raise ValueError('Give each section its own section- ID.')
        seen.add(ident)
        found['sections'].append({'id': ident, 'title': text(item['title'], 'Section title', 160),
            'objectives': lines(item['objectives'], 'Learning objectives', 6, 500, 1),
            'questions': lines(item['questions'], 'Research questions', 3, 400, 1)})
    return found
