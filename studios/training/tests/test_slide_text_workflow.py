"""New desk text approvals keep all slide production behind the person's decision."""
from test_runner_deck import DeckCase
from workspace import WorkspaceError
from runner_support import CHOSEN

class ContentFirstTests(DeckCase):
    def test_slide_text_is_approved_first_unless_the_form_turns_that_off(self):
        self.engine.content_first = True
        # The slide text comes first unless the form turns that off.
        self.assertIn('deck_content', self.engine._load(self.begin(flow='desk')))
        root = self.begin(title='Another deck', flow='desk', slide_text_review=False)
        self.assertNotIn('deck_content', self.engine._load(root))
        self.assertFalse((self.view(root)['outline'] or {}).get('waiting'))
        self.assertTrue(self.workers.of('section'))
        with self.assertRaises(WorkspaceError):
            self.start(title='A third', deck_target='pptx', brand=CHOSEN, flow='desk',
                       slide_text_review='yes')

    def test_text_review_then_design_with_exact_approval_and_no_early_render(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=True)
        shown = self.view(root)['outline']
        self.assertTrue(shown['waiting'])
        self.assertTrue(shown['content_first'])
        self.assertTrue(shown['slides'])
        self.assertFalse(self.workers.of('section'))
        self.assertFalse(self.workers.of('review'))
        self.assertFalse(any(call[0] in ('preview', 'render') for call in self.slides.calls))
        with self.assertRaises(WorkspaceError):
            self.engine.outline(root, None, 'approve')
        self.engine.outline(root, None, 'revise', 'Clarify the first title.', seen=shown['sha256'])
        revised = self.view(root)['outline']
        self.assertTrue(revised['waiting'])
        self.assertFalse(self.workers.of('section'))
        self.engine.outline(root, None, 'approve', seen=revised['sha256'])
        self.assertTrue(self.workers.of('section'))
        self.assertFalse(self.view(root)['problem'])


class WalkthroughTextTests(DeckCase):
    """A walkthrough of each slide's design keeps the slide text approval on the desk."""

    def setUp(self):
        super().setUp()
        self.slides.design = True

    def test_a_desk_walkthrough_still_waits_for_the_slide_text(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=True, walkthrough=True)
        self.assertIn('deck_content', self.engine._load(root))
        shown = self.view(root)['outline']
        self.assertTrue(shown['waiting'] and shown['content_first'])
        self.assertIsNotNone(shown['design'], 'written with its design')
        self.assertFalse(self.workers.of('section'), 'nothing is drawn before approval')
        self.engine.outline(root, None, 'approve', seen=shown['sha256'])
        self.assertTrue(self.workers.of('section'))
        self.assertFalse(self.view(root)['problem'])


from test_runner_deck import PageCase

class ContentPageTests(PageCase):
    def test_authenticated_desk_text_approval_route_preserves_other_desk_refusals(self):
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=True)
        shown = self.view(root)['outline']
        body = {'path': str(root), 'level': None, 'decision': 'approve', 'seen': shown['sha256']}
        self.assertEqual(self.ask('POST', '/api/outline', body, token=False)[0], 403)
        self.post('outline', {**body, 'seen': 'wrong-version'}, expect=409)
        self.assertFalse(self.workers.of('section'))
        self.post('outline', body)
        self.assertTrue(self.workers.of('section'))

import json
from pathlib import Path
from test_runner_deck import MAJOR
from studio_core import critic

class CurrentCriticRepairTests(DeckCase):
    def test_changed_section_gets_a_complete_review_without_retaining_old_peer_findings(self):
        preview = self.slides.preview
        def current(*args, **kwargs):
            made = preview(*args, **kwargs)
            packet = Path(made['critic']) if made.get('critic') else Path(args[1]) / 'critic.json'
            packet.write_text(json.dumps({'schema': 2, 'questions': list(critic.LEGACY),
                'slides': made['slides'], 'deckSha256': made['deckSha256']}))
            return made
        self.slides.preview = current
        # Found again after the one automatic pass of fixes, so it is still there to keep.
        self.workers.found = [[MAJOR], [MAJOR], []]
        root = self.begin(flow='desk', slide_text_review=True)
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.built(root)['rounds'][-1]['review']['findings'])
        self.engine.slide_note(root, None, 'check-yourself', 'Make this diagram clearer.', seen)
        self.to_end(root)
        job = [spec for kind, _, spec in self.workers.jobs if kind == 'review'][-1]
        self.assertEqual(len(job['review']['slides']), 6)
        self.assertEqual(self.built(root)['rounds'][-1]['review']['findings'], [])


