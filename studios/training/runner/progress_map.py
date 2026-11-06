"""Read-only workflow map, projected from an existing survey and material cards.

No I/O, saved state, worker dispatch or estimated completion. The survey owns
approval truth; cards own availability/readiness and observed writing activity.
"""

WORDS = {'waiting': 'Waiting', 'working': 'Working', 'needs-you': 'Needs you', 'available': 'Review drafts',
         'stopped': 'Stopped', 'complete': 'Complete', 'saved': 'Saved'}
GROUPS = (('reading', 'Plans, guides & briefs', ('blueprint', 'document', 'brief')),
          ('practice', 'Practice & Yoodli', ('scenario', 'yoodli')),
          ('slides', 'Slides', ('deck',)))


def project(record, found, cards, state, sentence, *, queued=False, mine=True):
    conversation = record.get('execution') == 'conversation'
    steps, done = found.steps, found.done
    outline = any(step.id == 'scan' for step in steps)
    has_plan = any(step.id == 'review:training-plan' for step in steps)
    kept = [card for card in cards if card['state'] != 'left-out']
    selected = set((found.session.get('settings') or {}).get('stages', ()))
    selected -= set(found.session.get('unavailable', ()))

    def stage_of(step):
        if step is None:
            return None
        if step.id in ('scan', 'review:training-plan'):
            return 'outline' if outline else 'plan'
        if step.stage in ('intake', 'research-plan', 'research'):
            return 'research'
        if step.stage == 'blueprint' and has_plan and not outline:
            return 'plan'
        return 'review' if step.stage == 'package' else 'materials'

    def entry(ident, label, status, detail, **more):
        return {'id': ident, 'label': label, 'state': status,
                'words': WORDS[status], 'detail': detail, **more}

    def phase(ident, label, detail):
        own = [step for step in steps if stage_of(step) == ident]
        return entry(ident, label, 'complete' if own and all(step.id in done for step in own)
                     else 'waiting', detail)

    def counts(items):
        return {'available': sum(bool(card['seen']) for card in items), 'total': len(items),
                'ready': sum(card['state'] == 'ready' for card in items)}

    def material_state(items):
        states = {card['state'] for card in items}
        if 'writing' in states:
            return 'working'
        if states & {'held', 'needs', 'decide'}:
            return 'needs-you'
        if states & {'queued'} or any(not card['seen'] for card in items):
            return 'waiting'
        return 'complete' if items else 'waiting'

    plans = [step for step in steps if step.stage == 'blueprint']
    scope_known = bool(plans) and all(step.id in done for step in plans)
    branches = []
    for ident, label, kinds in GROUPS:
        items = [card for card in kept if card['kind'] in kinds]
        if items or selected.intersection(kinds):
            empty_practice = ident == 'practice' and not items
            branches.append(entry(ident, label, 'complete' if empty_practice and scope_known else material_state(items),
                ('No practice items in the saved plans.' if scope_known else
                 'Practice items appear after their level plans.') if empty_practice else '',
                **counts(items), materials=[card['name'] for card in items]))
    materials = entry('materials', 'Materials', material_state(kept),
        'Open any saved draft while other work continues. A saved draft is not marked ready.',
        **counts(kept), branches=branches)
    if materials['state'] == 'complete' and any(branch['state'] == 'waiting' for branch in branches):
        materials.update(state='waiting', words='Waiting')
    review_state = ('complete' if kept and all(card['state'] == 'ready' for card in kept)
                    and all(branch['state'] == 'complete' for branch in branches)
                    else 'needs-you' if any(card['seen'] and card['state'] not in
                        ('ready', 'writing', 'queued') for card in kept) else 'waiting')
    if review_state == 'needs-you' and materials['state'] != 'complete':
        review_state = 'available'
    review = entry('review', 'Your review', review_state,
        'You mark each material ready after reviewing it. Writing a draft does not approve it.',
        **counts(kept), materials=[card['name'] for card in kept if card['seen']])
    research = phase('research', 'Research', 'Research uses the saved source scope. '
                     'Independent checking follows evidence collection and section writing.')
    plan = phase('outline' if outline else 'plan', 'Outline' if outline else 'Teaching plan',
                 'Approve the outline before detailed research starts.' if outline else
                 'This saved training reviews its teaching plans after research.')
    stages = ([plan, research] if outline else [research, plan] if has_plan else [research])
    stages = [materials, review] if conversation else [*stages, materials, review]
    by_id = {item['id']: item for item in stages}

    problem = record.get('problem') or {}
    problem_step = str(problem.get('step') or '')
    failed = next((step for step in steps if problem_step and
                   (problem_step == step.id or problem_step.startswith(step.id + ':'))), None)
    current = stage_of(failed or found.next.step)
    # A missing-source wait can precede the scan; it belongs to that starting scope.
    if found.next.kind == 'documents' and outline and plan['state'] != 'complete':
        current = 'outline'
    if current not in by_id:
        current = next((item['id'] for item in stages if item['state'] != 'complete'), 'review')
    active = by_id[current]
    if not conversation and mine:
        if problem or state in ('failed', 'stopped', 'paused'):
            active.update(state='stopped', words='Paused' if state == 'paused' else 'Stopped',
                          detail=problem.get('what') or sentence)
        elif queued:
            active.update(state='waiting', words='Waiting', detail='Waiting for an available assistant slot.')
        elif state == 'waiting' and current != 'review':
            active.update(state='needs-you', words='Needs you', detail=sentence)
        elif state == 'working' and active['state'] != 'complete':
            active.update(state='working', words='Working', detail=sentence)

    progress = (record.get('research_execution') or {}).get('progress') or {}
    research['phase'] = {'investigate': 'Collecting evidence', 'investigating': 'Collecting evidence',
        'synthesize': 'Writing research sections', 'combining-findings': 'Combining findings',
        'review': 'Independent check', 'independent-check': 'Independent check',
        'creator-review': 'Creator decisions', 'check-incomplete': 'Check incomplete'}.get(progress.get('phase'))
    if any(agent.get('section') == 'final' or agent.get('stream') == 'final'
           for agent in (progress.get('agents') or {}).get('active', ())):
        research['phase'] = 'Assembling the research brief'
    research['counts'] = []
    for key, label, accepted in (('streams', 'areas collected', ('kept', 'accepted')),
                                  ('combining', 'section drafts saved', ('kept',))):
        rows = progress.get(key) or (progress.get('workstreams') if key == 'streams' else []) or []
        if rows:
            research['counts'].append({'label': label, 'done': sum(row.get('status') in accepted for row in rows), 'total': len(rows)})
    if progress.get('phase') == 'creator-approved':
        research['warning'] = 'Creator choices are saved. Included uncertainty remains marked; it is not independently verified.'
        if research['state'] == 'complete':
            research['words'] = 'Accepted with flags'

    # Scope a stop to its actual branch; successful peers remain usable.
    if active is materials and active['state'] == 'stopped':
        step = failed or found.next.step
        for branch in branches:
            if step and step.artifact in branch['materials']:
                branch.update(state='stopped', words='Stopped', detail=active['detail'])
    if conversation or not mine:
        for item in [*stages, *branches]:
            if item['state'] == 'working':
                item.update(state='saved', words='Saved')
            if not mine and item['state'] == 'needs-you':
                item['words'] = 'Needs creator'
        current = None
    if not mine:
        review['detail'] = 'The creator marks each material ready. This map shows its saved state.'
    return {'stages': stages, 'current': current,
            'note': 'Retained materials; no work is scheduled here.' if conversation else
                    'Saved progress from another computer; live activity is unavailable.' if not mine else ''}
