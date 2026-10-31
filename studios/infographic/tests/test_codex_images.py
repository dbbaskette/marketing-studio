"""Codex built-in image generation and reference editing against stubbed event streams.

Every worker here is injected. No test starts Codex, reads a sign-in or contacts a provider.
"""
import json
from pathlib import Path

from helpers import Isolated
from graphics_fixtures import png
from runner.images.codex import Codex, failure_reason, saved_output
from runner.images.gemini import Gemini
from runner.validation import validate_image_result

THREAD = '01234567-1234-7123-8123-0123456789ab'
PNG = png()


def stream(*events):
    return '\n'.join(json.dumps(event) for event in events)


COMPLETED = stream({'type': 'thread.started', 'thread_id': THREAD},
                   {'type': 'turn.completed', 'usage': {'input_tokens': 7, 'output_tokens': 9}})


class Worker:
    """A stand-in Codex worker: records its command and writes only what a case asks for."""

    def __init__(self, *, events=COMPLETED, returncode=0, image=PNG, stderr='', state='complete'):
        self.events, self.returncode, self.image, self.stderr, self.state = events, returncode, image, stderr, state
        self.calls = []

    def __call__(self, command, prompt, folder, seconds, stop):
        self.calls.append((command, prompt))
        folder = Path(folder)
        if self.stderr:
            (folder / 'stderr.txt').write_text(self.stderr)
        if self.image is not None:
            (folder / 'generated_images').mkdir()
            (folder / 'generated_images' / 'image.png').write_bytes(self.image)
        return {'state': self.state, 'returncode': self.returncode, 'events': self.events}


