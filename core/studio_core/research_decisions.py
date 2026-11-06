"""Explicit creator disposition, separate from Harness Research's independent verdict.

The original helper bundle stays untouched. A deterministic consumer copy carries
the creator's choices, dependency exclusions and visible uncertainty labels.
"""
import copy
import hashlib
import json
import re
from urllib.parse import quote

from studio_core import research_contract as rc

OWNER = 'training-studio-creator-research'
STATUS = 'creator-approved'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prose_items(value):
    for section in value.get('sections', []):
        for i, block in enumerate(section['blocks']):
            yield section['id'] + ':' + str(i), block
    for section in value.get('brief') or []:
        for i, block in enumerate(section['blocks']):
            yield 'brief:' + section['id'] + ':' + str(i), block
    for ci, comparison in enumerate(value.get('comparisons') or []):
        for ri, row in enumerate(comparison['rows']):
            for si, cell in enumerate(row['cells']):
                yield f'comparison:{ci}:{ri}:{si}', cell


def flags(value):
    review = value.get('review') or {}
    if not review and value.get('facts') and value.get('findings'):
        return [{'id': 'assessment:unreviewed', 'kind': 'assessment',
            'title': 'Independent check did not finish',
            'text': 'The saved draft has cited evidence, but no completed independent verdict. Including it marks every claim as unverified.',
            'note': 'Include acknowledges this limitation for the whole draft; exclude rejects this draft.',
            'sources': [{'title': s['title'], 'origin': s['origin']} for s in value['sources']]}]
    if not review or review.get('accepted'):
        return []
    result = []
    sources = {row['id']: row for row in value['sources']}
    for row in review.get('originals', []):
        if not row.get('read_original'):
            source = sources[row['source']]
            result.append({'id': 'originals:' + row['source'], 'kind': 'source',
                'title': source['title'], 'text': 'Claims using this source and their dependent passages.',
                'note': row.get('access_error') or 'The independent checker did not read this source.',
                'sources': [{'title': source['title'], 'origin': source['origin']}]})
    lookup = {'facts': {row['id']: row for row in value['facts']},
              'findings': {row['id']: row for row in value['findings']},
              'prose': dict(prose_items(value))}
    facts = lookup['facts']
    def cited(ids):
        found = set()
        for ident in ids:
            if ident in facts:
                found.update(c['source'] for c in facts[ident]['citations'])
            elif ident in lookup['findings']:
                f = lookup['findings'][ident]
                for ref in set(f['support'] + f['counter'] + f['summary']['refs']):
                    found.update(c['source'] for c in facts.get(ref, {}).get('citations', []))
        return [{'title': sources[s]['title'], 'origin': sources[s]['origin']} for s in sorted(found)]
    for group in ('facts', 'findings', 'prose'):
        for row in review.get(group, []):
            if row.get('verdict') == 'supported':
                continue
            item = lookup[group][row['id']]
            result.append({'id': group + ':' + row['id'], 'kind': group,
                'title': {'facts': 'Source claim', 'findings': 'Research finding', 'prose': 'Report passage'}[group],
                'text': item.get('statement') or item.get('text') or item['summary']['text'],
                'note': row['note'], 'verdict': row['verdict'],
                'sources': cited([row['id']] if group != 'prose' else item.get('refs', []))})
    for key in ('coverage', 'usefulness'):
        assessment = review.get('assessment') or {}
        if assessment.get(key) == 'needs-revision':
            result.append({'id': 'assessment:' + key, 'kind': 'assessment',
                'title': 'Overall ' + key + ' limitation', 'text': assessment.get('note', ''),
                'note': 'This applies to the whole draft. Include acknowledges the limitation; exclude rejects this draft.',
                'sources': []})
    return result


class CreatorReview(ValueError):
    def __init__(self, count):
        self.count = count
        super().__init__(f'The research draft is ready for your decision on {count} '
                         'flagged item(s). Choose what to include with a warning or exclude. '
                         'No automatic correction loop was started.')


