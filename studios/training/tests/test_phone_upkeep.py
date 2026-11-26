"""GitHub issue #539: a phone on Marketing Studio's private link is told no folder of this
computer by the skills' upkeep report, not even inside a sentence. Four skill links are really
broken on disk and said by the runner's own upkeep check; GET /api/status, GET /api/setup and
the five upkeep routes are asked with the network bridge's header, then without it. Nothing
here starts an agent or touches the network."""
import json
import sys
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import helpers  # noqa: E402,F401,I001  the path-setting imports must come before runner
from runner_support import StudioCase  # noqa: E402
import computer  # noqa: E402
import desk  # noqa: E402
from runner import page, upkeep  # noqa: E402
from studio_core.shared_runner import caller  # noqa: E402
from workspace import WorkspaceError  # noqa: E402

PORT = 8765
ROUTES = {'/api/companions': {}, '/api/upgrade': {'version': '1.0.0'}, '/api/restart': {},
          '/api/versions': {'dismiss': 'brand'}, '/api/brand/install': {'commit': 'a' * 40}}


def never(*args, **kwargs):
    raise AssertionError('A test must never look at the real computer.')


class Keeping:
    """What looks after the skills here, answering every upkeep route with one report."""

    def __init__(self, found):
        self.found = found

    def report(self):
        return self.found

    def again(self):
        pass

    def close(self):
        pass

    def update(self, working):
        return self.found

    def upgrade(self, working, version):
        return self.found

    def restart(self, working):
        return self.found

    def dismiss(self, key):
        return self.found

    def install_brand(self, working, commit):
        return self.found


class PhoneUpkeepTests(StudioCase):
    def setUp(self):
        super().setUp()
        for patcher in (mock.patch.object(computer, 'run', never),
                        mock.patch.object(computer, 'reach', never)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.page = page.RunnerPage(PORT, self.engine)
        self.origin = f'http://127.0.0.1:{PORT}'

    def ask(self, method, target, sent=None, remote=False):
        made = Message()
        made['Host'] = f'127.0.0.1:{PORT}'
        made[desk.TOKEN_HEADER] = self.page.token
        if method == 'POST':
            made['Origin'] = self.origin
            made['Content-Type'] = 'application/json'
        if remote:
            made['X-Marketing-Studio-Via'] = 'network'
        body = json.dumps(sent).encode() if sent is not None else None
        try:
            status, _, data = self.page.answer(target, made, method, body)
        except (desk.Refusal, WorkspaceError) as refusal:
            self.fail(f'{target}: {refusal}')
        self.assertEqual(int(status), 200, target)
        return json.loads(data)

    def answers(self, remote):
        found = {('GET', target): self.ask('GET', target, remote=remote)
                 for target in ('/api/status', '/api/setup')}
        for target, sent in ROUTES.items():
            found[('POST', target)] = self.ask('POST', target, sent, remote=remote)
        return found

    def broken_links(self):
        """Four skill links really broken on disk, each said by the runner's upkeep check:
        one pointing at a copy that is gone, one replaced by a folder of someone's own, one
        whose assistant's skill folder is gone, and one put back."""
        home_dir = self.base / 'home'
        copy = self.base / 'copy'
        copy.mkdir()
        (copy / 'SKILL.md').write_text('stand-in\n')
        folders = {'claude': home_dir / '.claude' / 'skills', 'codex': home_dir / '.agents' / 'skills',
                   'gemini': home_dir / '.gemini' / 'skills', 'cursor': home_dir / '.cursor' / 'skills'}
        for harness in ('claude', 'codex', 'cursor'):
            folders[harness].mkdir(parents=True)
        links = {harness: folder / 'training-studio' for harness, folder in folders.items()}
        gone = self.base / 'gone-copy'
        links['claude'].symlink_to(gone)            # its copy is not there any more
        links['codex'].mkdir()                      # a folder of someone's own
        installing = SimpleNamespace(
            NAME='training-studio',
            HARNESS={'claude': 'Claude Code', 'codex': 'Codex', 'gemini': 'Gemini CLI',
                     'cursor': 'Cursor'},
            replace_link=lambda link, target: link.symlink_to(target))
        state = {'links': {harness: {'path': str(link), 'target': str(
            gone if harness == 'claude' else copy)} for harness, link in links.items()}}
        found = [upkeep.Upkeep._link(SimpleNamespace(home=home_dir), installing, state, harness,
                                     True) for harness in links]
        self.assertEqual([link['state'] for link in found],
                         ['missing', 'left alone', 'left alone', 'repaired'])
        self.assertTrue(all(str(self.base) in link['says'] for link in found), found)
        return {'links': found, 'repaired': [found[3]['says']], 'problem': None}

    def folders(self, value):
        """Every string anywhere in `value` that names a folder of this test, whole or inside
        a sentence."""
        if isinstance(value, dict):
            return [found for one in value.values() for found in self.folders(one)]
        if isinstance(value, list):
            return [found for one in value for found in self.folders(one)]
        here = (str(self.base), str(self.base.resolve()))
        return [value] if isinstance(value, str) and any(f in value for f in here) else []

    def test_a_really_broken_skill_link_is_said_to_a_phone_without_its_folder(self):
        found = self.broken_links()
        self.engine.upkeep = Keeping(found)
        phone = self.answers(remote=True)
        for asked, reply in phone.items():
            with self.subTest(asked=asked):
                self.assertEqual(self.folders(reply['upkeep']), [])
                self.assertEqual([link['says'] for link in reply['upkeep']['links']],
                                 [caller.FOLDER_SAID] * 4)
                self.assertEqual([link['state'] for link in reply['upkeep']['links']],
                                 ['missing', 'left alone', 'left alone', 'repaired'])
        # On this computer every answer carries the report as it is, each folder named.
        here = self.answers(remote=False)
        for asked, reply in here.items():
            with self.subTest(asked=asked, remote=False):
                self.assertEqual(reply['upkeep'], found)


if __name__ == '__main__':
    unittest.main()
