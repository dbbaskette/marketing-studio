"""A brief or source edit keeps the work and marks it out of date: Update or Keep as it is."""
import json

from helpers import Isolated, project as synthetic
import test_desk_engine as fixtures
from runner import api, google_delivery, progress, sources, stale
from runner.contracts import Invalid, advance
from runner.validation import validate_project


class StaleWorkTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)

    def current(self):
        return self.store.read(self.ident)

    def act(self, verb, **values):
        return api.action(self.engine, {'action': verb, 'id': self.ident,
                                        'expected_revision': self.current()['revision'], **values})

    def edit(self, **changes):
        p = self.current()
        return self.store.edit_brief(self.ident, {**p['brief'], **changes}, expected_revision=p['revision'])

    def approve(self):
        manifest = self.engine.preview(self.ident, expected_revision=self.current()['revision'])
        self.engine.manual_review(self.ident, manifest['id'], ['Inspected the actual page and its relationships.'],
                                  expected_revision=self.current()['revision'])
        self.engine.check(self.ident, expected_revision=self.current()['revision'])
        return self.engine.approve(self.ident, expected_revision=self.current()['revision'])

    def test_a_brief_edit_keeps_the_work_marks_it_and_clears_the_approval(self):
        before = self.approve()
        edited = self.edit(audience='Platform engineers')
        for key in ('facts', 'stories', 'selected_story', 'scene', 'assets'):
            self.assertEqual(edited[key], before[key], key)
        self.assertIsNone(edited['approval'])
        self.assertEqual(edited['checks'], [], 'Checks are run again for the new brief.')
        self.assertEqual(edited['stale'], {'stories': {'because': 'brief', 'revision': edited['revision']},
                                           'page': {'because': 'brief', 'revision': edited['revision']}})
        # A rename still marks nothing, and keeps what is already marked.
        renamed = self.edit(title='Restart one instance, one at a time')
        self.assertEqual(renamed['stale'], edited['stale'])
        fresh = self.store.create('Rename only', preset='digital')
        self.assertNotIn('stale', self.store.edit_brief(fresh['id'], {**fresh['brief'], 'title': 'Renamed'},
                                                         expected_revision=0))

    def test_a_source_edit_marks_the_facts_too_and_both_causes_are_named(self):
        added = sources.capture(self.store, self.ident, b'More synthetic notes.', name='More notes',
                                expected_revision=self.current()['revision'])
        self.assertEqual(set(added['stale']), {'facts', 'stories', 'page'})
        self.assertEqual(len(added['facts']), 1)
        edited = self.edit(purpose='Keep serving while restarting')
        self.assertEqual(edited['stale']['stories']['because'], 'brief and sources')
        self.assertEqual(edited['stale']['facts']['because'], 'sources')
        self.assertIn('made before the brief and sources changed',
                      progress.roadmap(edited, self.engine.deliveries(self.ident))['needs'])
        self.assertEqual(progress.readiness(edited)['summary'], 'Out of date after a change: update or keep')

    def test_approve_export_and_deliver_are_refused_while_anything_is_stale(self):
        approved = self.approve()
        files = self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        self.edit(audience='Platform engineers')
        with self.assertRaisesRegex(Invalid, 'Approval waits for out-of-date work: the story and the page were '
                                              'made before the brief changed'):
            self.engine.approve(self.ident, expected_revision=self.current()['revision'])
        with self.assertRaisesRegex(Invalid, 'Preparing the approved files waits for out-of-date work'):
            self.engine.preview(self.ident, expected_revision=self.current()['revision'], draft=False)
        with self.assertRaisesRegex(Invalid, 'Delivery waits for out-of-date work: the story and the page'):
            google_delivery.execute(self.store, self.ident, expected_revision=self.current()['revision'],
                                    export_id=files['id'], request_id='deliver-one', folder=None)
        # A draft preview is still drawn: only approval, export and delivery wait.
        self.engine.preview(self.ident, expected_revision=self.current()['revision'])

    def refused(self, *parts):
        """Approve, prepare approved files and deliver each refuse, naming what is out of date."""
        revision = self.current()['revision']
        for doing, run in (('Approval', lambda: self.engine.approve(self.ident, expected_revision=revision)),
                           ('Preparing the approved files', lambda: self.engine.preview(self.ident, expected_revision=revision, draft=False)),
                           ('Delivery', lambda: google_delivery.execute(self.store, self.ident, expected_revision=revision,
                                                                       export_id='e_synthetic', request_id='deliver-two', folder=None))):
            with self.subTest(doing=doing), self.assertRaisesRegex(Invalid, doing + ' waits for out-of-date work') as caught:
                run()
            for part in parts:
                self.assertIn(part, str(caught.exception))

    def two_stories(self):
        from copy import deepcopy
        from runner import scene, stories
        other = deepcopy(self.proposal)
        other.update(id='story2', headline='Serve while one restarts')
        other['blocks'][0].update(kind='process', title='Drain, restart, return')
        project = stories.adopt(self.store, self.ident, [self.proposal, other], expected_revision=self.current()['revision'])
        project = stories.select(self.store, self.ident, 'story1', expected_revision=project['revision'])
        return scene.adopt(self.store, self.ident, expected_revision=project['revision'])

    def test_choosing_another_story_after_a_brief_edit_leaves_the_story_out_of_date(self):
        from runner import stories
        self.two_stories()
        self.edit(audience='Platform engineers')
        chosen = stories.select(self.store, self.ident, 'story2', expected_revision=self.current()['revision'])
        # Choosing is neither making the story again nor keeping it: the mark stays.
        self.assertIn('stories', chosen['stale'])
        self.refused('the story')
        # Probe from the review, at the record itself.
        p = synthetic()
        edited = advance(p, {'brief': {**p['brief'], 'audience': 'Operators'}}, expected_revision=0, owner='owner1')
        # The synthetic record has an art direction but no image: there is no artwork to mark.
        self.assertEqual(set(edited['stale']), {'stories', 'page'})
        again = advance(edited, {'selected_story': None}, expected_revision=edited['revision'], owner='owner1')
        self.assertIn('stories', again['stale'])

    def test_editing_or_placing_on_the_page_after_keeping_the_story_leaves_the_page_out_of_date(self):
        from copy import deepcopy
        self.edit(audience='Platform engineers')
        self.act('keep-stale', part='stories')
        # One text element edited: the page is not laid out again.
        element = next(e for e in self.current()['scene']['elements'] if e['kind'] == 'text' and e['id'].endswith('_heading'))
        edited = self.engine.edit_text(self.ident, element['id'], 'One at a time', expected_revision=self.current()['revision'])
        self.assertEqual(set(edited['stale']), {'page'})
        self.refused('the page')
        # Artwork placed on the page (any other change to the scene) is not laying it out again.
        placed = deepcopy(self.current()['scene'])
        placed['elements'][0]['bounds'] = list(placed['elements'][0]['bounds'])
        placed['id'] = placed['id'] + 'x'
        changed = self.store.update(self.ident, {'scene': placed}, expected_revision=self.current()['revision'])
        self.assertEqual(set(changed['stale']), {'page'})
        self.refused('the page')
        # Laying the page out again (Update the page, layout, visual layout) makes it current.
        self.act('layout', arrangement='stack')
        self.assertNotIn('stale', self.current())

    def test_a_replaced_source_drops_only_the_facts_that_quoted_it(self):
        from runner import evidence
        project = sources.capture(self.store, self.ident, b'Two instances serve while one restarts.', name='More notes',
                                  expected_revision=self.current()['revision'])
        first, second = project['sources']
        quotes = {s['id']: sources.read(self.store, project, s) for s in (first, second)}
        facts = [{'id': key, 'statement': quotes[s['id']], 'value': quotes[s['id']], 'unit': '', 'status': 'supplied',
                  'evidence': [{'source_id': s['id'], 'start': 0, 'end': len(quotes[s['id']]), 'quote': quotes[s['id']]}]}
                 for key, s in (('f1', first), ('f2', second))]
        evidence.adopt(self.store, self.ident, facts, expected_revision=self.current()['revision'])
        replaced = sources.capture(self.store, self.ident, b'Different replacement notes.', name='More notes',
                                   replace_id=second['id'], expected_revision=self.current()['revision'])
        self.assertEqual([f['id'] for f in replaced['facts']], ['f1'], 'The fact quoting an untouched source stays.')
        self.assertEqual([d['id'] for d in replaced['stale']['facts']['dropped']], ['f2'])
        self.assertIn('replaced or removed', replaced['stale']['facts']['dropped'][0]['why'])

    def test_keep_as_it_is_clears_one_mark_and_approval_follows_once_none_is_left(self):
        self.edit(audience='Platform engineers')
        kept = self.act('keep-stale', part='stories')
        self.assertEqual(set(kept['stale']), {'page'})
        with self.assertRaisesRegex(Invalid, 'the page was made before the brief changed'):
            self.engine.approve(self.ident, expected_revision=kept['revision'])
        kept = self.act('keep-stale', part='page')
        self.assertNotIn('stale', kept)
        self.assertEqual(self.approve()['approval']['by'], 'user')
        with self.assertRaisesRegex(Invalid, 'not out of date'):
            self.act('keep-stale', part='page')

    def test_update_the_page_lays_it_out_again_locally(self):
        self.edit(audience='Platform engineers')
        self.engine.assistant = None
        manifest = self.act('refresh-page')
        project = self.current()
        self.assertEqual(set(project['stale']), {'stories'})
        self.assertEqual(manifest['revision'], project['revision'])
        self.assertEqual(self.renderer.call_count, 1)

    def test_update_the_story_makes_facts_and_stories_current(self):
        sources.capture(self.store, self.ident, b'More synthetic notes.', name='More notes',
                        expected_revision=self.current()['revision'])
        project = self.current()
        quote = sources.read(self.store, project, project['sources'][0])
        fact = {'id': 'f9', 'statement': quote, 'value': quote, 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': project['sources'][0]['id'], 'start': 0, 'end': len(quote), 'quote': quote}]}
        from runner import evidence, stories
        project = evidence.adopt(self.store, self.ident, [fact], expected_revision=project['revision'])
        self.assertNotIn('facts', project.get('stale', {}))
        story = {**self.proposal, 'blocks': [{**self.proposal['blocks'][0], 'fact_ids': ['f9']}]}
        project = stories.adopt(self.store, self.ident, [story], expected_revision=project['revision'])
        self.assertNotIn('stale', project, 'Made again from the current inputs: nothing is out of date.')

    def test_running_image_requests_are_not_kept_for_the_new_brief(self):
        from runner.contracts import basis
        p = synthetic()
        p['attempts'] = [{'id': name, 'provider': 'codex', 'state': state, 'revision': 0, 'basis': basis(p),
                          'image_brief_id': 'image1', 'asset_ids': [], 'cost': None, 'operation': 'generate',
                          'parent': None, 'automatic': False}
                         for name, state in (('running1', 'running'), ('done1', 'failed'))]
        changed = advance(p, {'brief': {**p['brief'], 'audience': 'Operators'}}, expected_revision=0, owner='owner1')
        self.assertEqual([a['id'] for a in changed['attempts']], ['done1'])
        self.assertEqual(set(changed['stale']), {'stories', 'page'})

    def test_projects_saved_before_held_work_open_unchanged(self):
        saved = self.current()
        self.assertNotIn('stale', saved)
        raw = json.dumps(saved, sort_keys=True)
        validate_project(saved)
        shown = self.engine.inspect(self.ident)
        self.assertEqual(json.dumps(shown['project'], sort_keys=True), raw)
        self.assertNotEqual(shown['roadmap']['stage'], 'updates')
        broken = {**saved, 'stale': {'page': {'because': 'nothing', 'revision': 0}}}
        with self.assertRaises(Invalid):
            validate_project(broken)
        with self.assertRaises(Invalid):
            stale.keep(self.store, self.ident, 'page', expected_revision=saved['revision'])
