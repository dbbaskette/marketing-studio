"""A page's scripts and styles are answered "not changed" or compressed, never stored blind."""
import gzip
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest import mock

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


class StaticFileTests(unittest.TestCase):
    """Counted, never timed: stat() calls, reads and hashes of a script asked for again."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'page.js'
        self.path.write_bytes(BODY)
        server._FILES.clear()
        self.addCleanup(server._FILES.clear)

    def counted(self):
        stats, opens, hashes = [], [], []
        real_stat, real_hash = server.os.stat, server.hashlib.sha256

        def stat(path, *args, **kwargs):
            stats.append(path)
            return real_stat(path, *args, **kwargs)

        def opened(path, *args, **kwargs):
            opens.append(path)
            return open(path, *args, **kwargs)

        def hashed(*args, **kwargs):
            hashes.append(args)
            return real_hash(*args, **kwargs)
        patches = (mock.patch.object(server.os, 'stat', stat),
                   mock.patch.object(server, 'open', opened, create=True),
                   mock.patch.object(server.hashlib, 'sha256', hashed))
        return patches, stats, opens, hashes

    def test_a_current_copy_costs_one_stat_and_no_read_or_hash(self):
        for headers in ({}, {'Accept-Encoding': 'gzip'}):
            with self.subTest(headers=headers):
                status, kind, body, extra = server.static_file(KIND, self.path, headers)
                self.assertEqual(int(status), 200)
                patches, stats, opens, hashes = self.counted()
                with patches[0], patches[1], patches[2]:
                    status, kind, body, again = server.static_file(
                        KIND, self.path, {**headers, 'If-None-Match': extra['ETag']})
                self.assertEqual((int(status), kind, body), (304, None, b''))
                self.assertEqual(again['ETag'], extra['ETag'])
                self.assertEqual((len(stats), opens, hashes), (1, [], []))

    def test_the_same_reply_as_static_reply(self):
        for headers in ({}, {'Accept-Encoding': 'gzip, deflate'}):
            self.assertEqual(server.static_file(KIND, self.path, headers),
                             server.static_reply(KIND, BODY, headers))

    def test_a_changed_file_is_served_fresh_at_once(self):
        tag = server.static_file(KIND, self.path, {})[3]['ETag']
        changed = BODY + b'// changed\n'
        self.path.write_bytes(changed)
        status, _, body, extra = server.static_file(KIND, self.path, {'If-None-Match': tag})
        self.assertEqual((int(status), body), (200, changed))
        self.assertNotEqual(extra['ETag'], tag)
        # The same size, written again: its times differ, so it is read again too.
        same_size = changed.replace(b'42', b'43')
        self.path.write_bytes(same_size)
        later = self.path.stat().st_mtime_ns + 1_000_000
        os.utime(self.path, ns=(later, later))
        status, _, body, _ = server.static_file(KIND, self.path, {'If-None-Match': extra['ETag']})
        self.assertEqual((int(status), body), (200, same_size))

    def test_at_most_static_files_are_held(self):
        for number in range(server.STATIC_FILES + 10):
            path = self.path.with_name(f'kit-{number}.js')
            path.write_bytes(b'let n = %d;\n' % number)
            server.static_file(KIND, path, {})
        self.assertEqual(len(server._FILES), server.STATIC_FILES)
        self.assertNotIn(str(self.path.with_name('kit-0.js')), server._FILES)
        self.assertIn(str(self.path.with_name(f'kit-{server.STATIC_FILES + 9}.js')), server._FILES)

    def test_a_missing_file_is_refused_as_before(self):
        self.path.unlink()
        with self.assertRaises(OSError):
            server.static_file(KIND, self.path, {})


class ServerBoundTests(unittest.TestCase):
    """The page's server answers at most SLOTS requests at once and closes one past that."""

    def test_a_request_past_the_bound_is_closed_and_the_next_is_answered(self):
        release = threading.Event()
        entered = threading.Semaphore(0)

        class Held(BaseHTTPRequestHandler):
            def do_GET(self):
                entered.release()
                release.wait(20)
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *args):
                pass

        with mock.patch.object(server, 'SLOTS', 2):
            made = server.Server(('127.0.0.1', 0), Held)
        self.addCleanup(made.server_close)
        serving = threading.Thread(target=made.serve_forever, args=(0.05,), daemon=True)
        serving.start()
        self.addCleanup(serving.join, 10)
        self.addCleanup(made.shutdown)
        self.addCleanup(release.set)
        port = made.server_address[1]

        def ask():
            line = socket.create_connection(('127.0.0.1', port), timeout=20)
            line.sendall(b'GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n')
            return line

        held = [ask(), ask()]
        for _ in held:
            self.assertTrue(entered.acquire(timeout=20))
        refused = ask()
        try:
            said = refused.recv(64)
        except ConnectionResetError:
            said = b''          # closed with the request unread: the same refusal
        finally:
            refused.close()
        self.assertEqual(said, b'', 'a request past the bound was answered')
        release.set()
        for line in held:
            with line:
                self.assertIn(b'ok', line.makefile('rb').read())
        for _ in range(2):      # both slots are let go once their threads end
            self.assertTrue(made.slots.acquire(timeout=20))
        for _ in range(2):
            made.slots.release()
        later = ask()
        with later:
            self.assertTrue(entered.acquire(timeout=20))
            self.assertIn(b'200', later.makefile('rb').read())


if __name__ == '__main__':
    unittest.main()
