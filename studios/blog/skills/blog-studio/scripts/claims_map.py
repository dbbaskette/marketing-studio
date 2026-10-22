"""Check a claims map: each quoted passage belongs to the selected source."""

import re

LINE = re.compile(
    r'^- \*\*(?P<claim>[^\n]+?)\*\* — [^\n]*?\(`(?P<source>[^`\n]+)`\): "(?P<passage>.*?)"[ \t]*(?=\n|\Z)',
    re.MULTILINE | re.DOTALL,
)
FORMAT = 'List at least one claim, one a line, as the guidance shows.'


def _flat(text):
    return ' '.join(str(text).split())


def problems(content, sources):
    texts = {source['id']: _flat(source.get('text') or '') for source in sources}
    matches, said = list(LINE.finditer(content)), []
    for match in matches:
        ident, claim = match['source'], match['claim']
        if ident not in texts:
            said.append(f'"{ident}" is not one of the sources this blog reads.')
        elif not _flat(match['passage']) or _flat(match['passage']) not in texts[ident]:
            said.append(f'The passage for "{claim}" is not in {ident}.')
    # A malformed claim beside a valid one must not evade passage validation.
    unparsed = any(
        not any(match.start() <= row.start() < match.end() for match in matches)
        for row in re.finditer(r'^\s*- \*\*', content, re.MULTILINE)
    )
    if not matches or unparsed or LINE.sub('', content).strip():
        said.append(FORMAT)
    return said
