"""Current, unreviewed previews without providers or a person's workspace."""
import base64
import json
import shutil
from pathlib import Path
import tempfile
import unittest

import helpers
from runner import build_progress
from workspace import WorkspaceError

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l6kAAAAASUVORK5CYII=')


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'render'
        self.output.mkdir()
        self.png = self.output / 'slide.png'
        self.png.write_bytes(PNG)
        self.spec = build_progress.begin(self.root, 'current', 'section-1',
            [{'id': 'first', 'title': 'First slide', 'number': 3}])
        self.preview = build_progress.Preview(self.spec, self.output)

    def publish(self, preview, slide='first', revision='a' * 64, image=None):
        """What a finished preview hands over: the deck's revision and each slide's picture."""
        preview.finish({'deckSha256': revision,
                        'slides': [{'id': slide, 'image': str(image or self.png)}]})

    def shown(self, basis='current'):
        found = build_progress.view(self.root, basis)
        return {slide['id']: slide['revision'] for slide in found['slides']} if found else {}

    def test_feedback_closes_only_the_affected_progress_writer(self):
        other = build_progress.begin(self.root, 'current', 'section-2',
            [{'id': 'second', 'title': 'Second', 'number': 4}])
        writer = build_progress.Preview(other, self.output)
        self.publish(self.preview)
        build_progress.invalidate(self.root, 'current', 'section-1')
        self.publish(self.preview, revision='c' * 64)
        self.publish(writer, slide='second')
        shown = build_progress.view(self.root, 'current')['slides']
        self.assertEqual((shown[0]['status'], shown[0]['revision']), ('needs-changes', 'a' * 64))
        self.assertEqual(shown[1]['id'], 'second')

    def test_partial_previews_are_kept_when_a_render_fails(self):
        self.publish(self.preview)
        shown = build_progress.view(self.root, 'current')['slides'][0]
        self.assertEqual((shown['number'], shown['revision']), (3, 'a' * 64))
        self.png.unlink()
        self.preview.failed()
        self.assertTrue(build_progress.view(self.root, 'current')['incomplete'])
        self.assertEqual(build_progress.image(self.root, 'current', shown['ref']), PNG)

    def test_a_replaced_attempt_publishes_nothing_and_its_urls_go(self):
        self.publish(self.preview)
        ref = build_progress.view(self.root, 'current')['slides'][0]['ref']
        spec = build_progress.begin(self.root, 'current', 'section-1',
            [{'id': 'first', 'title': 'New direction', 'number': 3}])
        new = build_progress.Preview(spec, self.output)
        self.publish(self.preview, revision='b' * 64)
        self.assertEqual(self.shown(), {})
        with self.assertRaises(FileNotFoundError):
            build_progress.image(self.root, 'current', ref)
        self.publish(new, revision='c' * 64)
        self.assertEqual(self.shown(), {'first': 'c' * 64})
        self.assertIsNone(build_progress.view(self.root, 'another-build'))

    def test_outside_files_and_non_pngs_are_not_published(self):
        outside = self.root / 'private.png'
        outside.write_bytes(PNG)
        self.publish(self.preview, image=outside)
        self.png.write_bytes(b'not a picture')
        self.publish(self.preview)
        self.assertIsNone(build_progress.view(self.root, 'current'))

    def test_later_preview_of_same_attempt_replaces_earlier_render(self):
        self.publish(self.preview)
        later = build_progress.Preview(self.spec, self.output)
        self.publish(self.preview, revision='b' * 64)
        self.publish(later, revision='c' * 64)
        self.assertEqual(self.shown(), {'first': 'c' * 64})

    def test_legacy_completed_section_is_available_before_whole_deck_review(self):
        self.preview.finish({'deckSha256': 'd' * 64, 'slides': [{'id': 'first', 'image': str(self.png)}]})
        self.assertEqual(build_progress.view(self.root, 'current')['slides'][0]['revision'], 'd' * 64)

    def test_whole_render_and_new_section_invalidate_superseded_writers(self):
        self.publish(self.preview)
        whole = build_progress.Preview(build_progress.begin(self.root, 'current', 'whole',
            [{'id': 'first', 'title': 'First slide', 'number': 3}]), self.output)
        self.publish(self.preview, revision='b' * 64)
        self.assertEqual(self.shown(), {'first': 'a' * 64})
        self.publish(whole, revision='c' * 64)
        self.assertEqual(self.shown(), {'first': 'c' * 64})
        build_progress.begin(self.root, 'current', 'section-1',
            [{'id': 'first', 'title': 'Changed slide', 'number': 3}])
        self.publish(whole, revision='e' * 64)
        self.assertNotIn('e' * 64, self.shown().values())

    def test_late_callbacks_do_not_recreate_a_removed_workspace(self):
        shutil.rmtree(self.root)
        self.preview.failed()
        self.publish(self.preview)
        self.assertFalse(self.root.exists())


class RenderProgressTests(unittest.TestCase):
    """A preview is shown as running from when it starts until it finishes or fails, with
    no events asked of the slides tool."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'render'

    def status(self):
        index = json.loads((self.root / build_progress.FOLDER / 'index.json').read_text())
        return index['parts']['section-1']['status']

    def test_preview_records_start_and_finish_without_events(self):
        from runner import worker_tools
        seen = []
        test = self

        class Tool:
            def preview(self, compiled, folder, renderer, file_id=None):
                seen.append(test.status())
                Path(folder).mkdir(parents=True)
                (Path(folder) / 'slide.png').write_bytes(PNG)
                return {'deckSha256': 'd' * 64,
                        'slides': [{'id': 'first', 'image': str(Path(folder) / 'slide.png')}]}

        spec = build_progress.begin(self.root, 'current', 'section-1',
                                    [{'id': 'first', 'title': 'First slide', 'number': 3}])
        self.assertEqual(self.status(), 'drawing')
        worker_tools.render(Tool(), self.root / 'compiled', self.output,
                            {'renderer': 'local', 'lock': str(self.root / 'render.lock'),
                             'progress': spec})
        self.assertEqual((seen, self.status()), (['rendering'], 'rendered'))
        shown = build_progress.view(self.root, 'current')['slides']
        self.assertEqual([slide['id'] for slide in shown], ['first'])

    def test_a_failed_preview_is_shown_as_incomplete(self):
        from runner import worker_tools

        class Tool:
            def preview(self, compiled, folder, renderer, file_id=None):
                raise WorkspaceError('It could not be rendered.')

        spec = build_progress.begin(self.root, 'current', 'section-1',
                                    [{'id': 'first', 'title': 'First slide', 'number': 3}])
        with self.assertRaises(WorkspaceError):
            worker_tools.render(Tool(), self.root / 'compiled', self.output,
                                {'renderer': 'local', 'lock': str(self.root / 'render.lock'),
                                 'progress': spec})
        self.assertEqual(self.status(), 'incomplete')