class CodexImageTests(Isolated):
    def setUp(self):
        super().setUp()
        self.brief = {'prompt': 'Draw three illustrative service stages; no words or numbers.'}
        self.count = 0

    def adapter(self, worker):
        self.count += 1
        folder = self.temp / ('attempt' + str(self.count))
        folder.mkdir()
        return Codex(folder, run=worker), folder

    def test_generate_and_reference_edit_use_the_scoped_image_tool_and_the_shared_contract(self):
        worker = Worker()
        adapter, folder = self.adapter(worker)
        generated = adapter.generate(attempt_id='attempt1', brief=self.brief)
        edit_worker = Worker()
        editor, edit_folder = self.adapter(edit_worker)
        edited = editor.edit(attempt_id='attempt2', brief=self.brief,
                             reference_assets=[{'mime': 'image/png', 'data': PNG}])
        for answer, place in ((generated, folder), (edited, edit_folder)):
            self.assertEqual(answer['state'], 'complete')
            self.assertEqual((place / answer['assets'][0]['file']).read_bytes(), PNG)
            self.assertEqual((answer['usage']['input_tokens'], answer['usage']['output_tokens']), (7, 9))
            self.assertIsNone(answer['usage']['cost'])
            validate_image_result(answer)
        self.assertEqual((generated['operation'], edited['operation']), ('generate', 'edit'))
        command = edit_worker.calls[0][0]
        self.assertEqual(command[command.index('--image') + 1], str((edit_folder / 'reference-0.png').resolve()))
        self.assertEqual(command[command.index('--enable') + 1], 'image_generation')
        self.assertNotIn('--image', worker.calls[0][0])
        # The same contract keys as the Gemini adapter, with no provider-specific additions.
        gemini = Gemini(self.temp, model='synthetic-model', key=lambda: None)
        self.assertEqual(set(generated), set(gemini.generate(attempt_id='attempt3', brief=self.brief)))

    def test_no_unrelated_capability_is_enabled_alongside_the_image_tool(self):
        worker = Worker()
        self.adapter(worker)[0].generate(attempt_id='attempt1', brief=self.brief)
        command = worker.calls[0][0]
        enabled = [command[i + 1] for i, part in enumerate(command) if part == '--enable']
        self.assertEqual(enabled, ['image_generation'])
        pairs = {(command[i], command[i + 1]) for i in range(len(command) - 1)}
        for feature in ('shell_tool', 'unified_exec', 'plugins', 'apps', 'browser_use', 'computer_use',
                        'in_app_browser', 'multi_agent', 'hooks', 'remote_plugin'):
            self.assertIn(('--disable', feature), pairs)
        self.assertIn(('-c', 'web_search="disabled"'), pairs)
        self.assertIn('--ignore-user-config', command)
        self.assertIn('--ephemeral', command)
        self.assertEqual(command[-1], '-')

    def test_an_installed_codex_without_its_image_tool_fails_clearly(self):
        cases = {
            'turn completed with no image': Worker(image=None),
            'unknown feature flag': Worker(image=None, returncode=2,
                                           stderr='error: unknown feature `image_generation`', events=''),
            'unsupported argument': Worker(image=None, returncode=2, stderr='unexpected argument --enable', events=''),
            'tool refused in this mode': Worker(image=None, events=stream(
                {'type': 'thread.started', 'thread_id': THREAD},
                {'type': 'turn.failed', 'error': {'message': 'image_generation is not available'}})),
        }
        for name, worker in cases.items():
            with self.subTest(case=name):
                answer = self.adapter(worker)[0].generate(attempt_id='attempt1', brief=self.brief)
                self.assertEqual((answer['state'], answer['reason']), ('failed', 'image-tool-unavailable'))
                self.assertEqual(answer['assets'], [])
                self.assertEqual(len(worker.calls), 1)

    def test_sign_in_and_quota_come_from_failure_diagnostics_not_model_prose(self):
        cases = [
            (Worker(image=None, returncode=1, stderr='Error: Not logged in. Run codex login.', events=''), 'sign-in-required'),
            (Worker(image=None, events=stream({'type': 'turn.failed', 'error': {'message': '401 Unauthorized'}})),
             'sign-in-required'),
            (Worker(image=None, events=stream({'type': 'turn.failed', 'error': {'message': 'rate_limit_exceeded'}})),
             'quota'),
            (Worker(image=None, returncode=1, stderr='You have hit your usage limit.', events=''), 'quota'),
            # A turn.failed event fails the request even when an image file is present.
            (Worker(events=stream({'type': 'turn.failed', 'error': {'message': 'Too Many Requests'}})), 'quota'),
            # Prose that mentions quota or sign-in is not a diagnosis.
            (Worker(image=None, returncode=1, events=stream({'type': 'item.completed', 'item': {
                'type': 'agent_message', 'text': 'The source discusses quota and sign-in.'}})), 'image-tool-unavailable'),
        ]
        for worker, reason in cases:
            with self.subTest(reason=reason):
                answer = self.adapter(worker)[0].generate(attempt_id='attempt1', brief=self.brief)
                self.assertEqual((answer['state'], answer['reason']), ('failed', reason))
                self.assertEqual(answer['assets'], [])
                self.assertNotIn('Unauthorized', json.dumps(answer))
                self.assertEqual(len(worker.calls), 1)

    def test_malformed_returned_files_are_refused_as_invalid_assets(self):
        bad = bytearray(PNG)
        bad[-5] ^= 0xFF  # A broken IEND checksum.
        for name, raw in (('not a PNG', b'not an image'), ('broken checksum', bytes(bad)),
                          ('empty file', b'')):
            with self.subTest(case=name):
                adapter, folder = self.adapter(Worker(image=raw))
                answer = adapter.generate(attempt_id='attempt1', brief=self.brief)
                self.assertEqual((answer['state'], answer['reason']), ('failed', 'invalid-asset'))
                self.assertEqual(answer['assets'], [])
                self.assertEqual([p.name for p in folder.iterdir() if p.suffix == '.png'], [])

    def test_timeouts_and_cancellation_stay_unknown_or_cancelled_and_never_retry(self):
        for state, reason in (('unknown', 'timeout'), ('cancelled', 'stopped')):
            with self.subTest(state=state):
                worker = Worker(image=None, returncode=-9, state=state, events='')
                answer = self.adapter(worker)[0].edit(attempt_id='attempt1', brief=self.brief,
                                                      reference_assets=[{'mime': 'image/png', 'data': PNG}])
                self.assertEqual((answer['state'], answer['reason']), (state, reason))
                self.assertEqual(len(worker.calls), 1)

    def test_reported_usage_is_kept_or_left_unknown_but_never_invented(self):
        events = stream({'type': 'thread.started', 'thread_id': THREAD},
                        {'type': 'turn.completed', 'usage': {'input_tokens': 'many', 'output_tokens': -1}})
        answer = self.adapter(Worker(events=events))[0].generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual(answer['state'], 'complete')
        self.assertEqual(answer['usage'], {'cost': None, 'currency': None, 'input_tokens': None, 'output_tokens': None})

    def test_a_clean_turn_has_no_failure_reason(self):
        self.assertIsNone(failure_reason({'returncode': 0, 'events': COMPLETED}))
        self.assertEqual(failure_reason({'returncode': 0, 'events': stream({'type': 'error', 'message': 'quota'})}), 'quota')

    def test_a_retried_stream_error_followed_by_a_completed_turn_is_not_a_failure(self):
        # Codex reports stream retries as error events; a later completed turn recovered them.
        events = stream({'type': 'thread.started', 'thread_id': THREAD},
                        {'type': 'error', 'message': 'Reconnecting... 1/5 (stream disconnected before completion)'},
                        {'type': 'error', 'message': 'Reconnecting... 2/5 (rate limit while reconnecting)'},
                        {'type': 'turn.completed', 'usage': {'input_tokens': 7, 'output_tokens': 9}})
        self.assertIsNone(failure_reason({'returncode': 0, 'events': events}))
        adapter, folder = self.adapter(Worker(events=events))
        answer = adapter.generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual(answer['state'], 'complete', 'A recovered request must not look failed and invite a paid retry.')
        self.assertEqual((folder / answer['assets'][0]['file']).read_bytes(), PNG)
        # Local recovery applies the same rule to the saved event stream.
        import os
        os.environ['CODEX_HOME'] = str(self.temp / 'codex')
        output = self.temp / 'codex' / 'generated_images' / THREAD
        output.mkdir(parents=True)
        (output / 'image.png').write_bytes(PNG)
        recovering = self.temp / 'recovering'
        recovering.mkdir()
        (recovering / 'events.jsonl').write_text(events)
        self.assertEqual(saved_output(recovering), output)

    def test_an_error_with_nothing_after_it_ends_the_request(self):
        events = stream({'type': 'thread.started', 'thread_id': THREAD},
                        {'type': 'turn.completed'},
                        {'type': 'error', 'message': 'stream disconnected before completion'})
        self.assertEqual(failure_reason({'returncode': 0, 'events': events}), 'provider-refusal')
        answer = self.adapter(Worker(events=events))[0].generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual(answer['state'], 'failed')
        self.assertEqual(answer['assets'], [])
        recovering = self.temp / 'recovering'
        recovering.mkdir()
        (recovering / 'events.jsonl').write_text(events)
        with self.assertRaises(ValueError):
            saved_output(recovering, root=self.temp / 'codex-output')

    def test_please_run_login_is_a_sign_in_problem(self):
        worker = Worker(image=None, returncode=1, stderr='Not signed in. Please run /login to continue.', events='')
        answer = self.adapter(worker)[0].generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual((answer['state'], answer['reason']), ('failed', 'sign-in-required'))