def resolve(base, choices):
    """Conservative exclusion closure; an included parent never restores a rejected child."""
    items = flags(base)
    if not items or not isinstance(choices, dict) or set(choices) != {row['id'] for row in items} \
            or any(choice not in ('include', 'exclude') for choice in choices.values()):
        raise ValueError('Choose Include with warning or Exclude for every current flag.')
    if any(row['kind'] == 'assessment' and choices[row['id']] == 'exclude' for row in items):
        raise ValueError('This choice rejects the whole draft. Retry correction or change the scope instead.')
    value = copy.deepcopy(base)
    excluded = set()
    uncertain = {s['id'] for s in value['sources']} if choices.get('assessment:unreviewed') == 'include' else set()
    notes = {row['id']: row['note'] for row in items}
    def marked(text):
        return 'Creator included with warning — independent verification is unresolved. ' + text
    def decision(key, dependencies=()):
        if choices.get(key) == 'exclude' or excluded.intersection(dependencies):
            return 'exclude'
        if choices.get(key) == 'include' or uncertain.intersection(dependencies):
            return 'include'
        return None
    for row in value['sources']:
        key = 'originals:' + row['id']
        if choices.get(key) == 'exclude': excluded.add(row['id'])
        if choices.get(key) == 'include': uncertain.add(row['id'])
    kept = []
    for fact in value['facts']:
        action = decision('facts:' + fact['id'], [c['source'] for c in fact['citations']])
        if action == 'exclude': excluded.add(fact['id']); continue
        if action == 'include':
            uncertain.add(fact['id']); fact['statement'] = marked(fact['statement'])
        kept.append(fact)
    value['facts'] = kept
    kept = []
    for finding in value['findings']:
        blocks = [finding['summary'], *finding.get('implications', []),
                  *finding.get('conditions', []), *finding.get('gaps', [])]
        refs = finding['support'] + finding['counter'] + [r for b in blocks for r in b['refs']]
        action = decision('findings:' + finding['id'], refs)
        if action == 'exclude': excluded.add(finding['id']); continue
        if action == 'include':
            uncertain.add(finding['id']); finding['summary']['text'] = marked(finding['summary']['text'])
        kept.append(finding)
    value['findings'] = kept
    for ident, block in prose_items(value):
        action = decision('prose:' + ident, block.get('refs', []))
        if action == 'exclude':
            block.update(text='Omitted by the creator because this passage or its supporting claim was excluded.', refs=[], kind='gap')
        elif action == 'include':
            block['text'] = marked(block['text'])
    if not value['facts'] or not value['findings']:
        raise ValueError('These exclusions leave no usable evidence-backed findings. Retry correction or narrow the scope.')
    value.update(owner=OWNER, status=STATUS)
    value['creator_review'] = {'choices': copy.deepcopy(choices), 'notes': notes,
                               'excluded': sorted(excluded), 'uncertain': sorted(uncertain)}
    return value


def md(text):
    text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return re.sub(r'([\\`*_{}\[\]()#+!|~])', r'\\\1', text).replace('\n', ' ').replace('\r', ' ')


