"""Discover independent installs and sibling source checkouts without importing them."""
import os
from pathlib import Path

STUDIOS = {
    'blog': ('Blog Studio', 'blog-studio', 'Shape your ideas into blogs in your voice.', 'blogs'),
    'presentation': ('Presentation Studio', 'presentation-studio', 'Build a researched deck in your brand.', 'presentations'),
    'training': ('Training Studio', 'training-studio', 'Turn a topic into training people can use.', 'trainings'),
}


def entry(studio, root):
    slug = STUDIOS[studio][1]
    if studio == 'blog':
        source = root / 'skills' / slug / 'scripts' / 'start_studio.py'
        return source if source.is_file() else root / 'scripts' / 'start_studio.py'
    return root / 'runner' / 'studio.py'


def locate(studio, paths):
    slug = STUDIOS[studio][1]
    named = os.environ.get(slug.upper().replace('-', '_') + '_INSTALL') or paths.get(studio)
    candidates = [Path(named).expanduser()] if named else [
        Path(__file__).resolve().parents[1] / 'studios' / studio,
        Path(__file__).resolve().parents[2] / slug,
        Path.home() / '.local/share' / slug / 'current',
        Path.home() / '.local/share' / slug / 'current' / 'runtime',
    ]
    suite = Path(__file__).resolve().parents[1]
    if not named and suite.parent.name == 'versions':
        candidates = candidates[2:] + candidates[:2]
    for candidate in candidates:
        if entry(studio, candidate).is_file():
            return candidate.resolve()
    return None


def describe(paths, running):
    rows = []
    for identifier, (name, slug, description, folder) in STUDIOS.items():
        root = locate(identifier, paths)
        version = None
        if root:
            try:
                version = (root / 'VERSION').read_text().strip()
            except OSError:
                pass
        rows.append({'id': identifier, 'name': name, 'description': description,
                     'installed': root is not None, 'path': str(root) if root else None,
                     'configured_path': paths.get(identifier, ''), 'version': version,
                     'running': running(identifier),
                     'repository': 'https://github.com/dbbaskette/marketing-studio/tree/main/studios/' + identifier})
    return rows
