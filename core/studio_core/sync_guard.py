"""Conservative exclusion of canonical Studio workers during repository replay."""
import json
import os
from pathlib import Path

SYNC_WAIT = ('A Studio step is still in progress in this repository. Stop it or wait for it '
             'to finish, then share again. If the Studio closed during the step, reopen it '
             'to recover the saved work first.')


def worker_in_progress(repo: Path, refusal=ValueError) -> bool:
    """Check known canonical worker records without following directory links.

    A missing marker is idle; unreadable scope or a malformed Blog Studio worker
    record is unknown and refuses replay. Output caches and Git internals are not
    candidates. Leftover markers remain busy until the existing recovery runs.
    """
    def unknown(error):
        raise refusal('The repository could not be checked for running Studio steps. '
                      'Check its saved worker records and folder permissions, then '
                      'share again.') from error

    def present(path):
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False
        except OSError as error:
            unknown(error)

    def blog_busy(folder):
        for directory in (folder, folder / 'tools'):
            if not present(directory):
                continue
            if directory.is_symlink():
                unknown(ValueError('Linked worker records'))
            try:
                for path in directory.iterdir():
                    if path.suffix != '.json' or (directory == folder and path.stem in (
                            'voice-guides', 'desk-step-times')):
                        continue
                    if path.is_symlink() or path.stat().st_size > 1_000_000:
                        unknown(ValueError('Unsupported worker record'))
                    value = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(value, dict) or not isinstance(value.get('status'), str):
                        unknown(ValueError('Unreadable worker status'))
                    if value['status'] == 'working':
                        return True
            except (OSError, ValueError) as error:
                unknown(error)
        return False

    for folder, directories, _ in os.walk(repo, followlinks=False, onerror=unknown):
        here = Path(folder)
        if any(present(here / name) for name in ('work/step.lock', '.training-studio/step.lock')):
            return True
        if present(here / '.blog-runs') and blog_busy(here / '.blog-runs'):
            return True
        directories[:] = [name for name in directories
                          if name not in ('.git', 'work', 'sources', '.training-studio',
                                          '.presentation-studio', '.blog-runs')
                          and not (here / name).is_symlink()]
    return False
