"""Where a brand skill may be installed, and the brands folder its commands are told: one
answer for Marketing Studio, Blog Studio, Presentation Studio, Training Studio and
Infographic Studio.

What a caller needs to know
---------------------------
    brand_skills.locations()                  # every folder that may be a brand skill
    brand_skills.locations(chosen, home=...)  # a chosen folder, which is the only place
    brand_skills.installed(home)              # every usual place, with no override
    brand_skills.setting('skill')             # a `brand` shared setting, or None
    brand_skills.brands_folder()              # the folder `brand.brands` names, when there
    brand_skills.environment(env)             # env with HARNESS_BRAND_DATA told

- A folder the caller chose (the `brand.skill` shared setting, or one a person picked) is
  the only place looked, said through its installer's `current` link when it was saved
  inside a `versions/` folder. Else BRAND_SKILL_RUNTIME, when set, is the only place.
  Else every folder in each place a brand skill is installed: the installers' own folders
  (`~/Library/Application Support/*/current`, `~/.local/share/*/current`), then the
  Claude Code, `~/.agents`, Codex and Cursor skills folders, each in name order.
- Nothing here runs a skill or installs anything; a caller asks each folder it is given.
- `setting` reads the shared studios-config file through studio_core.studios_config and
  never writes it. A file that cannot be read is no setting.
- `brands_folder` is where `brand.brands` keeps the brands (studio_core.brand_data.place),
  when that folder is there; None when the setting is blank, unreadable or not fetched yet.
- `environment` copies `env` (this process's environment when None) and names that folder
  in HARNESS_BRAND_DATA, so a brand skill reads the brands the shared settings name, not a
  folder recorded earlier. With no such folder, `env` is kept as it is.
"""
from __future__ import annotations

import os
from pathlib import Path

VARIABLE = 'BRAND_SKILL_RUNTIME'
DATA = 'HARNESS_BRAND_DATA'
# Each holds a folder per installed skill, kept by the skill's own installer as `<name>/current`.
MANAGED = (('Library', 'Application Support'), ('.local', 'share'))
# The skills folder of each assistant a brand skill may be installed for.
ASSISTANTS = (('.claude', 'skills'), ('.agents', 'skills'), ('.codex', 'skills'),
              ('.cursor', 'skills'))


def _inside(folder: Path) -> list[Path]:
    try:
        return sorted(folder.iterdir())
    except OSError:
        return []


def installed(home: Path | None = None) -> list[Path]:
    """Every folder that may be an installed brand skill, in the usual places only. `home`
    stands in for the person's home folder."""
    user = Path(home) if home is not None else Path.home()
    return [place / 'current' for parts in MANAGED for place in _inside(user.joinpath(*parts))] \
        + [place for parts in ASSISTANTS for place in _inside(user.joinpath(*parts))]


def locations(chosen=None, home: Path | None = None) -> list[Path]:
    """Every folder that may be the brand skill in use: the chosen folder alone, else the
    one BRAND_SKILL_RUNTIME names alone, else every usual place (`installed`)."""
    from studio_core.packaging import stable_address
    if chosen:
        return [stable_address(Path(chosen).expanduser(), saved=True)]
    named = os.environ.get(VARIABLE)
    if named:
        return [Path(named).expanduser()]
    return installed(home)


def setting(name: str):
    """A value of the shared `brand` settings, as text, or None when it is not set or the
    file cannot be read."""
    from studio_core import studios_config
    try:
        values, problem = studios_config.read()
    except (OSError, ValueError):
        return None
    brand = values.get('brand') if not problem and isinstance(values, dict) else None
    value = brand.get(name) if isinstance(brand, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def brands_folder(address=None) -> Path | None:
    """The folder `brand.brands` (or `address`) keeps the brands in, when it is there."""
    from studio_core import brand_data
    address = address if address is not None else setting('brands')
    if not isinstance(address, str) or not address.strip():
        return None
    try:
        folder = brand_data.place(address.strip())
    except ValueError:
        return None
    return folder if folder.is_dir() else None


def environment(env=None, address=None) -> dict:
    """`env`, or this process's environment, with HARNESS_BRAND_DATA naming the brands
    folder the shared settings name. Left as it is when they name none that is there."""
    told = dict(os.environ if env is None else env)
    folder = brands_folder(address)
    if folder is not None:
        told[DATA] = str(folder)
    return told
