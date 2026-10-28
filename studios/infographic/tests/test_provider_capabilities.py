import ast
import json
from pathlib import Path
import unittest

from helpers import Isolated, ROOT
from runner import provider_capabilities as capabilities


class CapabilityTests(Isolated):
    def test_missing_key_signin_tool_and_inspection_are_distinct(self):
        result = capabilities.report('claude', installed=True, authenticated=False,
                                     credential_present=False, model_access=False, inspection=False)
        self.assertEqual(set(result['problems']), {'sign-in-required', 'gemini-key-required',
                                                 'image-model-unavailable', 'manual-image-review-required'})
        self.assertEqual(result['state'], 'unavailable')
        codex = capabilities.report('codex', installed=True, authenticated=True, image_tool=False)
        self.assertEqual(codex['problems'], ['image-tool-unavailable'])
        self.assertFalse(codex['credential_required'])

    def test_local_discovery_cannot_claim_live_success(self):
        result = capabilities.report('codex', installed=True, authenticated=True,
                                     image_tool=True, inspection=True)
        self.assertEqual(result['state'], 'unverified')
        self.assertFalse(result['live_verified'])
        unknown = capabilities.report('codex', installed=True, image_tool=True,
                                      inspection=True, live_verified=True)
        self.assertIn('sign-in-not-checked', unknown['unknown'])
        self.assertFalse(unknown['live_verified'])
        with self.assertRaises(ValueError):
            capabilities.report('claude', installed=True, credential_present='a-secret-key')

    def test_codex_command_does_not_weaken_existing_workers(self):
        job = self.temp / 'job'
        job.mkdir()
        (job / 'reference.png').write_bytes(b'fixture')
        command = capabilities.codex_image_command(job, ['reference.png'])
        self.assertIn('--image', command)
        self.assertEqual(command[command.index('--enable') + 1], 'image_generation')
        tree = ast.parse((ROOT / 'core/studio_core/shared_runner/agents.py').read_text())
        baseline = next(ast.literal_eval(n.value) for n in tree.body
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CODEX_OFF' for t in n.targets))
        self.assertIn('image_generation', baseline)
        self.assertEqual(set(capabilities.CODEX_DISABLED), set(baseline) - {'image_generation'})
        for feature in capabilities.CODEX_DISABLED:
            self.assertIn(['--disable', feature], [command[i:i + 2] for i in range(len(command) - 1)])
        outside = self.temp / 'other.png'
        outside.write_bytes(b'fixture')
        with self.assertRaises(ValueError):
            capabilities.codex_image_command(job, [outside])

    def test_claude_inspection_is_read_only_with_no_extra_mcp_servers(self):
        job = self.temp / 'job'
        job.mkdir()
        config = job / 'mcp.json'
        config.write_text(json.dumps({'mcpServers': {}}))
        command = capabilities.claude_inspection_command(job, config)
        self.assertEqual(command[command.index('--tools') + 1], 'Read')
        self.assertIn('--restricted', command)
        self.assertIn('--strict-mcp-config', command)
        config.write_text(json.dumps({'mcpServers': {'unexpected': {}}}))
        with self.assertRaises(ValueError):
            capabilities.claude_inspection_command(job, config)

    def test_children_do_not_inherit_provider_credentials_or_git_overrides(self):
        values = {'PATH': '/bin', 'HOME': str(self.home), 'GEMINI_API_KEY': 'sentinel',
                  'OPENAI_API_KEY': 'sentinel', 'ANTHROPIC_API_KEY': 'sentinel',
                  'GIT_DIR': 'wrong', 'CUSTOM_SECRET': 'sentinel'}
        self.assertEqual(capabilities.private_child_environment(values),
                         {'PATH': '/bin', 'HOME': str(self.home)})
