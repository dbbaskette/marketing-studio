"""Grouped, revision-bound reviews for new runs; legacy gates remain unchanged."""
from pathlib import Path
import shutil

import home
import workspace
from workspace import WorkspaceError
from studio_core import deck_direction, research_view, review_policy
from runner import pipeline, deck, worker_tools

PREPARED = ('research-plan', 'research', 'blueprint', 'document', 'brief')
DECK_PREPARED = ('deck-handoff', 'deck-brand', 'deck-outline', 'deck-look')


def contained(root, relative):
    file = workspace.managed(root, relative)
    if root.resolve() not in file.resolve().parents:
        raise WorkspaceError('Review files must stay inside this training folder.')
    return file


def contents(root, session, run, phase):
    """Only stable inputs and file hashes, never display/approval timestamps."""
    values = {'settings': session['settings'], 'levels': session['levels'],
              'policy': run['review_policy'], 'files': {}, 'inputs': {}}
    for name in workspace.artifact_names(root, session):
        spec = workspace.artifact(root, session, name)
        if phase == 'direction' and spec['stage'] not in ('intake', *PREPARED):
            continue
        file = contained(root, spec['file'])
        values['files'][name] = workspace.sha256_file(file)
        values['files']['review:' + name] = workspace.sha256_file(
            contained(root, workspace.review_file(name)))
        values['inputs'][name] = (session['artifacts'].get(name) or {}).get('built_from')
    for level in session['levels'] or [None]:
        for relative in (pipeline.OUTLINE, pipeline.DESIGN,
                         *([pipeline.SHOWS] if phase == 'final' else [])):
            values['files'][f'{level}:{relative}'] = workspace.sha256_file(
                contained(root, f'{workspace.prefix(level)}{relative}'))
        if phase == 'direction':
            values['files'][f'{level}:sample'] = workspace.sha256_file(
                contained(root, f'{workspace.prefix(level)}work/review-sample/sample.png'))
            # The looks the brand drew are part of what is approved with the direction. Only
            # when there are any: a review approved before looks were offered stays approved.
            shown = pipeline.read_built(root, level).get('look') or {}
            if shown.get('folder') or shown.get('failed'):
                values['files'][f'{level}:looks'] = [shown.get('folder'), shown.get('outline'),
                                                     shown.get('failed')]
    return values


def signature(root, session, run, phase):
    return review_policy.fingerprint(contents(root, session, run, phase))


def group(root, session, run, listed, done):
    """Prepare all levels before direction; complete all levels before final review."""
    mode = review_policy.level(run)
    prep, build, package = [], [], []
    for step in listed:
        if step.id == 'package':
            package.append(step)
        elif (step.stage in ('intake', 'research-plan', 'research', 'blueprint')
              or step.stage in ('document', 'brief') and not step.id.startswith('copies:')
              or pipeline.bare(step.id) in DECK_PREPARED):
            prep.append(step)
        else:
            build.append(step)
    completed = set(done)
    samples = []
    if mode == 'balanced':
        for step in prep:
            if pipeline.bare(step.id) != 'deck-outline':
                continue
            level = workspace.split(step.artifact)[1]
            ident = workspace.qualify('review-sample', level)
            samples.append(pipeline.Step(ident, 'code', 'Draw a sample slide',
                                         'Drawing a sample slide', 'review', step.artifact))
            built = pipeline.read_built(root, level)
            brand = built.get('brand') or {}
            saved = (run.get('review_samples') or {}).get(level or '') or {}
            # A brand that drew its looks shows them instead: no cover is drawn for it.
            if (built.get('look') or {}).get('looks') and (built.get('look') or {}).get(
                    'outline') == workspace.sha256_file(pipeline.place(root, level,
                                                                       pipeline.OUTLINE)):
                completed.add(ident)
                continue
            # The sample is done when it was drawn from this brand and this outline, or
            # when drawing it from them failed and the review carries the note instead.
            drawn = saved.get('image') and saved['image'] == workspace.sha256_file(
                pipeline.place(root, level, 'work/review-sample/sample.png'))
            noted = saved.get('problem') and not saved.get('image')
            if saved.get('brand') == brand.get('sha256') and saved.get('outline') == workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE)) \
                    and (drawn or noted):
                completed.add(ident)
    boundaries = {}
    for phase in ('direction', 'final'):
        ident = 'review:' + phase
        label = 'Review the first drafts' if phase == 'direction' else 'Review the finished materials'
        boundaries[phase] = pipeline.Step(ident, 'review', label,
                                           'Waiting for you to ' + label.lower(), 'review')
        accepted = (run.get('review_decisions') or {}).get(phase) or {}
        if accepted.get('signature') == signature(root, session, run, phase):
            completed.add(ident)
    return tuple([*prep, *samples, *([boundaries['direction']] if mode == 'balanced' else []),
                  *build, boundaries['final'], *package]), frozenset(completed)


