"""stale.py's rule: a mark is cleared only by Keep as it is, by remaking the whole part, or when
nothing of the part is left. Each sequence ends with approve, export and delivery refused."""
from copy import deepcopy
import json
import struct
import threading
import zlib
from unittest import mock

from helpers import Isolated, project as synthetic
import test_desk_engine as fixtures
import test_stale
from runner import action_jobs, api, desk_chat, scene, server, stories
from runner.contracts import advance, lost
from runner.engine import Engine
from runner.image_jobs import Jobs


def other_png(shade):
    """A small valid PNG of its own colour, so new artwork is a new image."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    row = b'\x00' + bytes((shade, 0x7b, 0x79, 0xff)) * 4
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * 4)) + chunk(b'IEND', b''))


class StaleRuleTests(Isolated):
    # test_stale's helpers, without running its tests a second time.
    _base = test_stale.StaleWorkTests
    current, act, edit, approve, refused, two_stories = (
        _base.current, _base.act, _base.edit, _base.approve, _base.refused, _base.two_stories)

    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)

    def review_check_approve(self):
        """Lay out, render, review and check, then try to approve: the reviewer's sequence."""
        return self.approve()

    def test_a_conversation_edit_of_one_story_then_choosing_another_still_needs_a_decision(self):
        self.two_stories()
        self.edit(audience='Platform engineers')
        context = desk_chat.context(self.store, self.ident, 'story:story2')
        revised = deepcopy(context['inputs']['story'])
        revised['headline'] += ' now'
        desk_chat.submit(self.engine, self.ident, {'kind': 'story', 'target': 'story:story2',
                                                   'expected_basis': context['expected_basis'],
                                                   'payload': {'story': revised}})
        self.assertIn('stories', self.current()['stale'], 'One story edited is not the stories made again.')
        project = stories.select(self.store, self.ident, 'story1', expected_revision=self.current()['revision'])
        scene.adopt(self.store, self.ident, expected_revision=project['revision'])
        with self.assertRaisesRegex(Exception, 'Approval waits for out-of-date work: the story'):
            self.review_check_approve()
        self.refused('the story')
        # The person's decision is what clears it.
        self.act('keep-stale', part='stories')
        self.assertEqual(self.review_check_approve()['approval']['by'], 'user')

    def test_revising_one_story_with_the_assistant_then_choosing_another_still_needs_a_decision(self):
        self.two_stories()
        self.edit(audience='Platform engineers')
        def revise(project, story, block_id, instruction):
            return {**deepcopy(story), 'takeaway': 'Keep the others serving while one restarts.'}
        self.engine.assistant = mock.Mock()
        self.engine.assistant.revise_story.side_effect = revise
        self.act('revise-story', story_id='story2', block_id=None, instruction='Say it more plainly.')
        self.assertIn('stories', self.current()['stale'])
        project = stories.select(self.store, self.ident, 'story1', expected_revision=self.current()['revision'])
        scene.adopt(self.store, self.ident, expected_revision=project['revision'])
        with self.assertRaisesRegex(Exception, 'the story'):
            self.review_check_approve()
        self.refused('the story')

    # -- artwork -----------------------------------------------------------------------------
    def with_artwork(self):
        from runner.images.base import result, save_asset
        shades = iter((0x0b, 0x5a, 0xa0, 0xc8))
        proposal = deepcopy(self.proposal)
        proposal['blocks'][0].update(illustration=True, illustration_role='Show a restarting instance beside serving instances.')
        current = stories.adopt(self.store, self.ident, [proposal], expected_revision=self.current()['revision'])
        stories.select(self.store, self.ident, 'story1', expected_revision=current['revision'])

        class Adapter:
            def __init__(self, folder): self.folder = folder
            def generate(self, *, attempt_id, brief):
                return result('gemini', 'generate', attempt_id, state='complete',
                              assets=[save_asset(self.folder, other_png(next(shades)), 'image/png')])

        def direction(project):
            region = project['scene']['art_regions'][0]['id']
            return {'style': 'Coherent explanatory shapes.', 'reading_order': 'Restarting then serving instances.',
                    'acceptance': 'Exact counts and clear label regions.',
                    'objects': [{'id': 'instances', 'region_id': region, 'count': 3, 'description': 'Three service instances.',
                                 'relationships': 'One restarts; two serve.', 'preserve': 'Leave labels empty.'}]}
        self.engine.assistant = mock.Mock()
        self.engine.assistant.art_direction.side_effect = direction
        self.engine.adapters = {'gemini': Adapter}
        self.engine.configuration = {'image_provider': 'gemini'}
        self.engine.build(self.ident, expected_revision=self.current()['revision'], request_id='art-first')
        project = self.current()
        art = next(e for e in project['scene']['elements'] if e['kind'] == 'artwork')
        return art['asset_id']

    def test_update_the_page_and_placing_the_same_image_leave_the_artwork_out_of_date(self):
        first = self.with_artwork()
        self.edit(audience='Platform engineers')
        self.assertEqual(set(self.current()['stale']), {'stories', 'page', 'artwork'})
        self.act('keep-stale', part='stories')
        self.act('refresh-page')
        self.assertEqual(set(self.current()['stale']), {'artwork'}, 'Laid out again: the page, not the artwork.')
        self.refused('the artwork')
        self.act('layout', arrangement='infographic')
        self.act('compose-image', asset_id=first)
        self.assertEqual(set(self.current()['stale']), {'artwork'}, 'The same image placed again is not new artwork.')
        self.refused('the artwork')
        # New artwork, made now and placed on the page, makes the artwork current.
        project = self.engine.image_direction(self.ident, self.engine.assistant.art_direction(self.current()),
                                              expected_revision=self.current()['revision'])
        self.assertIn('artwork', project['stale'], 'An art direction alone is not artwork.')
        jobs = Jobs(self.store, self.engine.adapters)
        jobs.intent(self.ident, expected_revision=project['revision'], brief_id=project['image_briefs'][-1]['id'],
                    provider='gemini', request_id='art-second')
        jobs.execute(self.ident, 'art-second')
        project = self.current()
        fresh = next(a for a in project['attempts'] if a['id'] == 'art-second')['asset_ids'][0]
        self.assertNotEqual(fresh, first)
        placed = self.engine.compose_asset(self.ident, fresh, expected_revision=project['revision'])
        self.assertNotIn('stale', placed)

    def test_a_new_art_direction_from_the_page_or_the_conversation_leaves_the_artwork_out_of_date(self):
        self.with_artwork()
        self.edit(audience='Platform engineers')
        for part in ('stories', 'page'):
            self.act('keep-stale', part=part)
        self.act('art-direct')      # the page path: a new direction, the old image still on the page
        self.assertEqual(set(self.current()['stale']), {'artwork'})
        context = desk_chat.context(self.store, self.ident, 'art-direction')
        direction = self.engine.assistant.art_direction(self.current())
        desk_chat.submit(self.engine, self.ident, {'kind': 'art-direction', 'target': 'art-direction',
                                                   'expected_basis': context['expected_basis'],
                                                   'payload': {'direction': direction}})
        self.assertEqual(set(self.current()['stale']), {'artwork'})
        with self.assertRaisesRegex(Exception, 'the artwork'):
            self.review_check_approve()
        self.refused('the artwork')


