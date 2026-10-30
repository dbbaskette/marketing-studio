"""Traverse approved checkout links and materialize self-contained studio bundles."""
import os
from pathlib import Path


def shared_link(path):
    """Only the suite's named code and UI links are allowed in source packages."""
    path = Path(path)
    if not path.is_symlink():
        return False
    target = path.resolve()
    for parent in path.parents:
        if not (parent / 'core/studio_core/__init__.py').is_file():
            continue
        if path.name == 'companions.json' and path.parent.name == 'installer' and target == parent / 'pins/companions.json':
            return True
        if path.name in ('index.html', 'app.js', 'home.css') and path.parent == parent / 'marketing_studio/web' and target == parent / 'core/studio_core/setup_web' / path.name:
            return True
        if path.name == 'studio_core' and target == parent / 'core/studio_core':
            return True
        if path.name in ('style.css', 'markdown.js', 'drafting.js', 'research.js') and target == parent / 'ui-kit' / path.name:
            return True
    return False


def files(root):
    """Walk links only when their targets are the suite's shared source directories."""
    root = Path(root)
    result = []
    for directory, dirs, names in os.walk(root, followlinks=True):
        dirs[:] = sorted(name for name in dirs if name not in ('__pycache__', '.git'))
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink() and not shared_link(path):
                raise ValueError('Package files and folders must be regular, not links.')
        result.extend(Path(directory) / name for name in sorted(names))
    return sorted(result)