def rewritten(root, session, decks, target):
    """What is written again when `target` changes: every artifact downstream of it, and
    the deck direction of each level whose deck is. A practice scenario is built from
    nothing else, so a change to the research never rewrites one."""
    names = workspace.artifact_names(root, session)
    above = {name: set(workspace.artifact(root, session, name)['upstream']) for name in names}
    for level in decks:
        # What a deck says is written from what its deck is built from.
        above['outline:' + (level or '')] = set(above.get(workspace.qualify('deck', level), ()))
        above[workspace.qualify('deck', level)] = {'outline:' + (level or '')}
    below, found = {target}, True
    while found:
        found = False
        for name, inputs in above.items():
            if name not in below and inputs & below:
                below.add(name)
                found = True
    below.discard(target)
    return below


def commits(root, session, decks, phase):
    """What approving a review commits to: for the first drafts, the materials of every level
    not yet written (what was written before the stop is in `PREPARED`) and the deck, with
    the fixed estimate for a deck of this size. The final review commits to nothing more: it
    finishes the draft."""
    if phase != 'direction':
        return None
    slides = sum(len(deck.slides_of(mine.outline)) for mine in decks.values())
    before = deck.before(slides) if slides else {}
    return {'levels': len(session['levels'] or [None]),
            'materials': [stage for stage in pipeline.wanted(session)
                          if stage != 'deck' and stage not in PREPARED],
            'deck': bool(decks),
            'dollars': before.get('dollars'), 'minutes': before.get('minutes')}


def outline_text(shown):
    lines = []
    for number, slide in enumerate(shown['slides'], 1):
        lines += [f"### {number}. {slide.get('title') or 'Untitled'}", '']
        for key in ('understand', 'notes'):
            if slide.get(key):
                lines += [str(slide[key]), '']
        for point in slide.get('points') or ():
            lines.append('- ' + (str(point.get('text') or point.get('label') or '')
                                 if isinstance(point, dict) else str(point)))
        design = slide.get('design') or {}
        if design.get('drawn'):
            lines += ['', 'Visual direction: ' + str(design['drawn'])]
    lines += ['', '### Checked for you', *('- ' + str(line) for line in shown['checked']),
              '', '### Worth reviewing', *('- ' + str(line) for line in shown['worth'])]
    return '\n'.join(lines)


