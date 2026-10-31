import json, os, sys, tempfile, urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from unittest import mock
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo))
from marketing_studio.launcher import Launcher
from marketing_studio.network import Network, TOKEN_HEADERS
with tempfile.TemporaryDirectory(prefix='marketing-launch-acceptance-') as tmp:
    root=Path(tmp);(root/'home').mkdir()
    config=root/'shared.json'
    shared={'schema':1,'setup':{'version':1},'person':{'name':'Synthetic Author'},'assistant':{'agent':'codex'},'local':{'root':str(root/'work')},'output':'pptx'}
    config.write_text(json.dumps(shared))
    (root/'gitconfig').write_text('[user]\n name = Synthetic Author\n email = synthetic@example.invalid\n')
    env={'HOME':str(root/'home'),'STUDIOS_CONFIG':str(config),'MARKETING_STUDIO_DATA':str(root/'data'),
         'GIT_CONFIG_GLOBAL':str(root/'gitconfig'),'GIT_CONFIG_NOSYSTEM':'1',
         'GIT_AUTHOR_NAME':'Synthetic Author','GIT_AUTHOR_EMAIL':'synthetic@example.invalid',
         'GIT_COMMITTER_NAME':'Synthetic Author','GIT_COMMITTER_EMAIL':'synthetic@example.invalid'}
    for identifier in ('blog','presentation','training','infographic'):
        env[identifier.upper()+'_STUDIO_DATA']=str(root/(identifier+'-data'))
    wrapper=root/'shim';(wrapper/'marketing_studio').mkdir(parents=True)
    # Test-only replacements disable background update/research actions. Native page,
    # workspace, process startup, announcements, token auth, and teardown remain real.
    code=f'''import sys,runpy
from pathlib import Path
root=Path(sys.argv[2]); identifier=sys.argv[1]
if identifier not in ('blog','infographic'):
    sys.path.insert(0,str(root))
    from runner import engine,upkeep
    engine.Engine.resume=lambda *a,**kw: None
    upkeep.Upkeep.start=lambda *a,**kw: None
runpy.run_path({str(repo/'marketing_studio/bridge.py')!r},run_name='__main__')
'''
    (wrapper/'marketing_studio/bridge.py').write_text(code)
    paths={identifier:str(repo/'studios'/identifier) for identifier in ('blog','presentation','training','infographic')}
    with mock.patch.dict(os.environ,env),mock.patch('marketing_studio.launcher.ROOT',wrapper):
        # Exercise the LAN bridge protocol on loopback with synthetic work only.
        with mock.patch('marketing_studio.network.private_address', return_value='127.0.0.1'):
            network=Network('synthetic-interface')
        launcher=Launcher(network)
        try:
            for identifier in paths:
                # A phone's Open is given the studio's bridge; the computer's keeps loopback.
                link=launcher.open(identifier,{'paths':paths},shared,remote=True)
                assert link==network.bridges[identifier][3]!=launcher.children[identifier][1]
                with urllib.request.urlopen(link.split('#')[0],timeout=5) as response:
                    body=response.read()
                    assert response.status==200 and b'<html' in body.lower()
                    assert b'data-standalone="true"' not in body
                address=urlsplit(link)
                token=address.fragment.removeprefix('token=')
                endpoint={'blog':'runs','presentation':'decks','training':'trainings','infographic':'projects'}[identifier]
                request=urllib.request.Request(link.split('#')[0]+'api/'+endpoint,
                    headers={TOKEN_HEADERS[identifier]:token,'Origin':'http://'+address.netloc})
                with urllib.request.urlopen(request,timeout=5) as response:
                    assert response.status==200 and isinstance(json.load(response),dict)
                try:
                    urllib.request.urlopen(link.split('#')[0]+'api/'+endpoint,timeout=5)
                    raise AssertionError('An unauthenticated studio read was accepted')
                except urllib.error.HTTPError as error:
                    assert error.code==403
                assert launcher.open(identifier,{'paths':paths},shared,remote=True)==link
                assert launcher.open(identifier,{'paths':paths},shared)==launcher.children[identifier][1]
                print(identifier+': native page and authenticated API serve through network bridge; unauthenticated reads fail; repeated Open reuses process')
            processes=[p for p,_ in launcher.children.values()]
        finally:
            network.close()
            launcher.close()
        assert all(p.poll() is not None for p in processes)
        print('PASS: all native studio pages launched and all owned processes stopped')
