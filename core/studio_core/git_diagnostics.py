"""Explain Git failures that produce no stderr, retaining local diagnostic evidence."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import tempfile


def silent_failure(done, command, product):
    status = done.returncode
    if status < 0:
        try:
            name = signal.Signals(-status).name
        except ValueError:
            name = str(-status)
        detail = 'signal ' + name
    else:
        detail = 'exit status ' + str(status)
    # Command names only: arguments can include repository credentials or content.
    verb = command if command and command.isalpha() else 'command'
    message = f'Git {verb} failed with {detail} and no error output'
    root = Path(os.environ.get(product.upper() + '_STUDIO_DATA')
                or Path.home() / '.local/share' / (product + '-studio'))
    try:
        directory = root / 'logs'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        descriptor, filename = tempfile.mkstemp(prefix='git-' + stamp + '-', suffix='.json', dir=directory)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'time': stamp, 'command': 'git ' + verb, 'returncode': status,
                       'executable': getattr(done, 'studio_git', None),
                       'working_directory': getattr(done, 'studio_cwd', None)}, stream, indent=2)
            stream.write('\n')
        return message + '. Details: ' + filename
    except OSError:
        return message