class Reviewing:
    def _policy_accept(self, root, step):
        with self.files:
            record = self._load(root)
            if not review_policy.automatic(record, 'training', step.id):
                raise WorkspaceError('This step needs your review.')
            session = workspace.load(root)
            spec = workspace.artifact(root, session, step.artifact)
            digest = workspace.sha256_file(contained(root, spec['file']))
            self.deck_decided(root, step.artifact, 'approve',
                              'Continued under the saved review level.', digest)
            outcome = workspace.accept_policy(root, step.artifact, record['review_policy'])
            # deck_decided may have stored a receipt in the run.
            record = self._load(root)
            review_policy.receipt(record, step.id, outcome['approved'], home.now())
            self._store(root, record)
            self._commit(root, f'continue {workspace.label(step.artifact)} under the saved review level')

    def _policy_outline(self, root, found):
        if found.next.kind != 'outline':
            return
        with self.files:
            record = self._load(root)
            level = self._level(found.next.step)
            kept = self._decided(record, level)
            waiting = kept.get('waiting') or {}
            asked = waiting.get('design')
            if asked:
                self._answer(root, level, asked, 'approve',
                             'Continue under the user-selected review level.', 'the deck direction')
            approved = {'sha256': waiting['sha256'], 'by': 'review-policy', 'at': home.now()}
            if asked:
                approved['design'] = {'sha256': asked['sha256'], 'revision': asked['revision']}
            kept.update(approved=approved, waiting=None)
            review_policy.receipt(record, found.next.step.id, approved, home.now())
            self._store(root, record)
            self._commit(root, 'continue the deck direction under the saved review level')

    def _review_sample(self, root, found, step):
        """Draw one sample slide for the combined direction review. A sample that cannot
        be drawn is a note on the review, not a halt: the direction can be read without
        it, and the slides are drawn and reviewed after it is approved."""
        level = workspace.split(step.artifact)[1]
        mine = found.decks[level]
        try:
            self._draw_sample(root, found, level, mine)
        except (WorkspaceError, OSError, ValueError) as failure:
            why = str(failure).strip() or type(failure).__name__
            shutil.rmtree(contained(root, f'{workspace.prefix(level)}work/review-sample'),
                          ignore_errors=True)
            with self.files:
                record = self._load(root)
                record.setdefault('review_samples', {})[level or ''] = {
                    'brand': (mine.built.get('brand') or {}).get('sha256'),
                    'outline': workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE)),
                    'image': None, 'problem': why}
                self._store(root, record)
                self._commit(root, 'note that no sample slide could be drawn for the '
                                   'combined direction review')

    def _draw_sample(self, root, found, level, mine):
        tool, contract = self.slides(), pipeline.contract(root, mine)
        slides = deck.slides_of(mine.outline)
        cover = next((slide for slide in slides if slide.get('kind') == 'cover'),
                     {'id': 'cover', 'kind': 'cover', 'title': found.session['title']})
        laid = {'id': cover['id'], 'title': cover.get('title') or found.session['title'],
                'layout': deck.layouts(tool.layouts(contract).get('layouts'), [cover])['cover'],
                'sources': ['outline'], 'brief': {'rhythm': 'anchor'}}
        if cover.get('subtitle'):
            laid['subtitle'] = cover['subtitle']
        folder = contained(root, f'{workspace.prefix(level)}work/review-sample')
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        home.write_json(folder / 'composition.json', {
            'version': 1, 'title': found.session['title'],
            'direction': deck_direction.of_file(contract) or dict(deck.DIRECTION),
            'slides': [laid]})
        tool.compile(folder / 'composition.json', contract, folder=folder / 'compiled')
        shown = worker_tools.render(tool, folder / 'compiled', folder / 'preview',
                                    self._how(root, found, level))
        image = Path(shown['slides'][0]['image']).resolve()
        if (folder / 'preview').resolve() not in image.parents:
            raise WorkspaceError('The renderer did not return a sample slide.')
        data = worker_tools.picture(image)
        with self.files:
            (folder / 'sample.png').write_bytes(data)
            record = self._load(root)
            record.setdefault('review_samples', {})[level or ''] = {
                'brand': (mine.built.get('brand') or {}).get('sha256'),
                'outline': workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE)),
                'image': workspace.sha256_file(folder / 'sample.png'), 'problem': None}
            self._store(root, record)
            self._commit(root, 'draw a sample for the combined direction review')

    def _review_view(self, root, record, found):
        if found.next.kind != 'review':
            return None
        phase = found.next.step.id.partition(':')[2]
        items = []
        for name in workspace.artifact_names(root, found.session):
            spec = workspace.artifact(root, found.session, name)
            file = contained(root, spec['file'])
            if not file.is_file() or phase == 'direction' and spec['stage'] not in PREPARED:
                continue
            import desk
            document = desk.document(root, found.session, name)
            plan = desk.document(root, found.session, 'research-plan') if name == 'research' else {}
            items.append({'target': name, 'label': workspace.label(name),
                          'text': file.read_text(encoding='utf-8') if file.suffix == '.md' else '',
                          **({'document': document} if name == 'research-plan' else {}),
                          **({'research': research_view.account(root / 'research', plan.get('questions') or [])}
                             if name == 'research' else {}),
                          'deck': spec['stage'] == 'deck',
                          'notes': contained(root, workspace.review_file(name)).read_text()
                          if contained(root, workspace.review_file(name)).is_file() else ''})
        for level, mine in found.decks.items():
            if phase == 'direction':
                item = {'target': 'outline:' + (level or ''),
                        'label': 'Deck direction' + (f' · Level {level}' if level else ''),
                        'text': outline_text(pipeline.outline_view(root, found, level))}
                saved = (record.get('review_samples') or {}).get(level or '') or {}
                looks = pipeline.look_view(root, found, level)
                if looks:
                    # The draft and the look are approved together: the person picks one.
                    item['looks'] = looks
                elif saved.get('problem') and not saved.get('image'):
                    item['sample_note'] = (f"A sample slide could not be drawn: {saved['problem']} "
                                           'The direction can still be reviewed from what the '
                                           'deck says; the slides are drawn and reviewed after '
                                           'you approve it.')
                else:
                    item['sample'] = {'artifact': mine.name, 'number': 1,
                                      'section': 'review-sample'}
                items.append(item)
            elif phase == 'final':
                view = pipeline.deck_gate(root, found.session, mine.name)
                for item in items:
                    if item['target'] == mine.name:
                        item['deck_view'] = view
        labels = {item['target']: item['label'] for item in items}
        for item in items:
            below = rewritten(root, found.session, found.decks, item['target'])
            item['rewrites'] = [labels[name] for name in labels if name in below]
            # What a change to it writes again, and what that took, said before it is sent.
            item['redo'] = self._redo_view(root, record, found, item['target'], below)
        return {'phase': phase, 'label': found.next.step.label, 'items': items,
                'commits': commits(root, found.session, found.decks, phase),
                'expected': signature(root, found.session, record, phase)}

    def _request(self, root, record, decisions, target, note):
        """Record one change asked for from a combined review. Call it holding `files`."""
        base = target.partition('@')[0].partition(':')[0]
        if base not in ('scenario', 'yoodli'):
            decisions.pop('direction', None)
        if target.startswith('outline:'):
            level = target.partition(':')[2] or None
            self._decided(record, level)['asked'] = {
                'kind': 'revise', 'note': note.strip(), 'at': home.now()}
            self._fresh(record, workspace.qualify('deck-outline', level))
            return
        # The existing core records and invalidates all dependent materials.
        outcome = workspace.decide(root, target, 'revise', note, by='page')
        self._fresh(record, target)
        if target == 'research' and record.get('research'):
            record['research']['again'] = {
                'at': outcome['request']['at'],
                'left': pipeline.again(root, record, outcome['request'])}

    def review_decide(self, path, expected, decision, target=None, note=None, requests=None,
                      looks=None):
        """Approve a combined review, or ask for changes: to one `target` with a `note`,
        or to several at once as `requests`, each {'target', 'note'}. Every request is
        checked before any is recorded, so they are taken whole or not at all. Approving a
        direction review whose decks the brand drew looks for takes the person's pick for
        each, as `looks`: {level, or '' for a training without levels: {'choice', 'words'}}."""
        root = self._held(path)
        if decision not in ('approve', 'revise'):
            raise WorkspaceError('Approve the review or ask for changes.')
        asked = requests if requests is not None else [{'target': target, 'note': note}]
        if decision == 'revise' and (not isinstance(asked, list) or not asked
                                     or not all(isinstance(ask, dict) for ask in asked)):
            raise WorkspaceError('Say what should change, in at most 4000 characters.')
        again = []
        with self.files:
            record = self._load(root)
            found = self._survey(root, record)
            if self._resting(record) or found.next.kind != 'review':
                raise WorkspaceError('This training is not waiting for a combined review.')
            phase = found.next.step.id.partition(':')[2]
            view = self._review_view(root, record, found)
            if not expected or expected != view['expected']:
                raise WorkspaceError('The materials changed. Read the latest review before deciding.')
            if decision == 'approve':
                picks = {}
                for item in view['items']:
                    offered = item.get('looks')
                    if not offered:
                        continue
                    level = offered['level']
                    pick = (looks or {}).get(level or '') if isinstance(looks, dict) else None
                    choice = pick.get('choice') if isinstance(pick, dict) else None
                    # Looks that could not be rendered are never picked blind: drawn again,
                    # or the brand's default, chosen knowingly.
                    allowed = [pipeline.DEFAULT_LOOK, pipeline.AGAIN_LOOK] \
                        if offered.get('failed') else [look['id'] for look in offered['looks']]
                    if choice == pipeline.AGAIN_LOOK and offered.get('failed'):
                        again.append(level)
                        continue
                    if choice not in allowed:
                        raise WorkspaceError('Pick a look for ' + item['label'].lower()
                                             + ' before you approve the direction.')
                    words = pick.get('words') if isinstance(pick.get('words'), str) else ''
                    picks[level or ''] = {'choice': choice, 'words': words.strip()[:2000],
                                          'by': 'page', 'at': home.now()}
                for level, picked in picks.items():
                    self._decided(record, level or None).setdefault('look', {})['picked'] = picked
                # Asked to draw looks again, it is not approved yet: they are drawn again,
                # and the review comes back with them.
                for level in again:
                    self._note(root, level, look=None)
                if not again:
                    record.setdefault('review_decisions', {})[phase] = {
                        'signature': expected, 'by': 'page', 'at': home.now()}
            else:
                known = [item['target'] for item in view['items']]
                for ask in asked:
                    said = ask.get('note')
                    if not isinstance(said, str) or not said.strip() or len(said) > 4000:
                        raise WorkspaceError('Say what should change, in at most 4000 characters.')
                    if ask.get('target') not in known:
                        raise WorkspaceError('Choose a document or deck direction from this review.')
                if len({ask['target'] for ask in asked}) != len(asked):
                    raise WorkspaceError('Ask once for each document or deck direction.')
                decisions = record.setdefault('review_decisions', {})
                decisions.pop('final', None)
                for ask in asked:
                    self._request(root, record, decisions, ask['target'], ask['note'])
            self._store(root, record)
            self._commit(root, 'draw the looks again for the direction review'
                         if decision == 'approve' and again else
                         'approve the combined review' if decision == 'approve'
                         else f'request changes to {len(asked)} items from the combined review'
                         if len(asked) > 1 else 'request changes from the combined review')
        self.carry_on(root)
        return self.view(root)