class LostNamesTests(Isolated):
    def test_more_than_a_hundred_dropped_facts_name_the_newest_and_count_the_rest(self):
        p = synthetic()
        raw = 'Synthetic counts: baseline 12; comparison 24.'
        p['facts'] += [{'id': 'x%03d' % n, 'statement': 'Synthetic note ' + str(n), 'value': 'Sy', 'unit': '',
                        'status': 'supplied', 'evidence': [{'source_id': 's1', 'start': 0, 'end': 2}]}
                       for n in range(103)]
        p['stories'][0]['blocks'][0]['fact_ids'] = ['f1', 'f2']
        replacement = {**p['sources'][0], 'id': 's2', 'sha256': 'b' * 64}
        changed = advance(p, {'sources': [replacement]}, expected_revision=0, owner='owner1')
        facts = changed['stale']['facts']
        self.assertEqual(len(facts['dropped']), 100)
        self.assertEqual(facts['dropped_more'], 5)
        self.assertEqual(lost(facts, 'dropped'), 105)
        self.assertEqual(facts['dropped'][-1]['id'], 'x102', 'The newest are named.')
        removed = changed['stale']['stories']['removed']
        self.assertEqual([(s['id'], s['statement']) for s in removed], [('story1', 'Synthetic comparison')])
        self.assertIn('fact whose source was replaced', removed[0]['why'])
        self.assertEqual(changed['facts'], [])
        self.assertIsNone(raw and None)


class ShutdownTests(Isolated):
    def setUp(self):
        super().setUp()
        fixtures.setup_desk(self)

    def test_a_shutdown_during_approval_or_review_is_interrupted_with_the_next_step(self):
        for verb, values in (('approve', {'then_export': True}),
                             ('review', {'export_id': 'e_x', 'observations': ['Looked.'], 'then_check': True})):
            with self.subTest(verb=verb):
                entered = threading.Event()

                def busy(found, sent):
                    entered.set()
                    while True:
                        found.progress('Working')     # the next step or save after shutdown ends it
                        threading.Event().wait(.01)
                page = server.Page(8000, self.store, Engine(self.store))
                with mock.patch.object(api, 'action', side_effect=busy):
                    page.write('/api/action', {'action': verb, 'id': self.ident,
                                               'expected_revision': self.store.read(self.ident)['revision'], **values})
                    self.assertTrue(entered.wait(3))
                    page.actions.shutdown()
                shown = page.doing(self.ident)
                self.assertEqual(shown['state'], 'interrupted')
                self.assertNotIn('Stopped on request', json.dumps(shown))
                self.assertIn('was interrupted', shown['problem'])
                self.assertIn(action_jobs.NEXT[verb], shown['problem'])
                # The next server shows it too, with what to do next.
                later = server.Page(8001, self.store, Engine(self.store)).doing(self.ident)
                self.assertEqual((later['state'], later['next']), ('interrupted', action_jobs.NEXT[verb]))
                server.Page(8002, self.store, Engine(self.store)).actions.dismiss(self.ident)
