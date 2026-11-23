"""Read installed brand choices on explicit request; never install or update a skill."""
import json
import os
import re
import shutil
import subprocess

from studio_core import brand_skills
from studio_core.packaging import stable_place


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
        return {'skills': [], 'problem': 'Node.js is needed to list installed brands. You can keep the saved IDs or leave them blank.'}
    seen, found, problems = set(), [], []
    for folder in roots[:100]:
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
    problem = ' '.join(problems) or (None if found else 'No installed brand skill was found. Keep a repository address for installation from a studio’s settings, or leave the brand blank for now.')
    return {'skills': found, 'problem': problem}