def render(value):
    def refs(ids):
        return ', '.join(f'[{md(ident)}](evidence.md#{ident})' for ident in ids)
    def block(item):
        return md(item['text']) + (f" ({refs(item['refs'])})" if item.get('refs') else '') + '\n\n'
    banner = ('> Creator-approved research with flagged material. The independent check has '
              'not accepted every item. Preserve warnings and qualifications; do not use '
              'excluded claims.\n\n')
    heading = '# ' + md(value['topic']) + '\n\n' + banner
    report, brief, evidence = heading, heading, heading
    for key in ('sections', 'brief'):
        text = ''.join('## ' + md(s['title']) + '\n\n' + ''.join(block(b) for b in s['blocks'])
                       for s in value.get(key) or [])
        if key == 'sections': report += text
        else: brief += text
    for comparison in value.get('comparisons') or []:
        report += '## ' + md(comparison['title']) + '\n\n'
        report += '| Criterion | ' + ' | '.join(map(md, comparison['subjects'])) + ' |\n'
        report += '| --- | ' + ' | '.join('---' for _ in comparison['subjects']) + ' |\n'
        for row in comparison['rows']:
            cells = {c['subject']: c for c in row['cells']}
            report += '| ' + md(row['criterion']) + ' | ' + ' | '.join(
                block(cells[s]).strip() for s in comparison['subjects']) + ' |\n'
        report += '\n'
    for fact in value['facts']:
        evidence += f'<a id="{fact["id"]}"></a>\n## {md(fact["id"])}\n\n{md(fact["statement"])}\n\n'
        for citation in fact['citations']:
            evidence += '> ' + md(citation['quote']) + '\n\nSource: [' + md(citation['source']) + '](#' + citation['source'] + ').\n\n'
    for finding in value['findings']:
        evidence += f'<a id="{finding["id"]}"></a>\n## {md(finding["title"])}\n\n' + block(finding['summary'])
        evidence += 'Supporting facts: ' + refs(finding['support']) + '.\n\n'
        evidence += 'Counterevidence: ' + refs(finding['counter']) + '.\n\n'
        for key in ('conditions', 'implications', 'gaps'):
            for item in finding.get(key, []): evidence += block(item)
    for source in value['sources']:
        origin = source['origin']
        linked = '[Original source](' + quote(origin, safe=':/?=&%#@+;,') + ')' if origin.startswith(('https://', 'http://')) else md(origin)
        evidence += f'<a id="{source["id"]}"></a>\n## {md(source["title"])}\n\n' + linked + '\n\n'
        if source.get('context_note'): evidence += md(source['context_note']) + '\n\n'
        for key in ('snapshot', 'original_snapshot'):
            if source.get(key):
                path = source[key].removeprefix('research/')
                evidence += '[' + ('Saved original' if key == 'original_snapshot' else 'Saved capture') + '](' + quote(path, safe='/') + ')\n\n'
    notes = '## Creator decisions and independent-check notes\n\n'
    for key, choice in value['creator_review']['choices'].items():
        notes += '- ' + md(key) + ': **' + ('Included with warning' if choice == 'include' else 'Excluded') + '**. ' + md(value['creator_review']['notes'][key]) + '\n'
    notes += '\n'
    return {'report.md': report + notes, 'brief.md': brief + notes, 'evidence.md': evidence + notes}


def build(base, choices, inputs):
    value = resolve(base, choices)
    value['digest'] = digest([base, choices, inputs])
    receipt = {'schema': 1, 'base': base, 'choices': choices, 'inputs': inputs}
    files = render(value)
    files.update({'facts.json': json.dumps(value, ensure_ascii=False), 'creator.json': json.dumps(receipt, ensure_ascii=False)})
    return value, files


def publish(source, destination, choices, inputs, expected=None):
    base, original = rc.read_bundle(source, complete=False)
    if expected is not None and expected != digest([base, original]):
        raise ValueError('The reviewed draft changed before saving. Reopen its flags.')
    value, files = build(base, choices, inputs)
    if rc.inside(destination, 'output.json').exists(): rc.read_bundle(destination, complete=False)
    elif any(rc.inside(destination, name).exists() for name in rc.ARTIFACTS):
        raise ValueError('Existing research output has no owned manifest; preserve it.')
    entries = []
    for entry in original['artifacts']:
        if entry['file'] in rc.ARTIFACTS: continue
        data = rc.inside(source, entry['file']).read_bytes()
        rc.write(destination, entry['file'], data); entries.append(entry)
    for name, text in files.items():
        rc.write(destination, name, text)
        entries.append({'file': name, 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    manifest = {'owner': OWNER, 'schema': 2, 'status': STATUS, 'digest': value['digest'], 'artifacts': entries}
    rc.write(destination, 'output.json', json.dumps(manifest))
    return rc.read_bundle(destination)


def validate(root, value, manifest):
    """Hashes alone cannot promote a rejected helper review into creator approval."""
    receipt = json.loads(rc.inside(root, 'creator.json').read_text())
    if receipt.get('schema') != 1 or manifest.get('status') != STATUS:
        raise ValueError('Unrecognized creator decision record.')
    expected, files = build(receipt['base'], receipt['choices'], receipt['inputs'])
    if expected != value:
        raise ValueError('Creator decisions and research describe different revisions.')
    for name, text in files.items():
        if rc.inside(root, name).read_text() != text:
            raise ValueError('Creator-approved research changed. Review the current draft again.')
