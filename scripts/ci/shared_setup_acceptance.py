"""Real independent launchers and HTTP setup, with no providers or account state."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = ('blog', 'presentation', 'training', 'infographic')


@contextlib.contextmanager
def opened(identifier, env):
    native = ROOT / 'studios' / identifier
    # Only background jobs and update checks are replaced. Real launch, workspace,
    # setup page, native home page, HTTP auth, settings and teardown are exercised.
    script = '''import runpy, sys
from pathlib import Path
identifier, native = sys.argv[1], Path(sys.argv[2])
sys.stdout.isatty = lambda: True
if identifier == 'blog':
    scripts = native / 'skills/blog-studio/scripts'
    sys.path.insert(0, str(scripts))
    sys.argv = [str(scripts / 'start_studio.py'), '--no-open', '--json']
    runpy.run_path(sys.argv[0], run_name='__main__')
elif identifier == 'infographic':
    sys.path.insert(0, str(native))
    from runner import studio
    raise SystemExit(studio.main(['serve']))
else:
    sys.path.insert(0, str(native))
    from runner import engine, studio, upkeep
    engine.Engine.resume = lambda *a, **kw: None
    upkeep.Upkeep.start = lambda *a, **kw: None
    raise SystemExit(studio.main(['serve']))
'''
    process = subprocess.Popen([sys.executable, '-u', '-c', script, identifier, str(native)],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # This fixture has no session from a real account. Keep its token in memory.
        for _ in range(5):
            line = process.stdout.readline()
            if line.startswith('{'):
                found = json.loads(line)
                if 'url' in found:
                    link = found['url']
                    break
                raise AssertionError(found)
            if not line:
                raise AssertionError(identifier + ': launch failed: ' + process.stderr.read()[-2000:])
        else:
            raise AssertionError(identifier + ': no native launch announcement')
        yield link
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()


def request(link, identifier, path='/', body=None, authenticated=True):
    base, fragment = link.split('#', 1)
    token = fragment.removeprefix('token=')
    headers = {'Origin': base.rstrip('/')}
    if authenticated:
        headers['X-' + identifier.title() + '-Studio-Token'] = token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    sent = urllib.request.Request(base.rstrip('/') + path, headers=headers,
                                  data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(sent, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as failure:
        return failure.code, failure.read()


def assert_native(link, identifier):
    status, html = request(link, identifier)
    assert status == 200 and b'data-standalone="true"' not in html
    if identifier == 'blog':
        status, body = request(link, identifier, '/api/run-settings')
    elif identifier == 'infographic':
        status, body = request(link, identifier, '/api/status')
    else:
        status, body = request(link, identifier, '/api/setup')
    assert status == 200 and json.loads(body)['configured'], (identifier, status, body[:1000])


def journey(starter):
    with tempfile.TemporaryDirectory(prefix='studio-shared-setup-') as temp:
        case = Path(temp)
        home = case / 'home'
        home.mkdir()
        env = {**os.environ, 'HOME': str(home), 'STUDIOS_CONFIG': str(case / 'shared.json'),
               'GIT_CONFIG_GLOBAL': str(case / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1',
               'GIT_AUTHOR_NAME': 'Synthetic Author', 'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
               'GIT_COMMITTER_NAME': 'Synthetic Author', 'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid',
               'CODEX_HOME': str(home / '.codex'), 'CLAUDE_CONFIG_DIR': str(home / '.claude')}
        for identifier in PRODUCTS:
            env[identifier.upper() + '_STUDIO_DATA'] = str(home / '.local/share' / (identifier + '-studio'))
        (case / 'gitconfig').write_text('[user]\n name = Synthetic Author\n email = synthetic@example.invalid\n')
        for name in list(env):
            if name.startswith(('OPENAI_', 'ANTHROPIC_', 'CLAUDECODE')):
                env.pop(name)
        with opened(starter, env) as link:
            status, html = request(link, starter)
            assert status == 200 and b'data-standalone="true"' in html
            assert b'name="local.root"' in html and b'name="assistant.model"' in html
            status, _ = request(link, starter, '/onboarding/api/home', authenticated=False)
            assert status == 403
            wanted = {'local': {'root': str(case / 'work')}, 'person': {'name': 'Synthetic Author'},
                      'assistant': {'agent': 'codex', 'model': 'gpt-6-luna', 'effort': 'high'},
                      'review': {'level': 'step_by_step'},
                      'output': 'pptx', 'render': {'previews': 'local'}, 'share': 'asked',
                      'models': {'schema': 1, 'agent': 'codex', 'mode': 'by_task', 'profiles': {
                          'quick': {'selection': 'explicit', 'model': 'fixture-quick', 'effort': 'low'},
                          'main': {'selection': 'inherit'},
                          'complex': {'selection': 'provider_default'}}}}
            status, body = request(link, starter, '/onboarding/api/shared', {'changes': wanted, 'seen': {}})
            assert status == 200, body[:1000]
            assert not json.loads(body)['setup']['done']
            status, body = request(link, starter, '/onboarding/api/setup', {'done': True})
            assert status == 200 and json.loads(body)['setup']['done'], body[:1000]
            assert_native(link, starter)
        # Open each studio independently after setup, including the original studio again.
        for identifier in PRODUCTS:
            with opened(identifier, env) as link:
                assert_native(link, identifier)
                status, body = request(link, identifier, '/onboarding/api/home')
                values = json.loads(body)['shared']
                assert status == 200 and values['assistant'] == wanted['assistant']
                assert values['render'] == wanted['render']
                assert values['models'] == wanted['models']
        assert all((case / 'work' / (identifier + '-workspace')).is_dir() for identifier in PRODUCTS)
        assert not (home / '.local/share/marketing-studio/home.json').exists()
        print(starter.title() + ' Studio: standalone setup, immediate home, independent reopen, and later studios passed')


if __name__ == '__main__':
    for starter in PRODUCTS:
        journey(starter)
    print('PASS: setup from every independent studio carries through to all four')
