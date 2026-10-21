"""A page the studio's own page frames, such as a deck's draft: opened with a ticket, sandboxed."""
import time
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

from test_home import IsolatedHome  # noqa: F401  puts the core on the import path
from studio_core import server as core


def made():
    module = core.for_product('_framed_probe', 'Probe', 'X-Probe-Token', Path('/nowhere'),
                              {}, None, ValueError, reads=('/api/read',), writes=())

    class Probe(module.Page):
        framed = ('/api/frame',)

        def read_framed(self, path, scope):
            return module.framed_html(f'<p>{scope}</p>'.encode())

    return module, Probe(8765)


def asked(target, token=None):
    headers = Message()
    headers['Host'] = '127.0.0.1:8765'
    if token:
        headers['X-Probe-Token'] = token
    return target, headers


class FramedPageTests(unittest.TestCase):
    def test_a_frame_opens_only_with_a_ticket_for_its_own_address(self):
        module, page = made()
        ticket = page.ticket('/api/frame', 'deck draft')
        status, kind, body, extra = page.answer(*asked(f'/api/frame?ticket={ticket}'))
        self.assertEqual((status, kind, body), (200, 'text/html; charset=utf-8',
                                                b'<p>deck draft</p>'))
        self.assertTrue(extra['Content-Security-Policy'].startswith('sandbox; '))
        self.assertIn("default-src 'none'", extra['Content-Security-Policy'])
        self.assertNotIn('script', extra['Content-Security-Policy'])
        self.assertEqual((extra['X-Content-Type-Options'], extra['Cache-Control'],
                          extra['X-Frame-Options']), ('nosniff', 'no-store', 'SAMEORIGIN'))
        self.assertIn("frame-ancestors 'self'", extra['Content-Security-Policy'])
        self.assertEqual(extra['Referrer-Policy'], 'no-referrer')
        for wrong in ('/api/frame?ticket=made-up', '/api/frame'):
            with self.subTest(wrong=wrong), self.assertRaises(module.Refusal):
                page.answer(*asked(wrong))
        with self.assertRaises(ValueError):
            page.ticket('/api/read', 'x')
        # The key alone does not open a frame, and a ticket does not outlive its time.
        with self.assertRaises(module.Refusal):
            page.answer(*asked('/api/frame', page.token))
        later = time.monotonic() + core.TICKET_SECONDS + 1
        with mock.patch.object(module.time, 'monotonic', return_value=later), \
                self.assertRaises(module.Refusal):
            page.answer(*asked(f'/api/frame?ticket={ticket}'))

    def test_a_framed_page_carries_its_own_policy_and_no_other(self):
        module, _ = made()
        handler = object.__new__(module.Handler)
        sent = []
        handler.send_header = lambda name, value: sent.append((name, value))
        handler._own = {'content-security-policy', 'x-frame-options'}
        with mock.patch.object(module.BaseHTTPRequestHandler, 'end_headers'):
            handler.end_headers()
        names = [name for name, _ in sent]
        self.assertNotIn('Content-Security-Policy', names)
        self.assertNotIn('X-Frame-Options', names)
        self.assertIn('X-Content-Type-Options', names)
        sent.clear()
        with mock.patch.object(module.BaseHTTPRequestHandler, 'end_headers'):
            handler.end_headers()   # the next response has every one of the page's own
        self.assertIn(('X-Frame-Options', 'DENY'), sent)


class NeutralisedTests(unittest.TestCase):
    def test_nothing_in_a_framed_page_can_take_the_frame_elsewhere(self):
        page = (b'<base href="https://evil.example/"><meta http-equiv="refresh" '
                b'content="0;url=https://evil.example"><a href="https://evil.example" '
                b'target=_top>Out</a><a HREF=\'javascript:x\'>J</a><form action=/x>'
                b'<button formaction="https://e.example">B</button></form>'
                b'<svg><a xlink:href="https://e.example"><text>S</text></a></svg><p class="k">ok</p>')
        made = core.neutralised(page)
        for gone in (b'href', b'HREF', b'target', b'action', b'<base', b'refresh'):
            self.assertNotIn(gone, made)
        self.assertIn(b'<p class="k">ok</p>', made)
        self.assertIn(b'>Out</a>', made)
        _, _, body, _ = core.framed_html(page)
        self.assertEqual(body, made)
