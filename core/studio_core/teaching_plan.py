"""Optional teaching-plan fields shared by the training and infographic readers."""
import re

POINT = re.compile(r'\bK[1-9]\d*\.[1-9]\d*\b')
CASE = ('Basis', 'Situation', 'Observations', 'Decision', 'Feedback', 'Variation')
START = ('Prerequisite', 'Likely mistake', 'Opening check', 'If missed')
AID = ('Use when', 'Step', 'Evidence', 'Exception')
LABELS = {'Starting point': START, 'Shared case': CASE, 'Job aid': AID}


def sections(text):
    """Read only named level-two sections; older plans have none."""
    result = {}
    current = None
    for line in text.splitlines():
        if line.startswith('## '):
            name = line[3:].strip()
            current = result.setdefault(name, []) if name in LABELS else None
        elif current is not None and line.strip():
            current.append(line.strip())
    return result


def fields(lines, name):
    values = {label: [] for label in LABELS[name]}
    problems = []
    for line in lines:
        label, sep, value = line.partition(':')
        if not sep or label not in values or not value.strip():
            problems.append(f'{name}: expected a labeled value, got {line[:70]}.')
        else:
            values[label].append(value.strip())
    for label, entries in values.items():
        if not entries or (len(entries) > 1 and not (name == 'Job aid' and label == 'Step')):
            problems.append(f'{name}: supply {label} once' +
                            (' or more.' if name == 'Job aid' and label == 'Step' else '.'))
    return values, problems


def problems(blocks, points):
    issues = []
    for name, lines in blocks.items():
        values, invalid = fields(lines, name)
        issues.extend(invalid)
        if name in ('Shared case', 'Job aid'):
            for value in (values['Basis'] if name == 'Shared case' else
                          values['Step'] + values['Evidence'] + values['Exception']):
                refs = POINT.findall(value)
                if not refs or any(ref not in points or points[ref]['unsupported'] for ref in refs):
                    issues.append(f'{name}: cite a teachable blueprint key point for {value[:70]}.')
    return issues


def job_aid(text):
    lines = sections(text).get('Job aid')
    if not lines:
        return None
    values, errors = fields(lines, 'Job aid')
    if errors:
        return None
    def learner_text(value):
        return re.sub(r'\s*\[K[1-9]\d*\.[1-9]\d*(?:,\s*K[1-9]\d*\.[1-9]\d*)*\]', '', value)
    return '\n'.join(['# One-page job aid', '', *values['Use when'], '',
                      *(f'{n}. {learner_text(step)}' for n, step in enumerate(values['Step'], 1)),
                      '', 'Evidence to check', *map(learner_text, values['Evidence']),
                      '', 'Exceptions and limits', *map(learner_text, values['Exception'])]) + '\n'


def alignment(parsed):
    """A planned performance, never a claim about what learners actually achieved."""
    rows = []
    for ident, obj in parsed['objectives'].items():
        modules = [m for m in parsed['modules'].values() if ident in m['objectives']]
        check, _, observe = parsed['assessment'].get(ident, '').partition('| Observe:')
        rows.append((ident, obj['text'], ' '.join(e for m in modules for e in m.get('examples_text', [])),
                     check.removeprefix('Check:').strip(), observe.strip()))
    return rows


def alignment_table(parsed):
    def cell(value):
        return ' '.join(value.split()).replace('|', r'\|') or 'Unspecified'
    return ['| Objective | Evidence or example shown | Learner task | What earns credit |',
            '| --- | --- | --- | --- |',
            *['| ' + ' | '.join(map(cell, (f'{ident} — {objective}', evidence, task, credit))) + ' |'
              for ident, objective, evidence, task, credit in alignment(parsed)]]
