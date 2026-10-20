#!/bin/bash
# Offline checks in a disposable repository; existing workspaces/settings stay untouched.
set -eu
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
diagnostic_home="$HOME"
product=presentation
while [ "$#" -gt 0 ]; do
  case "$1" in
    --home) diagnostic_home="$2"; shift 2;;
    --studio) product="$2"; shift 2;;
    *) echo 'Usage: bash diagnose-git.sh [--home PATH] [--studio presentation|blog|training|marketing]' >&2; exit 2;;
  esac
done
python="$diagnostic_home/.local/share/marketing-studio/current/runtime/python/bin/python3"
if [ ! -x "$python" ]; then python="$script_dir/studio/runtime/python/bin/python3"; fi
if [ ! -x "$python" ]; then echo 'The installed or extracted private Python runtime was not found.' >&2; exit 1; fi
exec "$python" - "$diagnostic_home" "$product" <<'PY'
import datetime, json, os, pathlib, platform, subprocess, sys, tempfile
home = pathlib.Path(sys.argv[1]).expanduser().resolve()
product = sys.argv[2]
if product not in ('presentation', 'blog', 'training', 'marketing'):
    raise SystemExit('Choose presentation, blog, training, or marketing.')
records = [home / '.local/share' / (name + '-studio-local-bundle/installation.json')
           for name in dict.fromkeys((product, 'marketing'))]
record = next((json.loads(path.read_text()) for path in records if path.is_file()), None)
if record is None:
    raise SystemExit('No local bundle installation record was found.')
git = pathlib.Path(record['tools']) / 'tools/bin/git'
directory = home / '.local/state/marketing-studio/logs'
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
fd, filename = tempfile.mkstemp(prefix='git-check-', suffix='.json', dir=directory)
report = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'platform': platform.platform(), 'git': str(git), 'checks': []}
print('Git diagnostic: ' + filename, flush=True)
try:
    with tempfile.TemporaryDirectory(prefix='studio-git-check-') as scratch:
        root = pathlib.Path(scratch)
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env.update(HOME=scratch, XDG_CONFIG_HOME=str(root / 'config'),
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   GIT_TERMINAL_PROMPT='0', GIT_EDITOR='true',
                   GIT_CEILING_DIRECTORIES=str(root.parent),
                   GIT_AUTHOR_NAME='Studio Diagnostic', GIT_COMMITTER_NAME='Studio Diagnostic',
                   GIT_AUTHOR_EMAIL='diagnostic@example.invalid',
                   GIT_COMMITTER_EMAIL='diagnostic@example.invalid',
                   PATH=str(git.parent) + ':/usr/bin:/bin')
        for args in (['--version'], ['init', '--quiet'],
                     ['symbolic-ref', 'HEAD', 'refs/heads/main'], ['var', 'GIT_AUTHOR_IDENT'],
                     ['-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false',
                      'commit', '--quiet', '--allow-empty', '-m', 'Studio diagnostic']):
            try:
                done = subprocess.run([str(git), *args], cwd=root, env=env, capture_output=True,
                                      text=True, errors='replace', timeout=30, stdin=subprocess.DEVNULL)
                check = {'arguments': args, 'exit': done.returncode,
                         'stdout': done.stdout, 'stderr': done.stderr}
            except (OSError, subprocess.TimeoutExpired) as error:
                check = {'arguments': args, 'error': str(error)}
            report['checks'].append(check)
            print(json.dumps(check), flush=True)
            if check.get('exit') != 0:
                break
finally:
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
if any(check.get('exit') != 0 for check in report['checks']):
    raise SystemExit(1)
print('PASS: private Git can initialize and commit in a disposable repository.')
PY
