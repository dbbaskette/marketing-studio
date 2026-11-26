"""Read installed brand choices on explicit request; never install or update a skill.

A listing is kept for a short while so that a page asking again does not run every brand
skill again. It is used again only within KEPT_FOR seconds of the scan that made it, and
only while every place looked in is the same: the same folders, each resolving to the same
folder with the same modification time and the same modification time of its `scripts`
folder, the same Node.js, and the same brands folder (HARNESS_BRAND_DATA) with the same
modification time. Installing, removing, updating or relinking a brand skill changes one of
these, so it shows at once; anything else shows within KEPT_FOR seconds.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import threading
import time

from studio_core import brand_skills
from studio_core.packaging import stable_place

KEPT_FOR = 15     # seconds a listing is used again while nothing it was read from changed
MOST = 100        # skill folders looked at
_KEPT: dict = {}  # what a listing was read from -> (when, the listing)
_HELD = threading.Lock()
NO_NODE = 'Node.js is needed to list installed brands. You can keep the saved IDs or leave them blank.'
NONE_FOUND = ('No installed brand skill was found. Keep a repository address for installation from a '
              'studio’s settings, or leave the brand blank for now.')
# What a caller that came over Marketing Studio's network bridge (a phone on the private link)
# is told instead of anything naming a folder on this computer.
REMOTE_SKILL = ('The installed brand skill folder in these settings is read only on the computer '
                'Marketing Studio runs on. Look up its brands there, or enter a brand ID.')
REMOTE_UNASKED = ('Some installed brand skills could not be asked for their brands. See why on the '
                  'computer Marketing Studio runs on, or enter a brand ID.')
REMOTE_UNLISTED = ('The installed brands could not be listed. See why on the computer Marketing '
                   'Studio runs on, or enter a brand ID.')


def _looked_at(roots, env, node):
    """What a listing is read from, as cheaply as it can be read: each folder looked in,
    with the folder it resolves to and the modification times of it and of its `scripts`
    folder, Node.js, and the brands folder with its modification time. Nothing is run."""
    marks = []
    for folder in roots[:MOST]:
        try:
            real = folder.resolve(strict=True)
            made = real.stat().st_mtime_ns
        except (OSError, RuntimeError):
            marks.append((str(folder), None))
            continue
        try:
            scripts = (real / 'scripts').stat().st_mtime_ns
        except OSError:
            scripts = None
        marks.append((str(folder), str(real), made, scripts))
    data = env.get(brand_skills.DATA)
    try:
        data_made = os.stat(data).st_mtime_ns if data else None
    except OSError:
        data_made = None
    return tuple(marks), node, data, data_made


def choices(skill=None, home=None, run=subprocess.run, which=shutil.which):
    selected = skill or os.environ.get('BRAND_SKILL_RUNTIME')
    # A folder saved inside `versions/` is said through `current`; so is each one found. An
    # update keeps only the newest version, and the saved folder may be gone. Every studio
    # looks in the same places (studio_core.brand_skills).
    roots = brand_skills.locations(selected, home=home)
    # The brands the shared settings name (`brand.brands`), not a folder recorded earlier.
    env = brand_skills.environment()
    node = which('node')
    if not node:
        return {'skills': [], 'problem': NO_NODE}
    key = (str(selected), str(home), run, which, _looked_at(roots, env, node))
    now = time.monotonic()
    with _HELD:
        kept = _KEPT.get(key)
        if kept is not None and 0 <= now - kept[0] < KEPT_FOR:
            return copy.deepcopy(kept[1])
    found = _scan(roots, env, node, run)
    with _HELD:
        for old in [old for old, (when, _) in _KEPT.items()
                    if not 0 <= now - when < KEPT_FOR]:
            del _KEPT[old]
        if len(_KEPT) >= 32:
            _KEPT.clear()
        _KEPT[key] = (now, found)
    return copy.deepcopy(found)


def _scan(roots, env, node, run):
    """Ask each brand skill in `roots` for its brands."""
    seen, found, problems = set(), [], []
    for folder in roots[:MOST]:
        try:
            seen_as = folder.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        folder = stable_place(folder)
        if seen_as in seen or not (folder / 'SKILL.md').is_file():
            continue
        seen.add(seen_as)
        try:
            package = json.loads((folder / 'package.json').read_text()).get('name')
        except (OSError, ValueError, AttributeError):
            package = None
        for name in dict.fromkeys((package, folder.name)):
            if not isinstance(name, str) or not re.fullmatch(r'[\w.-]+', name):
                continue
            script = folder / 'scripts' / (name + '.mjs')
            try:
                if not script.is_file():
                    continue
                with script.open(errors='replace') as source:
                    if 'brands' not in source.read(200_000):
                        continue
                done = run([node, str(script), 'brands', '--json'], capture_output=True,
                           text=True, timeout=10, env=env)
                if done.returncode or len(done.stdout) > 1_000_000:
                    raise ValueError('The brand command did not return a readable list.')
                data = json.loads(done.stdout)
                brands = data.get('brands') if isinstance(data, dict) else data
                if not isinstance(brands, list):
                    raise ValueError('The brand command did not return a list.')
                valid = []
                for brand in brands[:100]:
                    if not isinstance(brand, dict) or not isinstance(brand.get('brand'), str):
                        raise ValueError('The brand list has an unreadable entry.')
                    variants = brand.get('variants') or []
                    if not isinstance(variants, list) or not all(isinstance(v, str) for v in variants):
                        raise ValueError('The brand list has unreadable variants.')
                    valid.append({'brand': brand['brand'], 'name': str(brand.get('name') or brand['brand']), 'variants': variants})
                found.append({'name': name, 'path': str(folder), 'brands': valid})
                break
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                problems.append(f'{name}: {error}')
    problem = ' '.join(problems) or (None if found else NONE_FOUND)
    return {'skills': found, 'problem': problem}


def unplaced(found: dict) -> dict:
    """`choices` for a caller that came over the network: each skill's name and brands with
    their variants, without the folder it is in, and a problem said without the folders or
    error text it may name on this computer."""
    skills = [{'name': skill.get('name'), 'brands': skill.get('brands') or []}
              for skill in found.get('skills') or [] if isinstance(skill, dict)]
    problem = found.get('problem')
    if problem not in (None, NO_NODE, NONE_FOUND):
        problem = REMOTE_UNASKED
    return {'skills': skills, 'problem': problem}


def listed(skill=None, remote=False) -> dict:
    """The installed brands as Shared settings' Brand card asks for them; never raises.
    A caller on this computer gets `choices(skill)` as it is. A caller that came over the
    network bridge is told names only, and a skill folder it names is refused unread:
    choosing one is done on the computer."""
    if remote and skill is not None:
        return {'skills': [], 'problem': REMOTE_SKILL}
    try:
        found = choices(skill)
    except (ValueError, OSError) as failure:
        if remote:
            return {'skills': [], 'problem': REMOTE_UNLISTED}
        return {'skills': [], 'problem': f'The installed brands could not be listed: {failure}'}
    return unplaced(found) if remote else found
