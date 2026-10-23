"""Local, unreviewed slide previews, bound to the current build and worker attempt.

This is a display cache, never evidence of review or permission to accept a deck.
The producer's native-deck and compiled-build revisions are separate identities.
"""
from contextlib import contextmanager
import fcntl
import hashlib
from pathlib import Path
import re
import secrets

import home
from workspace import WorkspaceError

FOLDER = Path('work/build/progress')
HEX = re.compile(r'^[0-9a-f]{64}$')
REF = re.compile(r'^[0-9a-f]{32}$')


@contextmanager
def locked(root, create=False):
    folder = Path(root) / FOLDER
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    elif not folder.is_dir():
        yield None
        return
    with (folder / '.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield folder


def begin(root, basis, part, slides):
    """Only a dispatched build job may replace the current owner of its section."""
    owner = secrets.token_hex(16)
    with locked(root, create=True) as folder:
        index = home.read_json(folder / 'index.json', {})
        if index.get('basis') != basis:
            index = {'basis': basis, 'parts': {}}
        index['parts'][part] = {'owner': owner, 'slides': slides, 'images': {},
                                'status': 'drawing', 'started_at': home.now()}
        if part != 'whole':
            index['parts'].pop('whole', None)
        else:
            # A whole preview was built from the completed sections. Keep their
            # images, but close the old writers before publishing the new deck.
            for name, entry in index['parts'].items():
                if name != 'whole':
                    entry['owner'] = 'sealed-' + secrets.token_hex(16)
        home.write_json(folder / 'index.json', index)
    return {'root': str(Path(root).resolve()), 'basis': basis, 'part': part, 'owner': owner}


class Preview:
    """One render of one attempt. Superseded attempts cannot publish into a newer one."""
    def __init__(self, spec, output):
        self.spec, self.output = spec, Path(output).resolve()
        self.render = secrets.token_hex(16)
        self.revision = self.build_revision = None
        self._update(lambda entry: entry.update(render=self.render, images={}, status='rendering'), activate=True)

    def _update(self, change, activate=False):
        spec = self.spec
        with locked(spec['root']) as folder:
            if folder is None:
                return False
            index = home.read_json(folder / 'index.json', {})
            entry = (index.get('parts') or {}).get(spec['part'])
            if index.get('basis') != spec['basis'] or not entry or entry.get('owner') != spec['owner']:
                return False
            if entry.get('render') and entry['render'] != self.render and not activate:
                # Activation is handled once, when the preview starts.
                return False
            if change is not None:
                change(entry)
                home.write_json(folder / 'index.json', index)
            return True

    def _image(self, event):
        from runner.worker_tools import picture
        spec = self.spec
        with locked(spec['root']) as folder:
            if folder is None:
                return False
            index = home.read_json(folder / 'index.json', {})
            entry = (index.get('parts') or {}).get(spec['part'])
            if index.get('basis') != spec['basis'] or not entry or entry.get('owner') != spec['owner'] \
                    or entry.get('render') != self.render:
                return False
            slide = next((slide for slide in entry['slides'] if slide['id'] == event['slide']), None)
            path = Path(event['path'])
            path = path if path.is_absolute() else self.output / path
            if slide is None or self.output not in path.resolve().parents:
                return False
            data = picture(path)
            ref = hashlib.sha256((self.render + event['revision'] + event['slide']).encode()).hexdigest()[:32]
            target = folder / (ref + '.png')
            if target.exists() and target.read_bytes() != data:
                return False
            pending = folder / ('.' + ref + '-' + secrets.token_hex(4))
            try:
                pending.write_bytes(data)
                pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
            entry['images'][slide['id']] = {**slide, 'ref': ref, 'revision': event['revision'],
                                            'buildRevision': self.build_revision,
                                            'ready_at': home.now(), 'reused': bool(event.get('reused'))}
            entry.setdefault('first_ready_at', home.now())
            index.setdefault('timings', {}).setdefault('first_whole_preview_at' if spec['part'] == 'whole' else 'first_section_ready_at', home.now())
            home.write_json(folder / 'index.json', index)
            return True

    def finish(self, found):
        """A finished preview publishes each slide's picture before whole-deck review."""
        revision = found.get('deckSha256')
        if not isinstance(revision, str) or not HEX.fullmatch(revision):
            return
        if self.revision is not None and revision != self.revision:
            self.failed()
            return
        for slide in found.get('slides') or ():
            if isinstance(slide, dict) and isinstance(slide.get('id'), str) and isinstance(slide.get('image'), str):
                try:
                    self._image({'slide': slide['id'], 'path': slide['image'], 'revision': revision})
                except (OSError, ValueError, WorkspaceError):
                    continue
        self._update(lambda entry: entry.update(status='rendered'))

    def failed(self):
        self._update(lambda entry: entry.update(status='incomplete'))


def invalidate(root, basis, part):
    with locked(root) as folder:
        if folder is None:
            return
        index = home.read_json(folder / 'index.json', {})
        if index.get('basis') == basis and part in (index.get('parts') or {}):
            entry = index['parts'][part]
            entry.update(owner='superseded-' + secrets.token_hex(16), status='needs-changes')
            home.write_json(folder / 'index.json', index)


def view(root, basis):
    index = home.read_json(Path(root) / FOLDER / 'index.json', {})
    if index.get('basis') != basis:
        return None
    parts = index.get('parts') or {}
    # A later whole preview takes precedence over section images of the same slide.
    slides = {}
    for part, entry in sorted(parts.items(), key=lambda pair: pair[0] == 'whole'):
        for ident, image in (entry.get('images') or {}).items():
            slides[ident] = {**image, 'part': part, 'status': entry['status']}
    if not slides:
        return None
    return {'slides': sorted(slides.values(), key=lambda one: one['number']),
            'incomplete': any(entry.get('status') == 'incomplete' for entry in parts.values())}


def image(root, basis, ref):
    if not isinstance(ref, str) or not REF.fullmatch(ref):
        raise FileNotFoundError('No current build preview has that name.')
    shown = view(root, basis)
    if not shown or not any(slide['ref'] == ref for slide in shown['slides']):
        raise FileNotFoundError('That preview has been replaced.')
    from runner.worker_tools import picture
    path = Path(root) / FOLDER / (ref + '.png')
    if path.is_symlink() or (Path(root) / FOLDER).resolve() not in path.resolve().parents:
        raise FileNotFoundError('No current build preview has that name.')
    return picture(path)


def mark(root, basis, name, ref=None):
    """Local display measurements, never review or approval receipts."""
    with locked(root) as folder:
        if folder is None:
            return {}
        index = home.read_json(folder / 'index.json', {})
        if index.get('basis') != basis:
            return {}
        if ref is not None:
            images = [image for part, entry in (index.get('parts') or {}).items()
                      if part != 'whole' for image in (entry.get('images') or {}).values()]
            if not any(image['ref'] == ref for image in images):
                return {}
        timings = index.setdefault('timings', {})
        if name not in timings:
            timings[name] = home.now()
            home.write_json(folder / 'index.json', index)
        return dict(timings)


def timings(root):
    return home.read_json(Path(root) / FOLDER / 'index.json', {}).get('timings', {})
