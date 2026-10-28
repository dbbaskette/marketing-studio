"""Provider transports are injected; tests never read real credentials or start assistants."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import socket
from unittest import mock

from helpers import Isolated
from graphics_fixtures import png
PNG = png()
from runner.images.codex import Codex
from runner.images.gemini import Gemini
from runner.validation import validate_image_result


class AdapterTests(Isolated):
    def setUp(self):
        super().setUp()
        self.folder = self.temp / 'attempt'
        self.folder.mkdir()
        self.brief = {'prompt': 'Draw two illustrative service stages; no words or numbers.'}

    def response(self):
        return {'id': 'synthetic-request', 'status': 'completed', 'steps': [{'type': 'model_output', 'content': [
            {'type': 'image', 'mime_type': 'image/png', 'data': base64.b64encode(PNG).decode()}]}],
            'usage': {'total_input_tokens': 10, 'total_output_tokens': 20}}

    def test_gemini_generate_and_reference_edit_use_only_explicit_parts_without_grounding(self):
        calls = []
        def transport(model, key, payload, seconds):
            calls.append((model, key, payload, seconds))
            return 200, self.response()
        adapter = Gemini(self.folder, model='synthetic-image-model', key=lambda: 'synthetic-private-key', transport=transport)
        generated = adapter.generate(attempt_id='attempt1', brief=self.brief)
        edited = adapter.edit(attempt_id='attempt2', brief=self.brief,
                              reference_assets=[{'mime': 'image/png', 'data': PNG}])
        self.assertEqual((generated['state'], edited['state']), ('complete', 'complete'))
        self.assertEqual(len(calls[0][2]['input']), 1)
        self.assertEqual(len(calls[1][2]['input']), 2)
        self.assertNotIn('tools', calls[0][2])
        self.assertFalse(calls[0][2]['store'])
        self.assertEqual(calls[0][2]['response_format']['mime_type'], 'image/png')
        for answer in (generated, edited):
            self.assertNotIn('synthetic-private-key', json.dumps(answer))
            self.assertIsNone(answer['usage']['cost'])
            self.assertEqual(answer['usage']['input_tokens'], 10)
            self.assertEqual((self.folder / answer['assets'][0]['file']).read_bytes(), PNG)
            self.assertEqual(answer['inspection'], 'unknown')
            validate_image_result(answer)

    def test_gemini_errors_are_normalized_without_reflected_secrets_or_retry(self):
        for status, state, reason in [(401, 'failed', 'sign-in-required'),
                                      (403, 'failed', 'image-model-unavailable'),
                                      (404, 'failed', 'image-model-unavailable'),
                                      (429, 'failed', 'quota'), (400, 'failed', 'provider-refusal'),
                                      (503, 'unknown', 'provider-refusal')]:
            transport = mock.Mock(return_value=(status, {'error': 'synthetic-private-key'}))
            adapter = Gemini(self.folder, model='synthetic-model', key=lambda: 'synthetic-private-key', transport=transport)
            answer = adapter.generate(attempt_id='attempt1', brief=self.brief)
            self.assertEqual((answer['state'], answer['reason']), (state, reason))
            self.assertNotIn('synthetic-private-key', json.dumps(answer))
            transport.assert_called_once()

    def test_gemini_timeout_remains_unknown_and_missing_key_sends_nothing(self):
        transport = mock.Mock(side_effect=socket.timeout())
        adapter = Gemini(self.folder, model='synthetic-model', key=lambda: 'synthetic-key', transport=transport)
        answer = adapter.generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual((answer['state'], answer['reason']), ('unknown', 'timeout'))
        transport.assert_called_once()
        transport.reset_mock()
        adapter.key = lambda: None
        self.assertEqual(adapter.generate(attempt_id='attempt2', brief=self.brief)['reason'], 'gemini-key-required')
        transport.assert_not_called()
        self.assertEqual(adapter.readiness()['state'], 'unavailable')

    def test_gemini_refuses_bad_media_and_does_not_call_a_provider_for_status_cancel_or_readiness(self):
        bad = self.response()
        bad['steps'][0]['content'][0]['data'] = base64.b64encode(b'not an image').decode()
        transport = mock.Mock(return_value=(200, bad))
        adapter = Gemini(self.folder, model='synthetic-model', key=lambda: 'synthetic-key', transport=transport)
        self.assertEqual(adapter.generate(attempt_id='attempt1', brief=self.brief)['reason'], 'invalid-asset')
        transport.reset_mock()
        self.assertEqual(adapter.readiness()['state'], 'unverified')
        adapter.status(attempt_id='attempt1')
        adapter.cancel(attempt_id='attempt1')
        transport.assert_not_called()

    def test_codex_collects_actual_owned_generated_files_and_preserves_other_tool_restrictions(self):
        calls = []
        def run(command, prompt, folder, seconds, stop):
            calls.append((command, prompt))
            output = folder / 'generated_images'
            output.mkdir()
            (output / 'synthetic.png').write_bytes(PNG)
            return {'state': 'complete', 'returncode': 0, 'events': json.dumps(
                {'type': 'turn.completed', 'usage': {'input_tokens': 12, 'output_tokens': 20}})}
        adapter = Codex(self.folder, run=run)
        answer = adapter.generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual(answer['state'], 'complete')
        self.assertEqual((self.folder / answer['assets'][0]['file']).read_bytes(), PNG)
        command = calls[0][0]
        self.assertIn('image_generation', command)
        self.assertIn('--ignore-user-config', command)
        self.assertIn('--ephemeral', command)
        for feature in ('shell_tool', 'unified_exec', 'plugins', 'browser_use', 'multi_agent'):
            self.assertIn(['--disable', feature], [command[i:i+2] for i in range(len(command)-1)])
        self.assertEqual(answer['usage']['input_tokens'], 12)
        self.assertIsNone(answer['usage']['cost'])

    def test_codex_success_message_alone_is_not_an_image_and_external_paths_are_not_adopted(self):
        run = mock.Mock(return_value={'state': 'complete', 'returncode': 0,
                                    'events': '{"type":"item.completed","item":{"type":"agent_message","text":"Image made at /private/image.png"}}'})
        answer = Codex(self.folder, run=run).generate(attempt_id='attempt1', brief=self.brief)
        self.assertEqual((answer['state'], answer['reason']), ('failed', 'image-tool-unavailable'))
        self.assertEqual(answer['assets'], [])
        outside = self.temp / 'outside'
        outside.mkdir()
        (outside / 'image.png').write_bytes(PNG)
        (self.folder / 'generated_images').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            Codex(self.folder, run=run).generate(attempt_id='attempt2', brief=self.brief)

    def test_codex_edit_stages_references_and_timeout_never_retries(self):
        run = mock.Mock(return_value={'state': 'unknown', 'returncode': -9, 'events': ''})
        adapter = Codex(self.folder, run=run)
        answer = adapter.edit(attempt_id='attempt1', brief=self.brief,
                              reference_assets=[{'mime': 'image/png', 'data': PNG}])
        self.assertEqual(answer['state'], 'unknown')
        self.assertEqual((self.folder / 'reference-0.png').read_bytes(), PNG)
        self.assertIn('--image', run.call_args.args[0])
        run.assert_called_once()

    def test_direct_https_uses_fixed_endpoint_and_one_total_response_deadline(self):
        from runner.images import gemini
        response = mock.Mock(status=200)
        response.read1.side_effect = [b'{"status":"completed"}', b'']
        connection = mock.Mock(); connection.getresponse.return_value = response
        with mock.patch.object(gemini.http.client, 'HTTPSConnection', return_value=connection):
            status, answer = gemini.https('synthetic-model', 'synthetic-key', {'model': 'synthetic-model', 'store': False}, 2)
        self.assertEqual((status, answer['status']), (200, 'completed'))
        sent = connection.request.call_args
        self.assertEqual(sent.args[:2], ('POST', '/v1beta/interactions'))
        self.assertNotIn('synthetic-key', sent.kwargs['body'].decode())
        self.assertEqual(sent.kwargs['headers']['x-goog-api-key'], 'synthetic-key')
        connection.close.assert_called_once()
        response.read1.side_effect = [b'partial', b'']
        with mock.patch.object(gemini.http.client, 'HTTPSConnection', return_value=connection), mock.patch.object(gemini.time, 'monotonic', side_effect=[0, 0, 0, 3]):
            with self.assertRaises(TimeoutError): gemini.https('synthetic-model', 'synthetic-key', {}, 2)
