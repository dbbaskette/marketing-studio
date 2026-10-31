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
    def __init__(self, slow=False, visual='concept', scenario=None, art=False):
        self.calls = []
        self.slow = slow
        self.release = threading.Event()
        self.fail = False
        self.visual = visual
        self.scenario = scenario
        self.art = art
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
                             'illustration': self.art, 'illustration_role': 'Show the service instances.' if self.art else ''}]}
        return {'facts': [fact], 'stories': [story]}
    def art_direction(self, project):
        self.calls.append('art')
        return {'style':'Flat explanatory schematic.','reading_order':'Follow the supplied service relationship.',
                'acceptance':'Service subjects are visible and exact label regions are clear.','reference_assets':[],
                'objects':[{'id':'obj'+str(i),'region_id':r['id'],'count':1,'description':'Illustrative service instance.',
                            'relationships':'The service continues serving.','preserve':'Keep native labels and diagrams clear.'}
                           for i,r in enumerate(project['scene']['art_regions'])]}
    def revise_story(self, project, story, block_id, instruction):
        from copy import deepcopy
        self.calls.append('revision')
        revised=deepcopy(story)
        for block in revised['blocks']:
            if block_id is not None and block['id'] != block_id:continue
            block.update(illustration=False,illustration_role='',visual={'nodes':[
                {'id':'service','label':'Service instances','caption':'','icon':'server','fact_ids':block['fact_ids']}],
                'links':[]})
        return revised
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
    parser.add_argument('--research-runtime', type=Path)
    parser.add_argument('--suite', action='store_true')
    parser.add_argument('--recover-image', action='store_true')
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
                          CODEX_HOME=str(root / 'codex'),
                          MARKETING_STUDIO_DATA=str(root / 'marketing-data'),
                          STUDIOS_CONFIG=str(root / 'settings.json'), STUDIOS_LIBRARY=str(root / 'library'),
                          GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        (root / 'settings.json').write_text(json.dumps({'schema': 1, 'assistant': {'agent': 'codex', 'model': None},
            'output':'google' if args.remote else 'pptx', 'person': {'name': 'Synthetic Author'}, 'local': {'root': str(root / 'work')}}))
        store = Store.setup()
        # One synthetic document in the disposable Document Library, for Add from library.
        from studio_core import document_library
        document_library.opened(create=True).add_upload(
            'synthetic-capacity.txt', b'Synthetic capacity notes: four instances; one restarts at a time.',
            title='Synthetic capacity notes')
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
        engine = Engine(store, executable=args.renderer, assistant=Assistant(slow=args.slow, visual=args.visual, scenario=args.scenario, art=args.recover_image))
        engine.configuration = {'image_provider': 'codex'}
        if args.recover_image:
            from runner.images.base import result
            from graphics_fixtures import png
            class EarlierAdapter:
                configuration = {}
                def __init__(self, folder): self.folder = folder
                def generate(self, *, attempt_id, brief):
                    engine.assistant.calls.append('image')
                    thread = '01234567-1234-7123-8123-0123456789ab'
                    output = root / 'codex/generated_images' / thread
                    output.mkdir(parents=True)
                    (output / 'image.png').write_bytes(png())
                    (self.folder / 'events.jsonl').write_text('\n'.join(map(json.dumps,[
                        {'type':'thread.started','thread_id':thread},{'type':'turn.completed'}])))
                    return result('codex','generate',attempt_id,state='failed',reason='image-tool-unavailable')
            engine.adapters = {'codex': EarlierAdapter}
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
        if args.research_runtime:
            def synthetic_research(phase, payload, guidance, **options):
                engine.assistant.calls.append(phase)
                if phase == 'investigate':
                    source=payload['sources'][0]
                    return {'schema':2, 'sources':[{'id':'source-a','title':source['title'],'publisher':'Synthetic fixture',
                        'file':source['file'],'origin':source['origin'],'permission':source['permission'],'context':'full',
                        'original_file':source['original_file']}],
                        'facts':[{'id':'fact-a','statement':source['text'].strip(),'author':payload['worker'],
                            'citations':[{'source':'source-a','quote':source['text'].strip()}]}], 'gaps':[]}
                if phase == 'synthesize':
                    fact=payload['evidence']['facts'][0]['id']
                    block={'text':'Use the supplied synthetic explanation within its scope.','kind':'recommendation','refs':[fact]}
                    return {'schema':2,'findings':[{'id':'scope','title':'Synthetic source scope',
                        'summary':{'text':'The source explains a synthetic relationship.','kind':'summary','refs':[fact]},
                        'support':[fact],'counter':[],'conditions':[],'implications':[],'gaps':[]}],
                        'sections':[{'id':'report','title':'Synthetic explanation','blocks':[block]}],
                        'brief':[{'id':'brief','title':'What to show','blocks':[block]}]}
                import copy
                review=copy.deepcopy(payload['review_template'])
                for original in review['originals']: original['read_original']=True
                for kind in ('facts','findings','prose'):
                    for item in review[kind]: item.update(verdict='supported',note='Synthetic independent fixture check.')
                review['assessment']={'coverage':'accurate','usefulness':'adequate','note':'Synthetic scope.'}
                return review
            engine.assistant.research=synthetic_research
        def native_page(port):
            found=Page(port,store,engine)
            if args.research_runtime:
                from runner.research_jobs import Jobs
                found.research=Jobs(store,author=engine.assistant,runtime=args.research_runtime)
            return found
        page = server.shared.Desk(page=native_page)
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
