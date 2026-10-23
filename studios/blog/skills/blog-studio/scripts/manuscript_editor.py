"""Version-bound local manuscript editing and explicit Google review delivery."""

import difflib
import json
import re
import uuid

import studio
import blog_runner
from text_checks import preserve

CHECKS = {
    'geo': 'Review clarity and citation readiness: point-first openings, consistent entity names, useful definitions, precise citations and self-contained explanations. Locate each finding and explain its practical benefit. Use only supplied evidence; missing evidence becomes a comment, never an invented citation. Preserve qualifiers. Do not promise rankings or citations or force FAQs, keyword density, tables or branded mentions.',
    'polish': 'Proofread and copy edit the manuscript together: correct spelling, grammar, punctuation and consistency; improve clarity and concision; humanize formulaic wording, repetition and unnatural rhythm using the pinned author rules, house style and humanization guidance. Preserve the author voice, stance, facts, quotations, links and meaningful technical qualifiers. Never invent experience or new claims. Return selected, located suggestions rather than rewriting the whole manuscript. Do not research. This is editorial review, not AI detection.',
    'proofread': 'Proofread for clarity, grammar and the pinned author and house rules. Preserve the author voice.',
    'copyedit': 'Suggest precise copy edits for grammar, clarity, concision, consistency and natural wording using the pinned author and house rules. Preserve voice, stance, facts, quotations and technical qualifiers. Do not research or introduce new claims.',
    'factual-support': 'Check exact factual claims against selected evidence. Report supported, unsupported and contradicted claims with source passages; mark unavailable evidence and coverage gaps.',
    'humanization': 'Review formulaic language, repetition and rhythm using the humanization guidance. Preserve the author voice, facts and stance; never invent experience.',
    'shape': 'Review the argument, audience relevance, section order and technical marketing claims. Distinguish optional alternatives from corrections.',
    'revise': 'Apply only the requested edits, preserving the original author voice, stance, meaningful qualifiers and technical precision.',
}


