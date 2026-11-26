"""The one rule for a repository address given from a phone on the private link (GitHub issue
#539): https or ssh, or user@host:path, of a computer other than this one."""
import ast
import unittest
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  (puts core/ on the path)
from studio_core import repository_address
from studio_core.repository_address import web_repository

HOST = 'Synthetic-Mac.local'


class WebRepositoryTests(unittest.TestCase):
    def setUp(self):
        named = mock.patch.object(repository_address.socket, 'gethostname', return_value=HOST)
        named.start()
        self.addCleanup(named.stop)

    def test_addresses_of_another_computer_are_accepted(self):
        for address in ('https://example.com/org/brands.git', 'https://git.example.com:8443/o/r',
                        'ssh://git@example.com/org/brands.git', 'ssh://example.com:2222/r.git',
                        'git@example.com:org/brands.git', 'me@build-server:repos/brands',
                        # Addresses on the local network are other computers.
                        'https://192.168.1.20/o/r.git', 'ssh://git@10.0.0.5/r.git', 'git@172.16.0.9:r.git',
                        'https://[fe80::1]/r.git', 'HTTPS://Example.com/r.git'):
            with self.subTest(address=address):
                self.assertTrue(web_repository(address))

    def test_a_folder_or_another_kind_of_address_is_refused(self):
        for address in ('/Users/someone/brands', '~/brands', 'brands', './brands', 'file:///Users/x/repo',
                        'http://example.com/org/brands.git', 'git://example.com/r.git', 'ftp://example.com/r',
                        'https://', 'https:///r.git', 'ssh://', 'me@:path', '@example.com:path', 'example.com:path',
                        '', None, 5, ['https://example.com/r.git']):
            with self.subTest(address=address):
                self.assertFalse(web_repository(address))

    def test_whitespace_control_characters_and_a_leading_dash_are_refused(self):
        for address in ('https://example.com/r.git ', ' https://example.com/r.git', 'https://example.com/a b',
                        'https://example.com/r\t', 'https://example.com/r\n', 'https://example.com/r\x00',
                        'https://example.com/r\x7f', 'git@example.com:r ', 'ssh://-oProxyCommand=x/r',
                        'ssh://git@-example.com/r', 'git@-example.com:r', 'https://-example.com/r'):
            with self.subTest(address=address):
                self.assertFalse(web_repository(address))

    def test_this_computer_is_refused_however_it_is_written(self):
        for address in (
                'https://localhost/a', 'https://LOCALHOST/a', 'https://localhost./a', 'ssh://localhost/Users/x/repo',
                'me@localhost:/Users/x/repo', 'https://studio.localhost/a', 'git@a.b.localhost:r',
                'https://127.0.0.1/r', 'https://127.0.0.1:8000/x.git', 'https://127.1.2.3/r', 'git@127.0.0.1:r',
                'https://127.1/r', 'https://2130706433/r', 'https://0x7f.0.0.1/r', 'https://017700000001/r',
                'https://[::1]/r', 'ssh://[::1]:22/r', 'https://[::ffff:127.0.0.1]/r', 'https://[0:0:0:0:0:0:0:1]/r',
                'https://0.0.0.0/r', 'https://0/r', 'https://[::]/r', 'git@0.0.0.0:r',
                'https://synthetic-mac/r', 'https://Synthetic-Mac.local/r', 'https://SYNTHETIC-MAC.LOCAL./r',
                'git@synthetic-mac:r', 'ssh://synthetic-mac.local/r', 'http://127.0.0.1:8000/x.git'):
            with self.subTest(address=address):
                self.assertFalse(web_repository(address))
        # Another computer whose name only begins like this one's.
        self.assertTrue(web_repository('https://synthetic-mac-2.local/r'))

    def test_a_host_holds_only_name_characters_and_no_user_starts_with_a_dash(self):
        # Second review, item 1: Git decodes a percent-encoded host into another one.
        for address in ('ssh://git@%6c%6fcalhost/x', 'ssh://%31%32%37.0.0.1/srv/x.git',
                        'https://%65xample.com/r.git', 'https://example.com%2f@localhost/r',
                        'git@%6c%6fcalhost:x', 'git@exa%6dple.com:x', 'https://exa_mple.com/r',
                        'https://example.com:/r', 'https://example.com:http/r', 'https://[::1%25lo]/r',
                        'https://[g::1]/r', 'https://[::1]x/r',
                        # A user name that starts with a dash, in every form.
                        'ssh://-oProxyCommand=x@example.com/r', 'https://-user@example.com/r',
                        '-user@example.com:x', 'ssh://@example.com/r', '@example.com:x',
                        # An IPv6 address carrying a loopback or unspecified IPv4 address.
                        'https://[::127.0.0.1]/r', 'ssh://[0:0:0:0:0:0:7f00:1]/x', 'ssh://[::ffff:7f00:1]/r', 'https://[2002:7f00:1::]/r',
                        'https://[64:ff9b::7f00:1]/r', 'https://[::0.0.0.0]/r', 'https://[2002::]/r'):
            with self.subTest(address=address):
                self.assertFalse(web_repository(address))
        for address in ('https://[2001:db8::1]/r', 'https://[fe80::1%en0]/r', 'ssh://git@example.com:22/r',
                        'https://user@example.com/r', 'git@a-b.example.com:x'):
            with self.subTest(address=address):
                self.assertTrue(web_repository(address))

    def test_a_host_name_without_local_is_compared_with_and_without_it(self):
        with mock.patch.object(repository_address.socket, 'gethostname', return_value='build-box'):
            self.assertFalse(web_repository('https://build-box.local/r'))
            self.assertFalse(web_repository('git@BUILD-BOX:r'))
            self.assertTrue(web_repository('https://build-box.example.com/r'))

    def test_every_studio_can_import_it(self):
        # Standard library only, and nothing from the deck studios' shared runner.
        source = Path(repository_address.__file__).read_text()
        imported = {name.split('.')[0] for node in ast.walk(ast.parse(source))
                    for name in ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                                 else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])}
        self.assertEqual(imported, {'__future__', 'ipaddress', 're', 'socket', 'urllib'})
        # Each studio links the whole shared core, so the module travels with every one.
        for studio in ('blog/skills/blog-studio/scripts', 'presentation/skills/presentation-studio/scripts',
                       'training/skills/training-studio/scripts', 'infographic/runner'):
            linked = Path(__file__).resolve().parents[1] / 'studios' / studio / 'studio_core'
            self.assertTrue(linked.is_symlink(), studio)
            self.assertTrue((linked / 'repository_address.py').is_file(), studio)


if __name__ == '__main__':
    unittest.main()
