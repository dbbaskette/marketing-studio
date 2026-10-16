"""Disposable acceptance against sibling checkouts or installed studio runtimes."""
import argparse
import json, os, subprocess, sys, tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--installed', action='store_true')
args=parser.parse_args()
original_home=Path.home()
def studio_root(identifier):
    return (original_home/'.local/share'/(identifier+'-studio')/'current').resolve() if args.installed else repo.parent/(identifier+'-studio')
for identifier in ('blog','presentation','training'):
    if not studio_root(identifier).is_dir():
        parser.error('Install or check out all three studios before running native acceptance.')
with tempfile.TemporaryDirectory(prefix='marketing-native-') as tmp:
    root=Path(tmp)
    home=root/'home';home.mkdir()
    env={**os.environ, 'HOME':str(home), 'STUDIOS_CONFIG':str(root/'shared.json'),
         'GIT_CONFIG_GLOBAL':str(root/'gitconfig'), 'GIT_CONFIG_NOSYSTEM':'1',
         'GIT_AUTHOR_NAME':'Synthetic Author', 'GIT_AUTHOR_EMAIL':'synthetic@example.invalid',
         'GIT_COMMITTER_NAME':'Synthetic Author','GIT_COMMITTER_EMAIL':'synthetic@example.invalid'}
    (root/'gitconfig').write_text('[user]\n name = Synthetic Author\n email = synthetic@example.invalid\n')
    shared={'schema':1,'person':{'name':'Synthetic Author'},'assistant':{'agent':'codex','model':None},
            'local':{'root':str(root/'work')},'output':'pptx'}
    (root/'shared.json').write_text(json.dumps(shared))
    for identifier in ('blog','presentation','training'):
        env[identifier.upper()+'_STUDIO_DATA']=str(root/(identifier+'-data'))
        env['MARKETING_STUDIO_HANDOFF']=json.dumps({'token':'a'*40,'shared':shared})
        studio=studio_root(identifier)
        result=subprocess.run([sys.executable,str(repo/'marketing_studio/bridge.py'),identifier,str(studio),'--prepare'],env=env,capture_output=True,text=True,timeout=30)
        print(identifier, result.returncode, result.stdout.strip())
        if result.returncode:
            print(result.stderr[-3000:]);sys.exit(1)
        if identifier=='blog':
            code="import sys;sys.path.insert(0,sys.argv[1]);from studio_sync import gitstate;import blog_runner;print(gitstate.current().root);assert blog_runner.settings(gitstate.current().root)['configured'];print(blog_runner.settings(gitstate.current().root)['defaults']['engine'])"
            module=studio/'skills/blog-studio/scripts'
            if not module.is_dir(): module=studio/'scripts'
        else:
            code="import sys;sys.path.insert(0,sys.argv[1]);from runner import gitstate,settings;print(gitstate.current().root);print(settings.load().agent)"
            module=studio
        check=subprocess.run([sys.executable,'-c',code,str(module)],env=env,capture_output=True,text=True,timeout=15)
        print('independent settings:',check.returncode, check.stdout.strip())
        if check.returncode:
            print(check.stderr[-3000:]);sys.exit(1)
    # Idempotence: a second prepare retains existing repositories, even with a new default.
    shared['local']['root']=str(root/'different')
    for identifier in ('blog','presentation','training'):
        env['MARKETING_STUDIO_HANDOFF']=json.dumps({'token':'b'*40,'shared':shared})
        result=subprocess.run([sys.executable,str(repo/'marketing_studio/bridge.py'),identifier,str(studio_root(identifier)),'--prepare'],env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(identifier,result.stdout,result.stderr)
    assert not (root/'different').exists()
    print('PASS: all three native setups, independent settings, and existing-workspace preservation')
