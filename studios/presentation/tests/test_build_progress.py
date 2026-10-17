"""Current, unreviewed previews without providers or a person's workspace."""
import base64
import json
import shutil
from pathlib import Path
import tempfile
import threading
import unittest

import helpers
from runner import build_progress, slide_events, slides
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

    def event(self, **changes):
        return {'schema': 1, 'runId': 'native-run', 'sequence': 1,
                'type': 'slide-ready', 'status': 'rendered-unreviewed',
                'revision': 'a' * 64, 'buildRevision': 'b' * 64, 'slide': 'first',
                'number': 1, 'path': str(self.png), **changes}

    def test_live_and_partial_previews_survive_reconnect_without_worker_restart(self):
        self.assertTrue(self.preview.event(self.event()))
        shown = build_progress.view(self.root, 'current')['slides'][0]
        self.assertEqual(shown['number'], 3)
        self.assertEqual(shown['revision'], 'a' * 64)
        self.assertEqual(shown['buildRevision'], 'b' * 64)
        self.png.unlink()
        self.preview.failed()
        self.assertTrue(build_progress.view(self.root, 'current')['incomplete'])
        self.assertEqual(build_progress.image(self.root, 'current', shown['ref']), PNG)

    def test_replaced_attempt_and_changed_build_reject_old_events_and_urls(self):
        self.preview.event(self.event())
        ref = build_progress.view(self.root, 'current')['slides'][0]['ref']
        spec = build_progress.begin(self.root, 'current', 'section-1',
            [{'id': 'first', 'title': 'New direction', 'number': 3}])
        new = build_progress.Preview(spec, self.output)
        self.assertFalse(self.preview.event(self.event(sequence=2)))
        with self.assertRaises(FileNotFoundError):
            build_progress.image(self.root, 'current', ref)
        self.assertTrue(new.event(self.event(runId='new-run', revision='c' * 64)))
        self.assertIsNone(build_progress.view(self.root, 'another-build'))

    def test_reordered_other_run_and_other_revision_are_rejected(self):
        self.assertTrue(self.preview.event(self.event()))
        for changes in ({}, {'sequence': 2, 'runId': 'other'}, {'sequence': 2, 'revision': 'c' * 64},
                        {'sequence': 2, 'buildRevision': 'c' * 64}):
            self.assertFalse(self.preview.event(self.event(**changes)))

    def test_outside_files_and_non_pngs_are_not_published(self):
        outside = self.root / 'private.png'
        outside.write_bytes(PNG)
        self.assertFalse(self.preview.event(self.event(path=str(outside))))
        self.png.write_bytes(b'not a picture')
        self.assertFalse(self.preview.event(self.event(sequence=2)))
        self.assertIsNone(build_progress.view(self.root, 'current'))

    def test_later_preview_of_same_attempt_replaces_earlier_render(self):
        self.preview.event(self.event())
        later = build_progress.Preview(self.spec, self.output)
        self.assertFalse(self.preview.event(self.event(sequence=2)))
        self.assertTrue(later.event(self.event(revision='c' * 64)))
        self.assertEqual(build_progress.view(self.root, 'current')['slides'][0]['revision'], 'c' * 64)

    def test_legacy_completed_section_is_available_before_whole_deck_review(self):
        self.preview.finish({'deckSha256': 'd' * 64, 'slides': [{'id': 'first', 'image': str(self.png)}]})
        self.assertEqual(build_progress.view(self.root, 'current')['slides'][0]['revision'], 'd' * 64)

    def test_whole_render_and_new_section_invalidate_superseded_writers(self):
        self.preview.event(self.event())
        whole = build_progress.Preview(build_progress.begin(self.root, 'current', 'whole',
            [{'id': 'first', 'title': 'First slide', 'number': 3}]), self.output)
        self.assertFalse(self.preview.event(self.event(sequence=2)))
        self.assertTrue(whole.event(self.event(runId='whole')))
        build_progress.begin(self.root, 'current', 'section-1',
            [{'id': 'first', 'title': 'Changed slide', 'number': 3}])
        self.assertFalse(whole.event(self.event(sequence=2, runId='whole')))

    def test_late_callbacks_do_not_recreate_a_removed_workspace(self):
        shutil.rmtree(self.root)
        self.preview.failed()
        self.assertFalse(self.preview.event(self.event()))
        self.assertFalse(self.root.exists())


class EventLogTests(unittest.TestCase):
    def test_split_event_arrives_before_command_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            folder, ready, found = Path(directory), threading.Event(), []
            def each(event):
                found.append(event)
                ready.set()
            with slide_events.watching(folder, each):
                log = folder / 'events.jsonl'
                log.write_text('{"schema":1,')
                with log.open('a') as stream:
                    stream.write('"type":"slide-ready"}\n')
                self.assertTrue(ready.wait(1))
            self.assertEqual(len(found), 1)

    def test_capability_fallback_and_failure_log_drained_before_output_cleanup(self):
        for supported in (False, True):
            with self.subTest(supported=supported), tempfile.TemporaryDirectory() as directory:
                root, calls, seen = Path(directory), [], []
                def run(command, cwd=None):
                    calls.append(command)
                    if '--version' in command:
                        return 0, 'Harness Slides 0.15.0', ''
                    if command[-1] == 'version':
                        return 0, json.dumps({'capabilities': ['progress-events'] if supported else []}), ''
                    output = Path(command[command.index('--output') + 1])
                    output.mkdir()
                    event = json.dumps({'schema': 1, 'type': 'failed', 'runId': 'test', 'sequence': 1})
                    if '--events' in command:
                        (output / 'events.jsonl').write_text(event + '\n')
                    return 1, '', event + '\nSynthetic failure'
                tool = slides.Slides(runtime=root, run=run)
                with tool.progress(seen.append), self.assertRaises(WorkspaceError) as failure:
                    tool.preview(root / 'compiled', root / 'preview', 'local')
                self.assertNotIn('schema', str(failure.exception))
                self.assertEqual('--events' in calls[-1], supported)
                self.assertEqual(bool(seen), supported)
                self.assertFalse((root / 'preview').exists())
