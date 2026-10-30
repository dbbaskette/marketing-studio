"""New desk text approvals keep all slide production behind the person's decision."""
from test_runner_deck import DeckCase
from workspace import WorkspaceError

class ContentFirstTests(DeckCase):
    def test_text_review_then_design_with_exact_approval_and_no_early_render(self):
        self.engine.content_first = True
        root = self.begin(flow='desk')
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

from test_runner_deck import PageCase

class ContentPageTests(PageCase):
    def test_authenticated_desk_text_approval_route_preserves_other_desk_refusals(self):
        self.engine.content_first = True
        root = self.begin(flow='desk')
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
        self.workers.found = [[MAJOR], []]
        root = self.begin(flow='desk')
        self.to_end(root)
        seen = self.engine._load(root)['deck']['']['saved']['sha256']
        self.assertTrue(self.built(root)['rounds'][-1]['review']['findings'])
        self.engine.slide_note(root, None, 'check-yourself', 'Make this diagram clearer.', seen)
        self.to_end(root)
        job = [spec for kind, _, spec in self.workers.jobs if kind == 'review'][-1]
        self.assertEqual(len(job['review']['slides']), 6)
        self.assertEqual(self.built(root)['rounds'][-1]['review']['findings'], [])
