"""Infographic Studio's authenticated native foundation APIs."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from studio_core import server as core

from .contracts import PRODUCT, Invalid

WEB = Path(__file__).parent / 'web'
shared = core.for_product(
    '_infographic_studio_server', PRODUCT, 'X-Infographic-Studio-Token', WEB,
    {'/': ('index.html', 'text/html; charset=utf-8'),
     '/style.css': ('style.css', 'text/css; charset=utf-8')},
    None, Invalid, reads=('/api/status', '/api/projects', '/api/project', '/api/asset'),
    writes=('/api/projects', '/api/project'))


class Page(shared.Page):
    def __init__(self, port, store):
        super().__init__(port)
        self.store = store

    def check_token(self, headers):
        if len(headers.get_all('X-Infographic-Studio-Token') or []) != 1:
            raise shared.Refusal(HTTPStatus.FORBIDDEN, 'Send exactly one page key.')
        super().check_token(headers)

    def read(self, path, one):
        if path == '/api/status':
            return shared.as_json(HTTPStatus.OK, {'product': PRODUCT, 'foundation': True,
                                  'configured': True, 'providers': 'not-checked',
                                  'generation_available': False})
        if path == '/api/projects':
            return shared.as_json(HTTPStatus.OK, {'projects': self.store.listing()})
        if path == '/api/project':
            return shared.as_json(HTTPStatus.OK, {'project': self.store.read(one('id'))})
        if path == '/api/asset':
            mime, raw = self.store.read_asset(one('id'), one('asset'))
            return HTTPStatus.OK, mime, raw
        raise shared.Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')

    def write(self, path, sent):
        if path == '/api/projects':
            if set(sent) - {'title', 'preset', 'direction'}:
                raise Invalid('Supply only a title, page preset, and direction.')
            project = self.store.create(sent.get('title'), preset=sent.get('preset', 'a4'),
                                        direction=sent.get('direction', 'suggest'))
            return shared.as_json(HTTPStatus.CREATED, {'project': project})
        if path == '/api/project':
            if set(sent) != {'id', 'expected_revision', 'brief'}:
                raise Invalid('Save the brief with its infographic ID and expected revision.')
            project = self.store.edit_brief(sent['id'], sent['brief'],
                                            expected_revision=sent['expected_revision'])
            return shared.as_json(HTTPStatus.OK, {'project': project})
        raise shared.Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')


def desk(store, port=0):
    return shared.Desk(port=port, page=lambda actual_port: Page(actual_port, store))
