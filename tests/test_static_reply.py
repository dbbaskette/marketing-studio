"""A page's scripts and styles are answered "not changed" or compressed, never stored blind."""
import gzip
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
from studio_core import server  # noqa: E402

BODY = b'const answer = 42;\n' * 400
KIND = 'text/javascript; charset=utf-8'


class StaticReplyTests(unittest.TestCase):
    def test_a_browser_that_reads_gzip_is_sent_the_same_bytes_compressed(self):
        status, kind, body, extra = server.static_reply(KIND, BODY, {'Accept-Encoding': 'gzip, deflate'})
        self.assertEqual((int(status), kind), (200, KIND))
        self.assertEqual(gzip.decompress(body), BODY)
        self.assertLess(len(body), len(BODY) // 4)
        self.assertEqual(extra['Content-Encoding'], 'gzip')
        self.assertEqual(extra['Cache-Control'], 'no-cache')
        self.assertEqual(extra['Vary'], 'Accept-Encoding')

    def test_a_browser_that_does_not_is_sent_them_plain(self):
        status, _, body, extra = server.static_reply(KIND, BODY, {})
        self.assertEqual((int(status), body), (200, BODY))
        self.assertNotIn('Content-Encoding', extra)

    def test_a_current_copy_is_answered_not_changed_with_no_body(self):
        for headers in ({}, {'Accept-Encoding': 'gzip'}):
            tag = server.static_reply(KIND, BODY, headers)[3]['ETag']
            status, kind, body, extra = server.static_reply(KIND, BODY, {**headers, 'If-None-Match': tag})
            self.assertEqual((int(status), kind, body), (304, None, b''))
            self.assertEqual(extra['ETag'], tag)

    def test_changed_bytes_are_sent_again(self):
        tag = server.static_reply(KIND, BODY, {})[3]['ETag']
        status, _, body, extra = server.static_reply(KIND, BODY + b'// changed\n', {'If-None-Match': tag})
        self.assertEqual(int(status), 200)
        self.assertNotEqual(extra['ETag'], tag)

    def test_the_plain_and_compressed_copies_have_different_marks(self):
        plain = server.static_reply(KIND, BODY, {})[3]['ETag']
        packed = server.static_reply(KIND, BODY, {'Accept-Encoding': 'gzip'})[3]['ETag']
        self.assertNotEqual(plain, packed)


if __name__ == '__main__':
    unittest.main()