class LocalTextCorrections(DeckCase):
    def test_approval_checks_and_designs_exactly_the_locally_corrected_text(self):
        from copy import deepcopy
        from runner import pipeline
        self.engine.content_first=True
        root=self.begin(flow='desk', slide_text_review=True)
        shown=self.view(root)['outline']
        edited=deepcopy(shown['slides'])
        edited[0]['title']='Rolling restarts, corrected locally'
        edited[1]['notes']='Emphasize available capacity.'
        self.assertFalse(self.workers.of('section'))
        self.engine.outline(root,None,'approve',seen=shown['sha256'],edited=edited)
        kept=pipeline.outline_of(root,None)
        self.assertEqual(kept['slides'][0]['title'],edited[0]['title'])
        self.assertEqual(kept['slides'][1]['notes'],edited[1]['notes'])
        approval=self.engine._load(root)['deck']['']['approved']
        from workspace import sha256_file
        self.assertEqual(approval['sha256'],sha256_file(pipeline.place(root,None,pipeline.OUTLINE)))
        self.assertTrue(self.workers.of('section'))

    def test_local_corrections_cannot_change_slide_structure_or_approve_another_version(self):
        from copy import deepcopy
        from runner import pipeline
        self.engine.content_first=True
        root=self.begin(flow='desk', slide_text_review=True)
        shown=self.view(root)['outline'];before=pipeline.place(root,None,pipeline.OUTLINE).read_bytes()
        edited=deepcopy(shown['slides']);edited[0]['id']='another-slide'
        with self.assertRaises(WorkspaceError):self.engine.outline(root,None,'approve',seen=shown['sha256'],edited=edited)
        edited=deepcopy(shown['slides']);edited[0]['title']='Local correction'
        with self.assertRaises(WorkspaceError):self.engine.outline(root,None,'approve',seen='earlier-version',edited=edited)
        self.assertEqual(pipeline.place(root,None,pipeline.OUTLINE).read_bytes(),before)
        self.assertFalse(self.workers.of('section'))


class ConcurrentLocalCorrections(DeckCase):
    def test_changed_teaching_inputs_during_validation_cannot_be_approved(self):
        from copy import deepcopy
        from unittest import mock
        from runner import pipeline,worker_tools
        import workspace
        self.engine.content_first=True
        root=self.begin(flow='desk', slide_text_review=True);shown=self.view(root)['outline']
        before=pipeline.place(root,None,pipeline.OUTLINE).read_bytes()
        edited=deepcopy(shown['slides']);edited[0]['title']='Local correction'
        original=worker_tools.check_outline
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            session=workspace.load(root)
            file=root/workspace.artifact(root,session,'blueprint')['file']
            file.write_text(file.read_text()+'\nConcurrent teaching input change.\n')
            return result
        with mock.patch.object(worker_tools,'check_outline',changed),self.assertRaises(WorkspaceError):
            self.engine.outline(root,None,'approve',seen=shown['sha256'],edited=edited)
        self.assertEqual(pipeline.place(root,None,pipeline.OUTLINE).read_bytes(),before)
        self.assertFalse(self.workers.of('section'))


class PrivateTextDrafts(PageCase):
    def test_approval_cannot_bypass_saved_or_newer_corrections(self):
        from copy import deepcopy
        from runner import pipeline
        self.engine.content_first = True
        root = self.begin(flow='desk', slide_text_review=True)
        shown = self.view(root)['outline']
        edited = deepcopy(shown['slides']); edited[0]['title'] = 'Acknowledged correction'
        saved = self.post('slide-text-draft', {'path': str(root), 'action': 'save',
            'expected': 0, 'patch': {'basis': shown['sha256'], 'edits': edited}})
        decision = {'path': str(root), 'decision': 'approve', 'seen': shown['sha256']}
        self.post('outline', decision, expect=409)
        self.post('outline', {**decision, 'draft_revision': saved['revision']}, expect=409)
        self.post('outline', {**decision, 'edited': edited, 'draft_revision': 0}, expect=409)
        self.assertFalse(self.workers.of('section'))
        self.post('outline', {**decision, 'edited': edited, 'draft_revision': saved['revision']})
        self.assertEqual(pipeline.outline_of(root, None)['slides'][0]['title'], edited[0]['title'])

    def test_saved_corrections_are_private_revision_checked_and_start_no_pipeline_work(self):
        from copy import deepcopy
        from runner import pipeline
        self.engine.content_first=True
        root=self.begin(flow='desk', slide_text_review=True);shown=self.view(root)['outline']
        before=pipeline.place(root,None,pipeline.OUTLINE).read_bytes();jobs=len(self.workers.jobs)
        held=self.post('slide-text-draft',{'path':str(root),'action':'read'})
        edited=deepcopy(shown['slides']);edited[0]['title']='Private pending correction'
        sent={'path':str(root),'action':'save','expected':held['revision'],
            'patch':{'basis':shown['sha256'],'edits':edited,'note':'Explain the risk','selected':1}}
        saved=self.post('slide-text-draft',sent)
        self.assertNotIn('draft',saved)
        self.assertEqual(self.post('slide-text-draft',{'path':str(root),'action':'read'})['draft']['edits'],edited)
        self.post('slide-text-draft',sent,expect=409)
        self.assertEqual(len(self.workers.jobs),jobs)
        self.assertEqual(pipeline.place(root,None,pipeline.OUTLINE).read_bytes(),before)
        self.assertIsNone(self.engine._load(root)['deck'][''].get('approved'))
