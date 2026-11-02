"""The look at whether an assistant's service can be reached keeps to one time limit.

Nothing here contacts the network: the connection and the certificate check are stand-ins.
"""
import ssl
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))

from studio_core import reachability  # noqa: E402


class BlockedTests(unittest.TestCase):
    def look(self, seconds=0.3, connect=None, wrap=None):
        context = mock.Mock()
        if wrap:
            context.wrap_socket.side_effect = wrap
        started = time.monotonic()
        with mock.patch.object(reachability.urllib.request, 'getproxies', return_value={}), \
                mock.patch.object(reachability.socket, 'create_connection',
                                  side_effect=connect), \
                mock.patch.object(reachability.ssl, 'create_default_context',
                                  return_value=context):
            found = reachability.blocked('service.example.com', seconds)
        return found, time.monotonic() - started

    def test_a_slow_address_lookup_ends_with_the_time_limit_and_says_nothing(self):
        found, took = self.look(connect=lambda *args, **named: time.sleep(2))
        self.assertIsNone(found)
        self.assertLess(took, 1.5)

    def test_a_connection_that_times_out_says_nothing_either(self):
        found, _ = self.look(connect=TimeoutError('timed out'))
        self.assertIsNone(found)

    def test_a_refused_connection_and_an_intercepted_one_are_told_apart(self):
        found, _ = self.look(connect=OSError('Network is unreachable'))
        self.assertEqual(found, ('unreachable', 'Network is unreachable'))
        failure = ssl.SSLCertVerificationError('certificate verify failed')
        failure.verify_message = 'self-signed certificate in certificate chain'
        found, _ = self.look(wrap=failure)
        self.assertEqual(found, ('intercepted', 'self-signed certificate in certificate chain'))

    def test_a_look_that_fails_in_another_way_never_raises(self):
        found, _ = self.look(connect=RuntimeError('synthetic'))
        self.assertIsNone(found)


if __name__ == '__main__':
    unittest.main()