def read(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    path = directory / 'DRAFT.md'
    body = path.read_text() if path.is_file() else ''
    proposals = (
        studio.read_json(directory / 'derived/editor-proposals.json')
        if (directory / 'derived/editor-proposals.json').is_file()
        else []
    )
    expected = studio.digest(json.dumps([record, body, proposals], sort_keys=True).encode())
    base = record.get('google', {}).get('baselines', {}).get('draft')
    baseline = ''
    if base:
        from google_workflow import snapshot_path

        baseline = snapshot_path(directory, base['transfer'], 'document').read_text()
    review = directory / 'derived/blog-review.md'
    operation = None
    if (directory / blog_runner.STATE).is_file():
        shown = blog_runner.engine(root).describe(ident)
        operation = {
            key: shown.get(key)
            for key in ('id', 'expected', 'status', 'error', 'enabled', 'next', 'editor_check')
        }
    checks = studio.freshness(root, directory, record)
    checked = operation.get('editor_check') if operation else None
    if checked in ('revise', 'copyedit'):
        checked = 'proofread'
    findings_from = [checks[checked]] if checked in checks else checks.values()
    return {
        'id': ident,
        'title': record['title'],
        'content': body,
        'expected': expected,
        'google': base.get('document') if base else None,
        'baseline': baseline,
        'proposals': proposals,
        'sources': [item['source_id'] for item in record['sources']],
        'checks': checks,
        'review': review.read_text() if review.is_file() else '',
        'findings': [
            f
            for v in findings_from
            if v.get('status') in ('current', 'unavailable')
            and v.get('inputs', {}).get('draft')
            == studio.artifact_fingerprint(directory, 'DRAFT.md')
            for f in v.get('result', {}).get('findings', [])
        ],
        'diff': list(difflib.unified_diff(baseline.splitlines(), body.splitlines(), lineterm=''))
        if base
        else [],
        'operation': operation,
        'working': blog_runner.engine(root).current == ident
        or bool(operation and operation['status'] in ('working', 'queued')),
    }


def guard(root, data):
    from team_workspace import guard as team_guard

    team_guard(root, data.get('id'))
    current = read(root, data.get('id'))
    if not data.get('expected') or data['expected'] != current['expected']:
        raise ValueError(
            'This manuscript changed. Keep your edits, reload and compare before saving.'
        )
    if current['working']:
        raise ValueError('Pause or stop the current writing step before editing this manuscript.')
    return current


def proposal(value):
    if not isinstance(value, dict) or set(value) - {
        'id',
        'before',
        'after',
        'reason',
        'kind',
        'context',
    }:
        raise ValueError('Use a quote, replacement and reason for each suggestion.')
    result = dict(value)
    result.setdefault('id', uuid.uuid4().hex)
    if not isinstance(result['id'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}', result['id']):
        raise ValueError('Invalid suggestion ID.')
    for name, limit in [('before', 10000), ('reason', 1000)]:
        if (
            not isinstance(result.get(name), str)
            or not result[name].strip()
            or len(result[name]) > limit
        ):
            raise ValueError('Provide the original quote and a concise reason.')
    if result.get('context') == '':
        result.pop('context')
    if 'context' in result and (
        not isinstance(result['context'], str)
        or result['before'] not in result['context']
        or len(result['context']) > 20000
    ):
        raise ValueError(
            'Surrounding text must contain the exact quote and be at most 20,000 characters.'
        )
    if result.get('kind') not in ('edit', 'comment'):
        raise ValueError('Choose a suggested edit or comment.')
    if result['kind'] == 'edit' and (
        not isinstance(result.get('after'), str) or len(result['after']) > 10000
    ):
        raise ValueError('Provide a replacement; empty text means deletion.')
    if result['kind'] == 'comment':
        result.pop('after', None)
    return result


def dispatch(root, action, data):
    current = guard(root, data)
    ident = current['id']
    directory, record = studio.item(root, 'articles', ident)
    if action in ('save', 'apply-proposal', 'apply-selected'):
        operation = current.get('operation') or {}
        if operation.get('editor_check') and operation.get('status') == 'waiting-for-approval':
            # Older page runs kept their worker enabled at the review gate.
            # Applying chosen feedback completes that pass, including on old runs.
            blog_runner.engine(root).control(ident, 'pause')
    if action == 'save':
        body = data.get('content')
        if not isinstance(body, str) or not body.strip() or len(body) > 200000:
            raise ValueError('Save a nonempty manuscript up to 200,000 characters.')
        result = preserve(current['content'], body)
        studio.save_artifact(directory, 'draft', body, record, 'Local manuscript edit')
        studio.persist(directory, 'articles', record)
        return {**read(root, ident), 'preservation': result}
    if action == 'apply-proposal':
        selected = next(
            (item for item in current['proposals'] if item['id'] == data.get('proposal')), None
        )
        if not selected or selected['kind'] != 'edit':
            raise ValueError('Choose a saved suggested replacement.')
        anchor = selected.get('context') or selected['before']
        if current['content'].count(anchor) != 1 or anchor.count(selected['before']) != 1:
            raise ValueError(
                'This quote is missing or ambiguous in the current draft. Edit the passage locally and compare it; no text was changed.'
            )
        body = current['content'].replace(
            anchor, anchor.replace(selected['before'], selected['after'], 1), 1
        )
        if not body.strip():
            raise ValueError('A suggestion cannot remove the entire manuscript.')
        result = preserve(current['content'], body)
        studio.save_artifact(directory, 'draft', body, record, 'Apply selected local suggestion')
        studio.persist(directory, 'articles', record)
        return {**read(root, ident), 'preservation': result}
    if action == 'apply-selected':
        chosen = data.get('proposals')
        if not isinstance(chosen, list) or not chosen or len(set(chosen)) != len(chosen):
            raise ValueError('Choose the saved edits to apply.')
        entries = {item['id']: item for item in current['proposals']}
        if any(value not in entries or entries[value]['kind'] != 'edit' for value in chosen):
            raise ValueError('Choose saved suggested replacements only.')
        spans = []
        body = current['content']
        for value in chosen:
            entry = entries[value]
            anchor = entry.get('context') or entry['before']
            if body.count(anchor) != 1 or anchor.count(entry['before']) != 1:
                raise ValueError(
                    'A selected quote is missing or ambiguous. Review the manuscript; no edits were applied.'
                )
            start = body.index(anchor) + anchor.index(entry['before'])
            spans.append((start, start + len(entry['before']), entry['after']))
        spans.sort()
        if any(left[1] > right[0] for left, right in zip(spans, spans[1:], strict=False)):
            raise ValueError(
                'Selected edits overlap. Choose one alternative for each passage; no edits were applied.'
            )
        for start, end, replacement in reversed(spans):
            body = body[:start] + replacement + body[end:]
        if not body.strip():
            raise ValueError('Selected edits cannot remove the entire manuscript.')
        result = preserve(current['content'], body)
        studio.save_artifact(directory, 'draft', body, record, 'Apply selected writing edits')
        studio.persist(directory, 'articles', record)
        return {**read(root, ident), 'applied': len(spans), 'preservation': result}
    if action == 'changes':
        if not current['google']:
            raise ValueError('This manuscript has no Google baseline.')
        before, after = current['baseline'].splitlines(), current['content'].splitlines()
        values = list(current['proposals'])
        for tag, a, b, c, d in difflib.SequenceMatcher(
            None, before, after, autojunk=False
        ).get_opcodes():
            if tag == 'equal':
                continue
            if b - a != 1 or d - c > 1 or not before[a].strip():
                raise ValueError(
                    'Some edits change paragraph structure. Keep those as quoted comments or individual suggestions; no partial conversion was saved.'
                )
            old, new = before[a], after[c] if d > c else ''
            left = 0
            while left < min(len(old), len(new)) and old[left] == new[left]:
                left += 1
            tail = 0
            while tail < min(len(old), len(new)) - left and old[-tail - 1] == new[-tail - 1]:
                tail += 1
            while left and old[left - 1].isalnum():
                left -= 1
            while tail and old[len(old) - tail].isalnum():
                tail -= 1
            quoted, replacement = old[left : len(old) - tail], new[left : len(new) - tail]
            if not quoted or any(character in quoted + replacement for character in '[]*`<>'):
                raise ValueError(
                    'This change includes insertion-only text or formatting. Add an individual quoted suggestion or comment; no partial conversion was saved.'
                )
            if not any(
                item.get('before') == quoted and item.get('after') == replacement for item in values
            ):
                values.append(
                    proposal(
                        {
                            'kind': 'edit',
                            'before': quoted,
                            'after': replacement,
                            'reason': 'Proposed wording from the locally edited manuscript.',
                        }
                    )
                )
        if len(values) > 100:
            raise ValueError('Select at most 100 changes per delivery.')
        studio.write_json(directory / 'derived/editor-proposals.json', values)
        return read(root, ident)
    if action == 'proposals':
        values = data.get('proposals')
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError('Keep at most 100 selected suggestions.')
        values = [proposal(v) for v in values]
        if len({v['id'] for v in values}) != len(values):
            raise ValueError('Suggestion IDs must be unique.')
        studio.write_json(directory / 'derived/editor-proposals.json', values)
        return read(root, ident)
    if action == 'check':
        check = data.get('check')
        if check not in CHECKS or not current['content']:
            raise ValueError('Save a manuscript and choose a listed editing action.')
        scope = data.get('request', '')
        if not isinstance(scope, str) or len(scope) > 8000:
            raise ValueError('Use an editing request up to 8,000 characters.')
        research = data.get('research', 'none')
        if research not in ('none', 'supplied-only', 'web-allowed'):
            raise ValueError('Choose a research scope.')
        if check in ('polish', 'proofread', 'copyedit'):
            research = 'none'
        if 'sources' in data:
            selected = data['sources']
            if (
                not isinstance(selected, list)
                or len(selected) > 50
                or len(set(selected)) != len(selected)
            ):
                raise ValueError('Choose at most 50 different sources.')
            pins = []
            for source_id in selected:
                _, source = studio.item(root, 'sources', source_id)
                pins.append(
                    {
                        'source_id': source_id,
                        'revision': source['revision'],
                        'purposes': source['purposes'],
                    }
                )
            record['sources'] = pins
        state = directory / blog_runner.STATE
        if state.is_file():
            research = blog_runner.research_scope(research, record['sources'])
            _, _, run = blog_runner.load(root, ident)
            run['approval'] = 'page'
            run['mode'] = 'revise' if check == 'revise' else 'review'
            run['existing'] = True
            # History is retained by save; old decisions cannot approve this new operation.
            run['pipeline'] = (['research-plan', 'research'] if research != 'none' else []) + (
                ['draft', 'review'] if check == 'revise' else ['review']
            )
            run['stages'] = {}
            record['research_policy'] = 'supplied-only' if research == 'none' else research
            # The editor's research words replace the blog's choice; it reads them.
            record.pop('research_from', None)
            if research != 'none':
                from studio_core import research_contract

                contract = research_contract.snapshot()
                if contract:
                    run['research_contract'] = contract
                    run['schema'] = 3
        else:
            blog_runner.create(
                root,
                {
                    'id': ident,
                    'mode': 'review',
                    'goal': 'Edit the saved manuscript',
                    'audience': record.get('writing_preferences', {}).get('audience')
                    or 'The manuscript’s intended readers',
                    'research': research,
                    'stop': 'review',
                    'sources': data.get(
                        'sources', [item['source_id'] for item in record['sources']]
                    ),
                },
                'page',
            )
            _, record, run = blog_runner.load(root, ident)
            if check == 'revise':
                run['mode'] = 'revise'
                run['pipeline'].insert(run['pipeline'].index('review'), 'draft')
        run['editor_check'] = check
        run['editor_request'] = CHECKS[check] + '\n' + scope
        run['stages'][run['pipeline'][0]] = {'status': 'pending', 'request': run['editor_request']}
        blog_runner.save(root, directory, record, run, 'Requested ' + check)
        return blog_runner.engine(root).control(ident, 'resume')
    if action in ('google-plan', 'google-send'):
        import google_drive as drive
        import google_suggestions as suggestions

        client = drive.Client(drive.account_for(root))
        if action == 'google-plan':
            if not current['google']:
                raise ValueError('Open a linked Google manuscript before sending suggestions.')
            mode = data.get('mode', 'auto')
            token = uuid.uuid4().hex
            path = studio.inside(drive.staging_root(root, create=True), 'editor-' + token + '.json')
            result = suggestions.plan(
                client, root, ident, 'draft', current['proposals'], path, mode
            )
            studio.write_json(
                path.with_suffix('.guard.json'), {'expected': current['expected'], 'id': ident}
            )
            return {
                'plan': token,
                'mode': result['mode'],
                'count': result['findings'],
                'target': current['google']['url'],
                'expected': current['expected'],
                'proposals': current['proposals'],
            }
        token = data.get('plan', '')
        if (
            not isinstance(token, str)
            or not re.fullmatch('[a-f0-9]{32}', token)
            or data.get('confirmed') is not True
        ):
            raise ValueError('Preview and confirm the selected Google suggestions first.')
        path = studio.inside(drive.staging_root(root), 'editor-' + token + '.json')
        bound = studio.read_json(path.with_suffix('.guard.json'))
        if bound != {'expected': current['expected'], 'id': ident}:
            raise ValueError('The selected edits changed. Preview Google delivery again.')
        saved = studio.read_json(path)
        if saved['article'] != ident:
            raise ValueError('This plan belongs to another manuscript.')
        # Existing CLI ledger handles safe retries and uncertain writes; never blindly resend.
        receipt = suggestions.ledger(root) / (suggestions.operation_key(saved) + '.json')
        if receipt.is_file():
            return suggestions.verify(client, root, saved)
        return suggestions.apply(client, root, saved)
    raise ValueError('Unknown manuscript action.')


def validate_review(result, manuscript):
    """Validate generated feedback without changing the manuscript or review records."""
    prefix = 'The editing review did not return valid, located findings: '

    def invalid(detail):
        return ValueError(prefix + detail + ' Your manuscript is unchanged.')

    try:
        value = json.loads(result['content'])
    except (ValueError, KeyError, TypeError):
        raise invalid('the response must contain a JSON review object.') from None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get('summary'), str)
        or not value['summary'].strip()
    ):
        raise invalid('provide a nonempty summary of coverage and limits.')
    if not isinstance(value.get('findings'), list) or len(value['findings']) > 100:
        raise invalid('findings must be an array of at most 100 changes.')
    findings, issues, ids = [], [], set()
    for index, item in enumerate(value['findings'], 1):
        try:
            if not isinstance(item, dict):
                raise ValueError('the finding must be an object.')
            if item.get('verdict') not in (
                'supported',
                'unsupported',
                'contradicted',
                'editorial',
            ) or not isinstance(item.get('evidence'), str):
                raise ValueError('provide a listed verdict and an evidence explanation.')
            finding = proposal({k: v for k, v in item.items() if k not in ('evidence', 'verdict')})
            if finding['before'] not in manuscript:
                raise ValueError(
                    'before is not an exact manuscript quote; copy its punctuation, whitespace and Markdown exactly, or choose a shorter contiguous passage.'
                )
            if finding['id'] in ids:
                raise ValueError('use a unique finding ID.')
            ids.add(finding['id'])
            findings.append({**finding, 'evidence': item['evidence'], 'verdict': item['verdict']})
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            issues.append('Change ' + str(index) + ': ' + str(error))
    if issues:
        raise invalid(' '.join(issues))
    return value, findings


