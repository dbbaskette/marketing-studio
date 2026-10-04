#!/usr/bin/env python3
"""Fixed Blog Studio native Actions VM lifecycle; never execute PR code on host.

Default invocation is a plan. --once/--serve create registration credentials and
must only be invoked after explicit installation/registration approval.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid

REPO = 'dbbaskette/blog-studio'
OWNER = 'dbbaskette'
VERSION = '2.337.0'
ASSETS = {
    'macos': ('osx', '5a2cd92908a93d7276a194e1de6008099f3e7946f3f8e14aa7a1a7b4a31fdec2'),
    'linux': ('linux', '9b1dc70626422526e3c94767cf024896beb15da5342a3f4819bf2feac13e0393'),
}
BASES = {'macos': 'tanzu-brand-golden-gate-base', 'linux': 'saypipe-ubuntu-24.04-base'}
PREFIX = 'blog-studio-native-'
VM_NAME = re.compile(r'blog-studio-native-(?:macos|linux)-[0-9a-f]{16}')
SCRIPT_DIR = Path(__file__).resolve().parent
STATE = Path.home()/'.local/share/blog-studio-ci/state'
PATH = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'

# Registration data enters only stdin, never command arguments or a shared file.
# Suppress config output; retain only temporary runner credentials inside the VM.
REGISTER = r'''
import json, os, pathlib, shutil, subprocess, sys
p=json.load(sys.stdin)
os.chdir('/tmp/blog-studio-actions-runner')
env=dict(os.environ, ACTIONS_RUNNER_INPUT_TOKEN=p.pop('token'),
         PATH='/tmp/blog-studio-runner-tools/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin')
result=subprocess.run(['./config.sh','--unattended','--ephemeral','--disableupdate',
    '--url','https://github.com/dbbaskette/blog-studio','--name',p['name'],
    '--labels',p['label'],'--work','_work'],env=env,stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
env.pop('ACTIONS_RUNNER_INPUT_TOKEN',None)
shutil.rmtree('_diag',ignore_errors=True)
sys.exit(result.returncode)
'''


class LifecycleError(RuntimeError):
    pass


def require_policy(repo, collaborators, fork_policy, workflow_policy):
    """Labels are insufficient: require the approved private/sole-owner boundary."""
    if repo.get('full_name') != REPO or not repo.get('private'):
        raise LifecycleError('Repository identity/private boundary changed')
    if {c.get('login') for c in collaborators} != {OWNER}:
        raise LifecycleError('Repository collaborators changed')
    if any(fork_policy.get(k, True) for k in (
        'run_workflows_from_fork_pull_requests', 'send_write_tokens_to_workflows',
        'send_secrets_and_variables')):
        raise LifecycleError('Fork execution/credential policy changed')
    if workflow_policy.get('default_workflow_permissions') != 'read':
        raise LifecycleError('Workflow default token permissions changed')


class Service:
    def __init__(self, state=STATE):
        self.state = Path(state)
        self.stop = threading.Event()
        self.print_lock = threading.Lock()
        self.state_lock = threading.Lock()

    def log(self, message):
        with self.print_lock:
            print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), message, flush=True)

    def call(self, arguments, *, data=None, timeout=120):
        # Captured output is never interpolated into errors (may contain a token).
        result = subprocess.run(arguments, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout,
                                env=dict(os.environ, PATH=PATH))
        if result.returncode:
            raise LifecycleError('Operation failed: '+arguments[0]+' '+arguments[1])
        return result.stdout

    def api(self, route, method='GET'):
        output = self.call(['gh', 'api', '--method', method, route])
        return json.loads(output) if output.strip() else None

    def check_policy(self):
        require_policy(self.api('repos/'+REPO),
            self.api('repos/'+REPO+'/collaborators?per_page=100'),
            self.api('repos/'+REPO+'/actions/permissions/fork-pr-workflows-private-repos'),
            self.api('repos/'+REPO+'/actions/permissions/workflow'))

    def artifact(self, platform):
        os_name, expected = ASSETS[platform]
        name = f'actions-runner-{os_name}-arm64-{VERSION}.tar.gz'
        cache = self.state/'downloads'
        cache.mkdir(mode=0o700, exist_ok=True)
        destination = cache/name
        if not destination.exists():
            temporary = cache/(name+'.partial-'+uuid.uuid4().hex)
            try:
                url = f'https://github.com/actions/runner/releases/download/v{VERSION}/{name}'
                with urllib.request.urlopen(url, timeout=60) as source, temporary.open('xb') as target:
                    shutil.copyfileobj(source, target)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                    raise LifecycleError('Official runner digest mismatch')
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
            raise LifecycleError('Cached runner digest mismatch')
        return destination

    def write_record(self, run, record):
        # Metadata only: never tokens or credential-bearing environment variables.
        temporary = run/'record.partial'
        temporary.write_text(json.dumps(record)+'\n')
        temporary.replace(run/'record.json')

    def remove_runner(self, name):
        if not VM_NAME.fullmatch(name):
            raise LifecycleError('Refusing cleanup of an unrelated runner')
        listing = self.api('repos/'+REPO+'/actions/runners?per_page=100')
        if listing.get('total_count', 0) > 100:
            raise LifecycleError('Runner listing exceeded cleanup bound')
        for runner in listing['runners']:
            if runner['name'] == name:
                self.api('repos/'+REPO+'/actions/runners/'+str(runner['id']), 'DELETE')

    def cleanup(self, record):
        vm = record['vm']
        if record.get('repository') != REPO or not VM_NAME.fullmatch(vm):
            raise LifecycleError('Invalid owned VM record')
        if record.get('clone_created'):
            # get inspects only this VM. Missing VM means prior cleanup succeeded.
            try:
                info = json.loads(self.call(['tart', 'get', vm, '--format', 'json']))
            except LifecycleError:
                # A running Mac's image-info operation can be busy. Attempt
                # cleanup directly if this recorded clone still exists locally.
                if (Path.home()/'.tart/vms'/vm).exists():
                    self.call(['tart', 'stop', vm])
                    self.call(['tart', 'delete', vm])
                info = None
            if info:
                if info['Running']:
                    self.call(['tart', 'stop', vm])
                self.call(['tart', 'delete', vm])
        if record.get('registration_started'):
            self.remove_runner(vm)

    def recover(self):
        # Only records written by this controller; never broad VM/runner pruning.
        runs = self.state/'runs'
        runs.mkdir(mode=0o700, exist_ok=True)
        for record_path in sorted(runs.glob('*/record.json')):
            record = json.loads(record_path.read_text())
            if not record.get('cleaned'):
                self.cleanup(record)
                record['cleaned'] = True
                self.write_record(record_path.parent, record)

    def prune_logs(self):
        with self.state_lock:
            self._prune_logs()

    def _prune_logs(self):
        # Downloads stay cached once; each retired clone's duplicate archive is
        # removed. Keep at most 30 cleaned run logs per lane for at most 14 days.
        for platform in BASES:
            records = []
            for path in (self.state/'runs').glob('*/record.json'):
                record = json.loads(path.read_text())
                if (record.get('repository') == REPO and record.get('platform') == platform
                        and record.get('cleaned') and VM_NAME.fullmatch(record.get('vm', ''))):
                    bootstrap = path.parent/'bootstrap'
                    if bootstrap.exists():
                        shutil.rmtree(bootstrap)
                    records.append(path)
            records.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for index, path in enumerate(records):
                if index >= 30 or time.time()-path.stat().st_mtime > 14*86400:
                    shutil.rmtree(path.parent)

    def runner_is_busy(self, name):
        if not VM_NAME.fullmatch(name):
            raise LifecycleError('Invalid owned runner name')
        listing = self.api('repos/'+REPO+'/actions/runners?per_page=100')
        if listing.get('total_count', 0) > 100:
            raise LifecycleError('Runner listing exceeded monitoring bound')
        return any(r['name'] == name and r.get('busy', False) for r in listing['runners'])

    def wait_command(self, args, logfile, *, timeout, monitor_policy=True, runner_name=None):
        with logfile.open('wb') as log:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, env=dict(os.environ, PATH=PATH))
            deadline, next_policy = time.monotonic()+timeout, time.monotonic()+60
            extended_for_job = False
            try:
                while process.poll() is None:
                    if self.stop.wait(1):
                        raise LifecycleError('Stopping')
                    if time.monotonic() > deadline:
                        # Allow an already-running 30-minute job to finish when
                        # the two-hour idle/lifecycle deadline is reached.
                        if runner_name and not extended_for_job and self.runner_is_busy(runner_name):
                            deadline = time.monotonic()+2100
                            extended_for_job = True
                        else:
                            raise LifecycleError('Operation deadline exceeded')
                    if monitor_policy and time.monotonic() >= next_policy:
                        self.check_policy()
                        next_policy = time.monotonic()+60
                if process.returncode:
                    raise LifecycleError('Guest operation failed; inspect private local log')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

    def cycle(self, platform, *, prepare_only=False):
        self.check_policy()
        base = BASES[platform]
        info = json.loads(self.call(['tart', 'get', base, '--format', 'json']))
        expected = 'darwin' if platform == 'macos' else 'linux'
        if info['Running'] or info['OS'] != expected:
            raise LifecycleError('Base must be stopped and match the selected OS')
        memory_limit = 4096 if platform == 'macos' else 8192
        if info.get('CPU', 9999) > 4 or info.get('Memory', 99999) > memory_limit:
            raise LifecycleError('Base exceeds approved CPU/memory bounds')
        archive = self.artifact(platform)
        vm = PREFIX+platform+'-'+uuid.uuid4().hex[:16]
        run = self.state/'runs'/vm
        run.mkdir(mode=0o700, parents=True)
        bootstrap = run/'bootstrap'
        bootstrap.mkdir(mode=0o700)
        for file in ('runner-bootstrap.sh', 'rosetta-linux.sh'):
            shutil.copyfile(SCRIPT_DIR/file, bootstrap/file)
        shutil.copyfile(archive, bootstrap/'runner.tar.gz')
        record = {'repository': REPO, 'vm': vm, 'platform': platform,
                  'clone_created': False, 'registration_started': False, 'cleaned': False}
        self.write_record(run, record)
        process = None
        try:
            # Record ownership before cloning, including partial clone failures.
            record['clone_created'] = True
            self.write_record(run, record)
            self.call(['tart', 'clone', base, vm], timeout=120)
            arguments = ['tart', 'run', '--no-graphics', '--no-clipboard', '--no-audio',
                         '--dir=bootstrap:'+str(bootstrap)+':ro']
            if platform == 'linux':
                arguments.append('--rosetta=rosetta')
            with (run/'tart.log').open('wb') as log:
                process = subprocess.Popen(arguments+[vm], stdout=log, stderr=subprocess.STDOUT,
                                           env=dict(os.environ, PATH=PATH))
            deadline = time.monotonic()+240
            while True:
                try:
                    self.call(['tart', 'exec', vm, '/usr/bin/true'], timeout=5)
                    break
                except (LifecycleError, subprocess.TimeoutExpired):
                    if self.stop.wait(2) or time.monotonic() > deadline or process.poll() is not None:
                        raise LifecycleError('Guest readiness failed')
            if platform == 'macos':
                guest = ['/bin/bash', '/Volumes/My Shared Files/bootstrap/runner-bootstrap.sh']
                python = '/opt/homebrew/bin/python3.13'
            else:
                guest = ['/bin/bash', '-c', 'set -e; sudo -n mkdir -p /mnt/shared; mountpoint -q /mnt/shared || sudo -n mount -t virtiofs com.apple.virtio-fs.automount /mnt/shared; exec /bin/bash /mnt/shared/bootstrap/runner-bootstrap.sh']
                python = '/usr/bin/python3'
            self.wait_command(['tart', 'exec', vm, *guest], run/'bootstrap.log', timeout=1800)
            if prepare_only:
                self.log(platform+' bootstrap verified; no credential created')
                return
            self.check_policy()
            if self.stop.is_set():
                raise LifecycleError('Stopping before registration')
            record['registration_started'] = True
            self.write_record(run, record)
            response = self.api('repos/'+REPO+'/actions/runners/registration-token', 'POST')
            token = response.pop('token')
            data = json.dumps({'token': token, 'name': vm,
                               'label': 'blog-studio-tart-'+platform}).encode()
            del token, response
            try:
                self.call(['tart', 'exec', '-i', vm, python, '-c', REGISTER], data=data, timeout=180)
            finally:
                del data
            self.log(platform+' ephemeral repository runner ready')
            command = 'cd /tmp/blog-studio-actions-runner; export PATH=/tmp/blog-studio-runner-tools/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; exec ./run.sh'
            self.wait_command(['tart', 'exec', vm, '/bin/bash', '-c', command],
                              run/'runner.log', timeout=7200, runner_name=vm)
            self.log(platform+' one-job runner exited')
        finally:
            try:
                self.cleanup(record)
                record['cleaned'] = True
                self.write_record(run, record)
                self.prune_logs()
            finally:
                if process and process.poll() is None:
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        process.wait(timeout=10)

    def worker(self, platform, once=False, prepare_only=False):
        while not self.stop.is_set():
            self.cycle(platform, prepare_only=prepare_only)
            if once or prepare_only:
                break
            self.stop.wait(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--serve', action='store_true')
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--prepare', action='store_true', help='Verify bootstrap without any credential or registration')
    parser.add_argument('--platform', choices=('macos', 'linux', 'all'), default='all')
    parser.add_argument('--state', type=Path, default=STATE)
    args = parser.parse_args()
    if not (args.serve or args.once or args.prepare):
        print(json.dumps({'repository': REPO, 'bases': BASES, 'runner_version': VERSION,
            'state': str(args.state), 'network': 'default NAT; owner-only approved trust model',
            'registration': 'not requested; plan only'}, indent=2))
        return
    os.umask(0o077)
    args.state.mkdir(mode=0o700, parents=True, exist_ok=True)
    service = Service(args.state)
    with (args.state/'service.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        service.check_policy()
        service.recover()
        service.prune_logs()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: service.stop.set())
        platforms = ('macos', 'linux') if args.platform == 'all' else (args.platform,)
        with ThreadPoolExecutor(max_workers=len(platforms)) as pool:
            futures = [pool.submit(service.worker, p, args.once, args.prepare) for p in platforms]
            try:
                for future in as_completed(futures):
                    future.result()
            finally:
                service.stop.set()


if __name__ == '__main__':
    main()
