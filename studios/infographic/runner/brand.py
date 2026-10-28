"""Pin portable visual constraints from a selected shared brand contract."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from studio_core import brand_catalog

from .contracts import Invalid, canonical, digest
from .provider_capabilities import private_child_environment
from .validation import require, text

HEX = re.compile(r'#[0-9a-fA-F]{6}\Z')
FONT = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,100}\Z')


def snapshot(contract: dict) -> dict:
    require(isinstance(contract, dict) and contract.get('schema') == 1,
            'Export a supported shared brand contract first.')
    identity, design = contract.get('identity'), contract.get('design')
    require(isinstance(identity, dict) and text(identity.get('id')) and text(identity.get('name'))
            and text(contract.get('revision')) and isinstance(design, dict),
            'The brand contract needs identity, revision and visual guidance.')
    colors = design.get('colors')
    require(isinstance(colors, dict) and all(isinstance(value, str) and HEX.fullmatch(value) for value in colors.values())
            and all(key in colors for key in ('canvasPrimary', 'inkPrimary', 'headingPrimary')),
            'The brand needs explicit hexadecimal canvas, text and heading colors.')
    require(isinstance(design.get('fontFamily'), str) and FONT.fullmatch(design['fontFamily']),
            'The brand needs an explicit supported font family. Install licensed fonts before rendering.')
    floors = design.get('infographicTypography') or {}
    require(isinstance(floors, dict) and set(floors) <= {'body_pt', 'source_pt', 'body_px', 'source_px'}
            and all(type(v) in (int, float) and 0 < v <= 100 for v in floors.values()),
            'Infographic typography constraints must name finite positive point/pixel size floors.')
    # Never import slide geometry, native templates, private reference paths or voice profiles.
    result = {'revision': contract['revision'], 'identity': deepcopy(identity),
              'contract_sha256': digest(contract), 'font': design['fontFamily'],
              'colors': deepcopy(colors), 'imagery': deepcopy(design.get('imagery', {})),
              'geometry': deepcopy(design.get('geometry', {})),
              'accessibility': deepcopy(design.get('accessibility', {})),
              'type_floors': deepcopy(floors), 'color_policy': deepcopy(design.get('colorPolicy', {})),
              'font_license': 'The installed font license controls embedding and redistribution. No font files are exported.',
              'reference_assets': []}
    result['sha256'] = digest(result)
    return result


def type_floors(pinned, digital):
    floors = pinned.get('type_floors', {})
    return (max(24, floors.get('body_px', 24)), max(18, floors.get('source_px', 18))) if digital else (
            max(12, floors.get('body_pt', 12)), max(9, floors.get('source_pt', 9)))


def export_selected(*, skill: Path, brand_id: str, variant: str | None = None,
                    run=subprocess.run, which=shutil.which) -> dict:
    """Explicit selection; use the shared non-canvas contract, not slide templates."""
    catalog = brand_catalog.choices(skill=skill, run=run, which=which)
    selected = next((entry for entry in catalog['skills']
                     if any(brand['brand'] == brand_id for brand in entry['brands'])), None)
    require(selected is not None, catalog.get('problem') or 'Select an installed brand capability; none is installed automatically.')
    choice = next(brand for brand in selected['brands'] if brand['brand'] == brand_id)
    require(variant is None or variant in choice['variants'], 'Choose a supported brand variant.')
    with tempfile.TemporaryDirectory(prefix='infographic-brand-') as name:
        output = Path(name) / 'contract'
        command = [which('node'), str(Path(selected['path']) / 'scripts' / (selected['name'] + '.mjs')),
                   'contract', 'export', '--medium', 'blog', '--brand', brand_id, '--output', str(output)]
        if variant:
            command += ['--variant', variant]
        import os
        try:
            done = run(command, capture_output=True, text=True, timeout=60,
                       env=private_child_environment(os.environ))
            require(done.returncode == 0, 'The installed brand could not export its shared visual contract. Check its local compatibility.')
            path = output / 'brand-contract.json'
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000,
                    'The brand did not return a bounded shared contract.')
            return snapshot(json.loads(path.read_text()))
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
            raise Invalid('The selected brand contract could not be read. No brand was installed or updated.') from failure


def adopt(store, ident: str, contract: dict, *, expected_revision: int) -> dict:
    return store.update(ident, {'brand': snapshot(contract)}, expected_revision=expected_revision)
