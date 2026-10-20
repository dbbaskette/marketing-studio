"""Private installer transcripts and subprocess diagnostics, without dependencies."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
import platform
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

LOG_ENV = 'STUDIO_INSTALL_LOG'
SECRET = re.compile(r'token|password|secret|api.?key|authorization', re.I)


def redact(value):
    text = str(value)
    text = re.sub(r'([a-z][a-z0-9+.-]*://)[^/\s@]+@', r'\1[redacted]@', text)
    text = re.sub(r'(?i)([?&](?:token|key|api_key|access_token|signature)=)[^&\s]+',
                  r'\1[redacted]', text)
    text = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[redacted]', text)
    for name, secret in os.environ.items():
        if SECRET.search(name) and len(secret) >= 6:
            text = text.replace(secret, '[redacted]')
    return text


def command_text(command):
    if isinstance(command, (str, bytes)):
        return '[shell command omitted]'
    values, hide = [], False
    for item in command:
        item = os.fsdecode(item)
        if hide:
            values.append('[redacted]')
            hide = False
        elif item.startswith('-') and SECRET.search(item):
            option, separator, _ = item.partition('=')
            values.append(option + ('=[redacted]' if separator else ''))
            hide = not separator
        else:
            values.append(redact(item))
    return shlex.join(values)


def selected_home(arguments):
    home = Path.home()
    for index, argument in enumerate(arguments):
        if argument == '--home' and index + 1 < len(arguments):
            home = Path(arguments[index + 1])
        elif argument.startswith('--home='):
            home = Path(argument.split('=', 1)[1])
    return home.expanduser().resolve()


class Transcript:
    def __init__(self, path):
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            os.close(descriptor)
            raise ValueError('Installation log must be a private regular file owned by this user.')
        self.stream = os.fdopen(descriptor, 'a', encoding='utf-8', buffering=1)

    def write(self, value):
        self.stream.write(redact(value))

    def event(self, value):
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.write(f'\n{stamp} [pid {os.getpid()}] {value}\n')


class Tee:
    def __init__(self, stream, transcript):
        self.stream, self.transcript = stream, transcript

    def write(self, text):
        self.transcript.write(text)
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()
        self.transcript.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextmanager
def session(product, arguments=None):
    """Instrument only an installer entrypoint; imports and dry runs have no effects."""
    arguments = sys.argv[1:] if arguments is None else arguments
    if any(arg in ('--help', '-h', '--dry-run') for arg in arguments):
        yield
        return
    inherited = os.environ.get(LOG_ENV)
    if inherited:
        path = Path(inherited)
    else:
        directory = selected_home(arguments) / '.local/state/marketing-studio/logs'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        descriptor, name = tempfile.mkstemp(prefix='install-' + stamp + '-', suffix='.log', dir=directory)
        os.close(descriptor)
        path = Path(name)
    transcript = Transcript(path)
    previous = os.environ.get(LOG_ENV)
    os.environ[LOG_ENV] = str(path)
    original_run, stdout, stderr = subprocess.run, sys.stdout, sys.stderr
    console_logged = os.environ.get('STUDIO_INSTALL_CONSOLE_LOGGED') == '1'
    if not console_logged:
        sys.stdout, sys.stderr = Tee(stdout, transcript), Tee(stderr, transcript)
    print('Installation log: ' + str(path), file=sys.stderr, flush=True)
    transcript.event(f'{product}: Python {sys.version.split()[0]} ({sys.executable})')
    transcript.event('Platform: ' + platform.platform())
    transcript.event('Installer: ' + command_text([sys.executable, *sys.argv]))

    def run(*args, **kwargs):
        command = args[0] if args else kwargs.get('args', [])
        transcript.event('Run: ' + command_text(command) + '\nWorking directory: '
                         + str(kwargs.get('cwd') or Path.cwd()))
        started = time.monotonic()
        try:
            result = original_run(*args, **kwargs)
        except (OSError, subprocess.SubprocessError) as error:
            for name in ('stdout', 'stderr'):
                value = getattr(error, name, None)
                if value:
                    transcript.write(value.decode('utf-8', 'replace') if isinstance(value, bytes) else value)
            transcript.event(f'Command raised {type(error).__name__} after '
                             f'{time.monotonic() - started:.2f}s; '
                             f'exit status: {getattr(error, "returncode", "unavailable")}')
            raise
        for name in ('stdout', 'stderr'):
            value = getattr(result, name, None)
            if value:
                transcript.write(f'\n{name}:\n')
                transcript.write(value.decode('utf-8', 'replace') if isinstance(value, bytes) else value)
        transcript.event(f'Command finished: exit {result.returncode}, {time.monotonic() - started:.2f}s')
        return result

    subprocess.run = run
    try:
        yield
    except BaseException as error:
        status = error.code if isinstance(error, SystemExit) else 1
        transcript.event(f'{product} finished: exit {status}; {type(error).__name__}: {error}')
        raise
    else:
        transcript.event(f'{product} finished: exit 0')
    finally:
        subprocess.run, sys.stdout, sys.stderr = original_run, stdout, stderr
        if previous is None:
            os.environ.pop(LOG_ENV, None)
        else:
            os.environ[LOG_ENV] = previous
        transcript.stream.close()
