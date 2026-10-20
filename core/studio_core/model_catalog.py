"""Read-only model catalogs shared by setup and the native model pickers."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from copy import deepcopy

from studio_core.model_profiles import EFFORTS, check_choice

SECONDS = 30
LIMIT = 2 * 1024 * 1024
BUNDLED_CODEX = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')


class Unavailable(ValueError):
    """Why a model list is unavailable, in words for the person choosing a model."""


def clip(text, length=140):
    text = ' '.join(str(text).split())
    return text if len(text) <= length else text[:length - 1] + '…'


def codex_models(printed: str) -> list[dict]:
    """The models in Codex's catalog that it lists for choosing, each with the levels it
    takes that `settings` knows, and the one it uses when none is given."""
    unreadable = Unavailable('Codex listed its models in a form this runner cannot read.')
    try:
        catalog = json.loads(printed)
    except ValueError:
        raise unreadable
    entries = catalog.get('models') if isinstance(catalog, dict) else None
    if not isinstance(entries, list):
        raise unreadable
    known, found = EFFORTS['codex'], []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('visibility', 'list') != 'list':
            continue
        name = entry.get('slug')
        try:
            if not name:
                continue
            check_choice(name, None, 'codex')
        except ValueError:
            continue
        levels = []
        for level in entry.get('supported_reasoning_levels') or ():
            word = level.get('effort') if isinstance(level, dict) else level
            if isinstance(word, str) and word in known and word not in levels:
                levels.append(word)
        shown, about = entry.get('display_name'), entry.get('description')
        shown = clip(shown, 80) if isinstance(shown, str) and shown.strip() else name
        usual = entry.get('default_reasoning_level')
        found.append({'name': name, 'label': name if shown == name else f'{shown} ({name})',
                      'family': None,
                      'about': clip(about, 120) if isinstance(about, str) and about.strip()
                      else None,
                      'default_level': usual if usual in levels else None, 'levels': levels})
    return found



def claude_models():
    """Use the studios' existing cached reference, with its provenance visible."""
    kept = json.loads(Path(__file__).with_name('claude-code-models.json').read_text())
    entries = {entry['id']: entry for entry in kept['models']}
    found = []
    for name, entry in entries.items():
        check_choice(name, None, 'claude')
        meant = entries[entry['alias']] if 'alias' in entry else entry
        label = (f'{entry["family"]}, always the newest (now {meant["label"]})'
                 if meant is not entry else f'{entry["label"]} ({name})')
        found.append({'name': name, 'label': label, 'family': entry['family'],
                      'about': None, 'levels': list(meant['levels']), 'default_level': None})
    return {'models': found, 'levels': list(EFFORTS['claude']),
            'source': kept.get('source') or 'Bundled Claude Code reference'}


def codex_output():
    binary = shutil.which('codex') or (str(BUNDLED_CODEX) if BUNDLED_CODEX.is_file() else None)
    if not binary:
        raise Unavailable('Codex was not found. Install it and sign in, or enter a model ID.')
    # No prompt, workspace, provider job, shell, installation or user-config writes.
    # Regular temporary files bound the amount read and avoid a blocked output pipe.
    with tempfile.TemporaryDirectory(prefix='studio-model-list-') as temporary:
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen([binary, 'debug', 'models'], cwd=temporary,
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                start_new_session=True)
            try:
                deadline = time.monotonic() + SECONDS
                while process.poll() is None:
                    if time.monotonic() >= deadline or output.tell() > LIMIT:
                        raise Unavailable('The model list did not finish. Enter a model ID or try Refresh models.')
                    time.sleep(.05)
                if process.returncode or output.tell() > LIMIT:
                    raise Unavailable('Codex could not list models. Check its sign-in, enter a model ID, or try Refresh models.')
                output.seek(0)
                return output.read(LIMIT).decode('utf-8')
            finally:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)


def discover(agent):
    if agent == 'claude':
        return claude_models()
    models = codex_models(codex_output())
    return {'models': models, 'levels': list(EFFORTS['codex']),
            'source': 'Your Codex CLI model list'}


class Catalog:
    def __init__(self, loader=discover):
        self.loader = loader
        self.locks = {agent: threading.Lock() for agent in EFFORTS}
        self.saved = {}

    def get(self, agent, refresh=False):
        if not isinstance(agent, str) or agent not in EFFORTS:
            raise ValueError('Choose Claude Code or Codex.')
        with self.locks[agent]:
            kept = self.saved.get(agent)
            if not refresh and kept and time.monotonic() < kept[0]:
                return deepcopy(kept[1])
            try:
                result = {**self.loader(agent), 'agent': agent, 'problem': None}
                if not result['models']:
                    raise Unavailable('No models were listed. Enter a model ID or try Refresh models.')
            except (OSError, ValueError, KeyError, TypeError, UnicodeError) as failure:
                # Only a reason written for people is shown; a provider's own output is not.
                problem = (f'{failure} Your choices are kept.' if isinstance(failure, Unavailable) else
                           'The model list is unavailable. Your choices are kept. Enter a model ID or try Refresh models.')
                result = {'agent': agent, 'models': [], 'levels': list(EFFORTS[agent]),
                          'source': None, 'problem': problem}
            self.saved[agent] = (time.monotonic() + (30 if result['problem'] else 3600), result)
            return deepcopy(result)
