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
from workflow_cases import NAMES, case, captured_answer


class Assistant:
    def __init__(self, slow=False, visual='concept', scenario=None):
        self.calls = []
        self.slow = slow
        self.release = threading.Event()
        self.fail = False
        self.visual = visual
        self.scenario = scenario
    def propose(self, brief, captured):
        self.calls.append('story')
        if self.slow:
            self.fail = False
            self.release.clear()
            if not self.release.wait(60):
                raise RuntimeError('Synthetic assistant was not released.')
            if self.fail == 'timeout':
                from runner.assistant_failure import AssistantFailure
                raise AssistantFailure('timeout')
            if self.fail:
                from runner.contracts import Invalid
                raise Invalid('Synthetic planning failure. Your saved work is kept.')
        if self.scenario:
            from runner.author import Author
            example = case('paraphrase' if self.scenario == 'recovery' else self.scenario)
            answer = captured_answer(example, captured[0]['id'])
            if self.scenario == 'recovery':
                for fact in answer['facts']:
                    fact['evidence'][0]['quote'] = 'This quotation is deliberately absent.'
            def run(command, prompt, folder, timeout):
                assert '--output-schema' in command
                events = [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(answer)}},
                          {'type': 'turn.completed'}]
                return {'state': 'complete', 'returncode': 0, 'events': '\n'.join(map(json.dumps, events))}
            return Author({'agent': 'codex'}, run=run).propose(brief, captured)
        source = captured[0]
        fact = {'id': 'f1', 'statement': source['text'], 'value': source['text'], 'unit': '', 'status': 'supplied',
                'evidence': [{'source_id': source['id'], 'start': 0, 'end': len(source['text']), 'quote': source['text']}]}
        story = {'id': 's1', 'headline': 'Keep serving', 'takeaway': 'Restart one instance at a time.',
                 'rationale': 'Explain the supplied relationship without inventing a metric.', 'qualifications': [], 'omissions': [],
                 'blocks': [{'id': 'b1', 'kind': self.visual, 'title': 'Rolling restart',
                             'text': 'Other instances continue serving requests.', 'fact_ids': ['f1'], 'required_ids': [],
                             'illustration': False, 'illustration_role': ''}]}
        return {'facts': [fact], 'stories': [story]}
    def inspect_images(self, context, images):
        self.calls.append('inspection')
        assert images[0].startswith(b'\x89PNG')
        if self.scenario:
            from runner.author import Author
            def run(command, prompt, folder, timeout):
                assert '--output-schema' in command and '--image' in command
                event = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(visual_answer())}}
                return {'state': 'complete', 'returncode': 0, 'events': json.dumps(event)}
            return Author({'agent': 'codex'}, run=run).inspect_images(context, images)
        return visual_answer()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer', required=True, type=Path)
    parser.add_argument('--suite', action='store_true')
    parser.add_argument('--remote',action='store_true')
    parser.add_argument('--bridge',action='store_true')
    parser.add_argument('--slow', action='store_true')
    parser.add_argument('--visual', choices=('concept', 'comparison', 'parts'), default='concept')
    parser.add_argument('--scenario', choices=(*NAMES, 'recovery'))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='infographic-browser-') as folder:
        root = Path(folder).resolve(); home = root / 'home'; home.mkdir()
        path = os.environ.get('PATH', '')
        os.environ.clear()
        os.environ.update(PATH=path, HOME=str(home), INFOGRAPHIC_STUDIO_DATA=str(root / 'data'),
                          MARKETING_STUDIO_DATA=str(root / 'marketing-data'),
                          STUDIOS_CONFIG=str(root / 'settings.json'), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        (root / 'settings.json').write_text(json.dumps({'schema': 1, 'assistant': {'agent': 'codex', 'model': None},
            'output':'google' if args.remote else 'pptx', 'person': {'name': 'Synthetic Author'}, 'local': {'root': str(root / 'work')}}))
        store = Store.setup()
        source_text = case('paraphrase' if args.scenario == 'recovery' else args.scenario)['source'] if args.scenario else 'One instance restarts while the others serve.'
        settings.save({'renderer': str(args.renderer)}, expected=settings.snapshot()['native_revision'])
        if args.remote:
            from runner import remote_sources,google_delivery
            from studio_core.google_api import DOC_MIME,SLIDES_MIME
            class Google:
                def __init__(self,account):
                    assert account in (None,'editor@example.invalid')
                    self.account='editor@example.invalid'
                def selected_account(self):return self.account
                def file(self,ident):
                    return {'id':ident,'mimeType':SLIDES_MIME if ident=='synthetic_slides' else DOC_MIME,'name':'Synthetic Google slides' if ident=='synthetic_slides' else 'Synthetic Google source','version':'7','modifiedTime':'2026-10-28T00:00:00Z','capabilities':{'canDownload':True}}
                def document(self,ident):
                    return {'documentId':ident,'tabs':[{'tabProperties':{'tabId':'main','title':'Main'},'documentTab':{'body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':source_text}}]}}]}}}]}
                def presentation(self,ident):
                    return {'presentationId':ident,'slides':[{'objectId':'slide_a','pageElements':[{'objectId':'body','shape':{'text':{'textElements':[{'textRun':{'content':source_text}}]}}}]}]}
                def create_document(self,payload,**values):
                    assert payload.startswith(b'PK')
                    return {'id':'synthetic_delivered','mimeType':DOC_MIME,'appProperties':{'infographic_request':values['request_key'],'infographic_payload':values['payload_hash']}}
            remote_sources.Client=google_delivery.Client=Google
        engine = Engine(store, executable=args.renderer, assistant=Assistant(slow=args.slow, visual=args.visual, scenario=args.scenario))
        engine.configuration = {'image_provider': 'codex'}
        class Page(server.Page):
            reads = (*server.Page.reads, '/api/fixture-calls', '/api/fixture-source')
            writes = (*server.Page.writes, '/api/fixture-release')
            def read(self, route, one):
                if route == '/api/fixture-calls': return server.shared.as_json(200, {'calls': engine.assistant.calls})
                if route == '/api/fixture-source': return server.shared.as_json(200, {'text': source_text})
                return super().read(route, one)
            def write(self, route, sent):
                if route == '/api/fixture-release':
                    engine.assistant.fail = sent.get('fail', False)
                    engine.assistant.release.set()
                    return server.shared.as_json(200, {'released': True})
                if route == '/api/brand-current':
                    project = brand.adopt(store, sent['id'], contract(), expected_revision=sent['expected_revision'])
                    return server.shared.as_json(200, {'project': project})
                return super().write(route, sent)
        page = server.shared.Desk(page=lambda port: Page(port, store, engine))
        suite = None
        launcher = None
        bridge = None
        try:
            page.start()
            if args.bridge:
                sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
                from marketing_studio.network import BridgeServer
                bridge=BridgeServer(('127.0.0.1',0),f'127.0.0.1:{page.port}',page.token,server.shared.TOKEN_HEADER,'infographic')
                threading.Thread(target=bridge.serve_forever,daemon=True).start()
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
                # Simulate a native loopback home port differing from the phone/network origin.
                os.environ['MARKETING_STUDIO_HOME_PORT'] = '1'
            offered=suite.url if suite else page.url
            if bridge:
                from urllib.parse import urlsplit,urlunsplit
                parts=urlsplit(offered);offered=urlunsplit(parts._replace(netloc=bridge.authority))
            print(offered, flush=True)  # Private test process only.
            signal.signal(signal.SIGTERM, server.shared.interrupt)
            signal.signal(signal.SIGINT, server.shared.interrupt)
            threading.Event().wait()
        except KeyboardInterrupt: pass
        finally:
            if bridge:bridge.shutdown();bridge.server_close()
            if suite: suite.stop()
            if launcher: launcher.close()
            page.stop()

if __name__ == '__main__': main()
