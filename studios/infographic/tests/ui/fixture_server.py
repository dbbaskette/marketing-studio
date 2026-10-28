"""Disposable browser fixture. Never starts an assistant or contacts an image provider."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
from runner import brand, server, settings, sources
from runner.engine import Engine
from runner.workspace import Store
from test_composition import contract
from helpers import visual_answer


class Assistant:
    def __init__(self): self.calls = []
    def propose(self, brief, captured):
        self.calls.append('story')
        source = captured[0]
        fact = {'id': 'f1', 'statement': source['text'], 'value': source['text'], 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': source['id'], 'start': 0, 'end': len(source['text']), 'quote': source['text']}]}
        story = {'id': 's1', 'headline': 'Keep serving', 'takeaway': 'Restart one instance at a time.',
                 'rationale': 'Explain the supplied relationship without inventing a metric.', 'qualifications': [], 'omissions': [],
                 'blocks': [{'id': 'b1', 'kind': 'concept', 'title': 'Rolling restart',
                             'text': 'Other instances continue serving requests.', 'fact_ids': ['f1'], 'required_ids': [],
                             'illustration': False, 'illustration_role': ''}]}
        return {'facts': [fact], 'stories': [story]}
    def inspect_images(self, context, images):
        self.calls.append('inspection')
        assert images[0].startswith(b'\x89PNG')
        return visual_answer()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', required=True, type=Path)
    parser.add_argument('--suite', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='infographic-browser-') as folder:
        root = Path(folder).resolve(); home = root / 'home'; home.mkdir()
        path = os.environ.get('PATH', '')
        os.environ.clear()
        os.environ.update(PATH=path, HOME=str(home), INFOGRAPHIC_STUDIO_DATA=str(root / 'data'),
                          MARKETING_STUDIO_DATA=str(root / 'marketing-data'),
                          STUDIOS_CONFIG=str(root / 'settings.json'), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        (root / 'settings.json').write_text(json.dumps({'schema': 1, 'assistant': {'agent': 'codex', 'model': None},
            'person': {'name': 'Synthetic Author'}, 'local': {'root': str(root / 'work')}}))
        store = Store.setup()
        settings.save({'renderer': str(args.renderer)}, expected=settings.snapshot()['native_revision'])
        engine = Engine(store, executable=args.renderer, assistant=Assistant())
        engine.configuration = {'image_provider': 'codex'}
        class Page(server.Page):
            def read(self, route, one):
                if route == '/api/fixture-calls': return server.shared.as_json(200, {'calls': engine.assistant.calls})
                return super().read(route, one)
            def write(self, route, sent):
                if route == '/api/brand-current':
                    project = brand.adopt(store, sent['id'], contract(), expected_revision=sent['expected_revision'])
                    return server.shared.as_json(200, {'project': project})
                return super().write(route, sent)
        page = server.shared.Desk(page=lambda port: Page(port, store, engine))
        suite = None
        launcher = None
        try:
            page.start()
            if args.suite:
                sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
                from marketing_studio import server as home_server
                from marketing_studio.launcher import Launcher
                from marketing_studio.page import Home
                from studio_core import preferences, studios_config
                preferences.finish(studios_config, lambda _: None)
                launcher = Launcher()
                class Suite(Home):
                    def write(self, route, sent):
                        if route == '/api/open' and sent == {'studio': 'infographic'}:
                            return home_server.as_json(200, {'link': page.url})
                        return super().write(route, sent)
                suite = home_server.Desk(page=lambda port: Suite(port, launcher))
                suite.start()
            print(suite.url if suite else page.url, flush=True)  # Private test process only.
            signal.signal(signal.SIGTERM, server.shared.interrupt)
            signal.signal(signal.SIGINT, server.shared.interrupt)
            threading.Event().wait()
        except KeyboardInterrupt: pass
        finally:
            if suite: suite.stop()
            if launcher: launcher.close()
            page.stop()

if __name__ == '__main__': main()