def record_review(root, directory, record, run, result):
    """Store scoped assistant findings with exact input pins, never a fabricated tool verdict."""
    value, findings = validate_review(result, (directory / 'DRAFT.md').read_text())
    check = 'proofread' if run['editor_check'] in ('revise', 'copyedit') else run['editor_check']
    status = 'current'
    if (
        check in ('factual-support', 'geo')
        and not studio.ready_evidence(root, record)
        and not run['stages'].get('research')
    ):
        status = 'unavailable'
    research_digest = None
    if (
        check in ('factual-support', 'geo')
        and run['stages'].get('research')
        and run.get('research_contract')
    ):
        from studio_core import research_contract

        _, manifest = research_contract.read_bundle(directory / 'research')
        research_digest = manifest['digest']
    old = record['reviews'].get(check)
    if old:
        studio.write_json(
            directory / 'history' / ('review-' + check + '-' + uuid.uuid4().hex + '.json'), old
        )
    record['reviews'][check] = {
        'status': status,
        'inputs': studio.fingerprints(root, directory, record),
        'checked_at': studio.now(),
        'result': {
            'findings': findings,
            'coverage': value['summary'],
            'research_digest': research_digest,
            'method': 'Assistant assessment of supplied inputs; no independent live verification is implied.',
        },
    }
    lines = ['# Editing review', '', value['summary'], '', 'Check status: ' + status]
    for finding in findings:
        lines += [
            '',
            '## ' + finding['id'],
            '',
            '> ' + finding['before'],
            '',
            finding['reason'],
            '',
            'Evidence: ' + finding['evidence'],
            '',
            'Assessment: ' + finding['verdict'],
        ]
        if finding['kind'] == 'edit':
            lines += ['', 'Suggested replacement: ' + finding['after']]
    return {'content': '\n'.join(lines), 'notes': result['notes']}
