"""Prepare a slide edit away from the training and publish only its changed files.

Rendering, saving, and tool failures cannot alter the live deck. Publication checks
its inputs again and keeps a before/after journal until every write has succeeded.
The previous round is retained: deleting it is unnecessary for a word edit.
"""
import hashlib
import shutil
import tempfile
from pathlib import Path

import home
from workspace import WorkspaceError, locked, write_atomic


def storage(root):
    return home.data_root() / 'slide-edits' / hashlib.sha256(str(root).encode()).hexdigest()


def check_pending(root):
    for journal in storage(root).glob('*/PUBLISHING.txt'):
        raise WorkspaceError('An interrupted slide save needs recovery before this training can continue. '
                             f'Its original and prepared files are kept at {journal.parent}.')


class PreparedEdit:
    def __init__(self, live: Path, basis=None):
        self.live = live
        self.basis = basis
        check_pending(live)
        parent = storage(live)
        parent.mkdir(parents=True, exist_ok=True)
        self.folder = Path(tempfile.mkdtemp(prefix='edit-', dir=parent))
        self.before = self.folder / 'before'
        self.root = self.folder / 'prepared'
        self.recovery = False
        self.outputs = {}
        self.published = False

    @staticmethod
    def files(root):
        found = {}
        for path in root.rglob('*'):
            if path.is_symlink():
                raise WorkspaceError('A linked file prevents changing this deck safely.')
            if path.is_file():
                found[path.relative_to(root)] = hashlib.sha256(path.read_bytes()).digest()
        return found

    def __enter__(self):
        try:
            self.original = self.files(self.live)
            if self.basis is not None and self.original != self.basis:
                raise WorkspaceError('This training changed while the slide was being checked. Try again.')
            shutil.copytree(self.live, self.before)
            shutil.copytree(self.before, self.root)
            if self.files(self.before) != self.original:
                raise WorkspaceError('This training changed while the slide was being opened. Try again.')
            return self
        except BaseException:
            shutil.rmtree(self.folder, ignore_errors=True)
            raise

    def output_folder(self, staged):
        """Give the renderer an inactive, final location: its receipts use absolute paths."""
        folder = self.live / staged.relative_to(self.root)
        if folder.exists():
            raise WorkspaceError('The new drawing folder already exists. Try again.')
        return folder

    def seal_output(self, folder):
        self.outputs[folder] = self.files(folder)

    @staticmethod
    def same(file, digest):
        if file.is_symlink():
            return False
        if not file.exists():
            return digest is None
        return file.is_file() and hashlib.sha256(file.read_bytes()).digest() == digest

    def publish(self):
        with locked(self.live):
            return self._publish()

    def _publish(self):
        after = self.files(self.root)
        changed = [path for path, digest in after.items() if self.original.get(path) != digest]
        owned = {folder.relative_to(self.live) / path: digest
                 for folder, files in self.outputs.items() for path, digest in files.items()}
        # Check all the inputs, including files not rewritten by the edit. New unrelated
        # files are left alone. Nothing deleted by rendering the private copy is deleted
        # here; old rounds and previews remain recoverable throughout publication.
        if any(not self.same(self.live / path, digest) for path, digest in self.original.items()) \
                or any((self.live / path).exists() and owned.get(path) != after[path]
                       for path in changed if path not in self.original):
            raise WorkspaceError('This training changed while the slide was being prepared. Try again.')
        journal = self.folder / 'PUBLISHING.txt'
        journal.write_text('Training Studio slide edit\nOriginal folder: ' + str(self.live)
                           + '\nBefore: before/\nPrepared: prepared/\nChanged files:\n'
                           + '\n'.join(str(path) for path in changed)
                           + '\nRecovery: compare each changed file with before/ and prepared/. '
                           'Restore before/ only where the live bytes still equal prepared/; '
                           'preserve any other live change for manual resolution. Files missing '
                           'from before/ were added. Once consistent, remove this journal.\n', encoding='utf-8')
        written = []
        try:
            for path in changed:
                if path in owned:
                    if not self.same(self.live / path, after[path]):
                        raise WorkspaceError('The new drawing changed while the slide was being saved.')
                    continue
                if not self.same(self.live / path, self.original.get(path)):
                    raise WorkspaceError('This training changed while the slide was being saved.')
                written.append(path)
                write_atomic(self.live / path, (self.root / path).read_bytes())
        except BaseException as refusal:
            conflicts = []
            for path in reversed(written):
                try:
                    if self.same(self.live / path, self.original.get(path)):
                        continue
                    if not self.same(self.live / path, after[path]):
                        conflicts.append(path)
                    elif path in self.original:
                        write_atomic(self.live / path, (self.before / path).read_bytes())
                    else:
                        (self.live / path).unlink()
                except OSError:
                    conflicts.append(path)
            if conflicts:
                self.recovery = True
                raise WorkspaceError('The slide could not be saved completely. Later changes were '
                                     f'left alone; the original and prepared files are kept at {self.folder}.') from refusal
            self._clear_journal(journal)
            raise
        self.published = True
        self._clear_journal(journal)
        return changed

    def _clear_journal(self, journal):
        # Cleanup is fallible too. Once publication finished, its new round belongs to
        # the live deck. A failed cleanup keeps both copies and blocks further work.
        self.recovery = True
        try:
            journal.unlink()
        except OSError as refusal:
            raise WorkspaceError('The slide save could not finish its recovery record. '
                                 f'The original and prepared files are kept at {self.folder}.') from refusal
        self.recovery = False

    def __exit__(self, *unused):
        if not self.published and not self.recovery:
            for folder, files in self.outputs.items():
                for path, digest in files.items():
                    target = folder / path
                    if self.same(target, digest):
                        target.unlink(missing_ok=True)
                for path in sorted(folder.rglob('*'), reverse=True):
                    if path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
        if not self.recovery:
            shutil.rmtree(self.folder, ignore_errors=True)
