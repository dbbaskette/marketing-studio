"""Grouped, revision-bound reviews for new runs; legacy gates remain unchanged."""
from pathlib import Path
import shutil

import home
import workspace
from workspace import WorkspaceError
from studio_core import review_policy
from runner import pipeline, deck, worker_tools

PREPARED = ('research-plan', 'research', 'blueprint', 'document', 'brief')
DECK_PREPARED = ('deck-handoff', 'deck-brand', 'deck-outline')


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
            brand = (pipeline.read_built(root, level).get('brand') or {})
            saved = (run.get('review_samples') or {}).get(level or '') or {}
            if saved.get('brand') == brand.get('sha256') and saved.get('outline') == workspace.sha256_file(pipeline.place(root, level, pipeline.OUTLINE)) \
                    and saved.get('image') == workspace.sha256_file(
                        pipeline.place(root, level, 'work/review-sample/sample.png')) \
                    and saved.get('image'):
                completed.add(ident)
    boundaries = {}
    for phase in ('direction', 'final'):
        ident = 'review:' + phase
        label = 'Review the direction' if phase == 'direction' else 'Review the finished materials'
        boundaries[phase] = pipeline.Step(ident, 'review', label,
                                           'Waiting for you to ' + label.lower(), 'review')
        accepted = (run.get('review_decisions') or {}).get(phase) or {}
        if accepted.get('signature') == signature(root, session, run, phase):
            completed.add(ident)
    return tuple([*prep, *samples, *([boundaries['direction']] if mode == 'balanced' else []),
                  *build, boundaries['final'], *package]), frozenset(completed)


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
        level = workspace.split(step.artifact)[1]
        mine = found.decks[level]
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
        home.write_json(folder / 'composition.json', {'version': 1, 'title': found.session['title'],
                        'direction': dict(deck.DIRECTION), 'slides': [laid]})
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
                'image': workspace.sha256_file(folder / 'sample.png')}
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
            items.append({'target': name, 'label': workspace.label(name),
                          'text': file.read_text(encoding='utf-8') if file.suffix == '.md' else '',
                          'deck': spec['stage'] == 'deck',
                          'notes': contained(root, workspace.review_file(name)).read_text()
                          if contained(root, workspace.review_file(name)).is_file() else ''})
        for level, mine in found.decks.items():
            if phase == 'direction':
                items.append({'target': 'outline:' + (level or ''),
                              'label': 'Deck direction' + (f' · Level {level}' if level else ''),
                              'text': outline_text(pipeline.outline_view(root, found, level)),
                              'sample': {'artifact': mine.name, 'number': 1, 'section': 'review-sample'}})
            elif phase == 'final':
                view = pipeline.deck_gate(root, found.session, mine.name)
                for item in items:
                    if item['target'] == mine.name:
                        item['deck_view'] = view
        return {'phase': phase, 'label': found.next.step.label, 'items': items,
                'expected': signature(root, found.session, record, phase)}

    def review_decide(self, path, expected, decision, target=None, note=None):
        root = self._held(path)
        if decision not in ('approve', 'revise'):
            raise WorkspaceError('Approve the review or ask for changes.')
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
                record.setdefault('review_decisions', {})[phase] = {
                    'signature': expected, 'by': 'page', 'at': home.now()}
            else:
                if not isinstance(note, str) or not note.strip() or len(note) > 4000:
                    raise WorkspaceError('Say what should change, in at most 4000 characters.')
                if target not in [item['target'] for item in view['items']]:
                    raise WorkspaceError('Choose a document or deck direction from this review.')
                decisions = record.setdefault('review_decisions', {})
                decisions.pop('final', None)
                base = target.partition('@')[0].partition(':')[0]
                if base not in ('scenario', 'yoodli'):
                    decisions.pop('direction', None)
                if target.startswith('outline:'):
                    level = target.partition(':')[2] or None
                    self._decided(record, level)['asked'] = {
                        'kind': 'revise', 'note': note.strip(), 'at': home.now()}
                    self._fresh(record, workspace.qualify('deck-outline', level))
                else:
                    # The existing core records and invalidates all dependent materials.
                    outcome = workspace.decide(root, target, 'revise', note, by='page')
                    self._fresh(record, target)
                    if target == 'research' and record.get('research'):
                        record['research']['again'] = {
                            'at': outcome['request']['at'],
                            'left': pipeline.again(root, record, outcome['request'])}
            self._store(root, record)
            self._commit(root, 'approve the combined review' if decision == 'approve'
                         else 'request changes from the combined review')
        self.carry_on(root)
        return self.view(root)
