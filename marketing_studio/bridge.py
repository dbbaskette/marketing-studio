"""Compatibility entry point using each studio's existing Python interfaces.

Runs in a child interpreter: no studio modules enter Marketing Studio's process.
Workspace setup is durable, so the independent launcher can use it afterward.

    bridge.py <studio> <root>            serve the studio for Marketing Studio
    bridge.py <studio> <root> --prepare  set a missing workspace up as the shared settings
                                         say; report `connect` when the one it has differs
    bridge.py <studio> <root> --connect  join the storage the shared settings name through
                                         the studio's own join, carrying its work over

Connecting never moves or deletes the workspace a studio used before: its work is copied
into the new one with the studio's own bring-in checks, the copy is committed and shared,
and the earlier workspace is left where it was and named in the report. When the carry
fails, the studio's workspace record is put back as it was, so nothing is switched; the
carry's source is noted in the studio's data folder until it is complete, so a Connect
asked again finishes one that was interrupted.
"""
import argparse
import json
import os
import shutil
import signal
import sys
from pathlib import Path


# This entry point runs by file path, before either product package is imported.
_CORE = Path(__file__).resolve().parents[1] / 'core'
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
from studio_core.runtime import ensure_python

ensure_python(Path(__file__).resolve().parents[1])

from studio_core import workspace_setup
from studio_core.workspace_setup import configure

NAMES = {'blog': 'Blog Studio', 'training': 'Training Studio', 'presentation': 'Presentation Studio'}
NOUNS = {'blog': 'blogs', 'training': 'trainings', 'presentation': 'decks'}
# Blog Studio's kinds of work: the group, the file that marks one, and what the report calls them.
BLOG_GROUPS = (('articles', 'session.json', 'blogs'), ('sources', 'record.json', 'references'),
               ('profiles', 'record.json', 'voices'))
# Where a carry came from, kept in the studio's data folder until the carry is complete.
PENDING = 'marketing-studio-connect.json'


def prepare_blog(root):
    """Keep native private defaults so the independent launcher opens its home page."""
    import studio
    import blog_runner
    from hub_store import acquire_lock, release_lock
    studio.initialize(root)
    found = blog_runner.settings(root)
    if found['configured']:
        return
    lock = acquire_lock(studio.inside(root, '.blog-runner.lock'), wait=0)
    if lock is None:
        raise ValueError('Blog Studio is open in setup. Finish or close that page before preparing it here.')
    try:
        blog_runner.settings(root, {**found['defaults'], 'shared_before': found['shared_before']})
    finally:
        release_lock(lock)


def serve_blog(root):
    # Use the native page server and runner; only the parent-facing announcement differs.
    import management
    import blog_runner
    import studio
    from hub_store import acquire_lock, release_lock
    from start_studio import running
    data = blog_data()
    with running(data, root):
        studio.initialize(root)
        lock = acquire_lock(studio.inside(root, '.blog-runner.lock'), wait=0)
        if lock is None:
            raise ValueError('Blog Studio is already running for this workspace. Use its page.')
        runner, httpd = None, None
        try:
            runner = blog_runner.engine(root)
            httpd, url = management.server(root, shared_setup=True)
            # Blog Studio generates its own key. It travels only over the private pipe.
            print(json.dumps({'link': url}), flush=True)
            runner.start()
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if runner:
                runner.close()
            if httpd:
                active = getattr(httpd, 'active_root', None)
                if active:
                    blog_runner.engine(active).close()
                if getattr(httpd, 'team_runner_lock', None) is not None:
                    release_lock(httpd.team_runner_lock)
                httpd.server_close()
            release_lock(lock)


# --- the carry's bookkeeping -------------------------------------------------------------

def read_json(path):
    try:
        found = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def pending_source(data, current_root):
    """Where an unfinished carry into the current workspace came from, or None."""
    kept = read_json(data / PENDING)
    source = kept.get('from') if kept else None
    if not isinstance(source, str) or not source:
        return None
    source = Path(source)
    return source if source.is_dir() and source != current_root else None


def note_pending(data, source):
    data.mkdir(parents=True, exist_ok=True)
    (data / PENDING).write_text(json.dumps({'from': str(source)}), encoding='utf-8')


class Restoring:
    """Put a studio's workspace record back as it was when a switch does not complete."""

    def __init__(self, path):
        self.path = path
        try:
            self.held = path.read_bytes()
        except OSError:
            self.held = None

    def restore(self):
        if self.held is None:
            self.path.unlink(missing_ok=True)
        else:
            self.path.write_bytes(self.held)


def not_switched(identifier, before, failure):
    where = f" It still uses {before['root']}." if before else ''
    return ValueError(f'{NAMES[identifier]} was not switched: connecting did not '
                      f'finish ({failure}).{where} Nothing was moved or deleted; put the cause '
                      'right, then connect again.')


# --- Blog Studio -------------------------------------------------------------------------

def blog_data():
    return Path(os.environ.get('BLOG_STUDIO_DATA', '~/.local/share/blog-studio')).expanduser()


def blog_root(gitstate, shared):
    """The writing folder Blog Studio would open: the workspace it remembers, else the folder
    its native launcher remembers, else one set up as the shared settings say. With the
    notice of a join whose first push was refused, else None."""
    space = gitstate.current()
    if space is not None:
        return space.root, None
    previous = blog_data() / 'page.json'
    if previous.is_file():
        if previous.is_symlink():
            raise ValueError('Blog Studio page preferences must be a regular file.')
        kept = json.loads(previous.read_text()).get('workspace')
        if kept:
            root = Path(kept).expanduser()
            if not root.is_absolute():
                raise ValueError('Blog Studio needs an absolute workspace path.')
            return root, None
    made, notice = workspace_setup.set_up(gitstate, shared, 'blog')
    return made.root, notice


def remember_blog_page(root):
    """The native launcher must remember this workspace for its next launch."""
    import secrets
    data = blog_data()
    data.mkdir(parents=True, exist_ok=True)
    preferences = data / 'page.json'
    if preferences.is_symlink():
        raise ValueError('Blog Studio page preferences must be a regular file.')
    pending = data / ('.page-' + secrets.token_hex(6))
    try:
        pending.write_text(json.dumps({'workspace': str(root)}))
        os.chmod(pending, 0o600)
        os.replace(pending, preferences)
    finally:
        pending.unlink(missing_ok=True)


def blog_items(root):
    """Each blog, shared reference and voice a Blog Studio writing folder holds, by group.
    One blog's uploaded material stays on this computer and is not listed."""
    import studio
    found = {}
    for group, marker, _ in BLOG_GROUPS:
        folder = studio.inside(root, group)
        names = []
        for path in sorted(folder.glob('*/' + marker)) if folder.is_dir() else ():
            if path.parent.name.startswith('.') or path.parent.is_symlink():
                continue
            if group == 'sources':
                try:
                    record = studio.read_json(path)
                except (OSError, ValueError):
                    record = {}
                if studio.is_material(root, path.parent, record):
                    continue
            names.append(path.parent.name)
        found[group] = names
    return found


def blog_described(root):
    """A Blog Studio writing folder as Marketing Studio shows it. A plain folder, which no
    hub.json marks, has no branch."""
    import team_workspace
    space = team_workspace.space(root)
    if space is not None:
        return workspace_setup.describe(space)
    return {'root': str(root), 'repository': None, 'branch': None}


def blog_matches(found, shared):
    """Whether a writing folder is the storage the settings name. A plain folder is not
    Git, so it never is: Connect moves its work into local Git or the repository."""
    return found['branch'] is not None and workspace_setup.matches(
        found['repository'], found['branch'], shared, 'blog')


def blog_carry(root):
    return {noun: len(blog_items(root).get(group, [])) for group, _, noun in BLOG_GROUPS}


def prepare_blog_workspace(gitstate, shared):
    """What Marketing Studio shows for Blog Studio, with a missing workspace set up."""
    root, notice = blog_root(gitstate, shared)
    prepare_blog(root)
    found = blog_described(root)
    result = {'prepared': True, 'workspace': found}
    if notice:
        result['notice'] = notice
    if not blog_matches(found, shared):
        wanted = workspace_setup.target(shared, 'blog')
        result['connect'] = {'from': found, 'to': {key: wanted.get(key) for key in ('repository', 'root', 'branch')},
                             'carry': blog_carry(root)}
    return result, root


def carry_blog(source, target):
    """Copy the blogs, shared references, voices and team memory of one writing folder into
    another, commit them, and say what was carried and what was left. Or leave nothing:
    what was copied and never committed is removed again when the copy does not finish."""
    import studio
    import team_workspace
    from studio_sync import gitstate, team
    found = team_workspace.space(target)
    carried, left, created, items = {}, [], [], blog_items(source)
    try:
        with team_workspace.internal():
            for group, _, noun in BLOG_GROUPS:
                for ident in items.get(group, []):
                    origin, destination = studio.inside(source, group, ident), studio.inside(target, group, ident)
                    if destination.exists():
                        left.append({'id': ident, 'why': f'{ident} is already there.'})
                        continue
                    why = team.unacceptable(origin)
                    if why:
                        left.append({'id': ident, 'why': why})
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    team.copy_in(origin, destination)
                    created.append(destination)
                    if group == 'articles' and found.address:
                        studio.write_json(destination / 'run.json', {'schema': 1, 'driver': team.claim(found)})
                    carried.setdefault(noun, []).append(ident)
            memory = source / '.shared/memory'
            for path in sorted(memory.glob('*.json')) if memory.is_dir() else ():
                kept = target / '.shared/memory' / path.name
                if not kept.exists() and not path.is_symlink():
                    kept.parent.mkdir(parents=True, exist_ok=True)
                    studio.atomic(kept, path.read_bytes())
                    created.append(kept)
        gitstate.commit(found, f'Bring Blog Studio work in from {source}', [*carried.get('blogs', []), '.shared'])
    except BaseException:
        for path in created:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        raise
    return {noun: len(names) for noun, names in carried.items()}, left


def connect_blog(gitstate, shared):
    """Join the storage the shared settings name through Blog Studio's own join, and carry
    the blogs, references and voices of the writing folder used before into it."""
    import studio
    import team_workspace
    from hub_store import acquire_lock, release_lock
    from studio_sync import support
    root, _ = blog_root(gitstate, shared)
    before = blog_described(root)
    data = support.data_root()
    if blog_matches(before, shared):
        result = {'connected': True, 'already': True, 'workspace': before}
        source = pending_source(data, root)
        if source is not None:
            # An earlier Connect switched the workspace but did not finish carrying.
            carried, left = carry_blog(source, root)
            found = team_workspace.space(root)
            report = gitstate.sync(found) if found.address and carried else None
            result.update(carried=carried, left=left, **{'from': {'root': str(source)}},
                          shared=report['shared'] if report else None,
                          notice=report['notice'] if report else None)
        (data / PENDING).unlink(missing_ok=True)
        return result
    wanted = workspace_setup.target(shared, 'blog')
    lock = acquire_lock(studio.inside(root, '.blog-runner.lock'), wait=0)
    if lock is None:
        raise ValueError('Blog Studio is open for this writing folder. Close its page, then connect again.')
    record = Restoring(gitstate.settings_path())
    try:
        note_pending(data, root)
        try:
            if 'repository' in wanted:
                # The branch and when to share go through as the settings have them: blank
                # means the clone's own branch, and nothing is written back they did not say.
                target = team_workspace.join(wanted['repository'], wanted['branch'], wanted.get('share'))
            else:
                target = gitstate.local(Path(wanted['root']), branch=wanted['branch']).root
                with team_workspace.internal():
                    studio.initialize(target)
            carried, left = carry_blog(root, target)
            found = team_workspace.space(target)
            report = gitstate.sync(found) if found.address else None
        except BaseException as failure:
            record.restore()
            (data / PENDING).unlink(missing_ok=True)
            if isinstance(failure, Exception):
                raise not_switched('blog', before, failure) from failure
            raise
        remember_blog_page(target)
        (data / PENDING).unlink(missing_ok=True)
    finally:
        release_lock(lock)
    return {'connected': True, 'from': before, 'to': blog_described(target), 'carried': carried,
            'left': left, 'shared': report['shared'] if report else None,
            'notice': report['notice'] if report else None}


# --- Training Studio and Presentation Studio ---------------------------------------------

def runner_marker(identifier):
    return '.training-studio/run.json' if identifier == 'training' else 'run.json'


def runner_items(root, identifier):
    """Every training or deck a run record marks in a workspace's folder."""
    marker, depth = runner_marker(identifier), 2 if identifier == 'training' else 1
    found = []
    for path in sorted(Path(root).glob('*/' + marker)):
        top = path.parents[depth - 1]
        if not top.name.startswith('.') and not top.is_symlink():
            found.append(top)
    return found


def runner_carry(identifier):
    return lambda space: {NOUNS[identifier]: len(runner_items(space.root, identifier))}


def carry_runner(identifier, source, new):
    """Copy the trainings or decks of one workspace folder into another, each as its
    bring-in takes it: a copy, taken by this computer, committed. Or leave nothing."""
    from runner import gitstate, team
    import home
    marker = runner_marker(identifier)
    carried, left, created = [], [], []
    try:
        for top in runner_items(source, identifier) if source else ():
            ident, destination = top.name, new.root / top.name
            if destination.exists():
                left.append({'id': ident, 'why': f'{new.folder}/{ident} is already there.'})
                continue
            why = team.unacceptable(top)
            if why:
                left.append({'id': ident, 'why': why})
                continue
            team.copy_in(top, destination)
            created.append(destination)
            record = home.read_json(destination / marker, None)
            if not isinstance(record, dict):
                left.append({'id': ident, 'why': 'Its run record cannot be read.'})
                shutil.rmtree(destination, ignore_errors=True)
                created.remove(destination)
                continue
            home.write_json(destination / marker, {**record, 'driver': team.claim(new)})
            carried.append(ident)
        if carried:
            gitstate.commit(new, f'Bring {NOUNS[identifier]} in from {source}', carried)
    except BaseException:
        for destination in created:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    return {NOUNS[identifier]: len(carried)}, left


def connect_runner(identifier, shared):
    """Join the storage the shared settings name through the runner's own join, and carry
    the trainings or decks of the workspace used before into it."""
    from runner import gitstate, setup, studio
    import home
    current, data = gitstate.current(), home.data_root()
    if current is not None and workspace_setup.matches(current.address, current.branch, shared, identifier):
        result = {'connected': True, 'already': True, 'workspace': workspace_setup.describe(current)}
        source = pending_source(data, current.root)
        if source is not None:
            # An earlier Connect switched the workspace but did not finish carrying.
            with studio.only_runner():
                carried, left = carry_runner(identifier, source, current)
                report = gitstate.sync(current) if current.address and carried[NOUNS[identifier]] else None
            result.update(carried=carried, left=left, **{'from': {'root': str(source)}},
                          shared=report['shared'] if report else None,
                          notice=report['notice'] if report else None)
        (data / PENDING).unlink(missing_ok=True)
        return result
    wanted = workspace_setup.target(shared, identifier)
    before = workspace_setup.describe(current) if current else None
    with studio.only_runner():
        setup.migrate()
        record = Restoring(gitstate.settings_path())
        if current is not None:
            note_pending(data, current.root)
        try:
            if 'repository' in wanted:
                new = gitstate.join(wanted['repository'], branch=wanted['branch'], share=wanted.get('share'))
            else:
                new = gitstate.local(Path(wanted['root']), branch=wanted['branch'])
            carried, left = carry_runner(identifier, current.root if current else None, new)
            report = gitstate.sync(new) if new.address else None
        except BaseException as failure:
            record.restore()
            (data / PENDING).unlink(missing_ok=True)
            if isinstance(failure, Exception):
                raise not_switched(identifier, before, failure) from failure
            raise
        (data / PENDING).unlink(missing_ok=True)
    return {'connected': True, 'from': before, 'to': workspace_setup.describe(new), 'carried': carried,
            'left': left, 'shared': report['shared'] if report else None,
            'notice': report['notice'] if report else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('studio', choices=('blog', 'presentation', 'training'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--connect', action='store_true')
    # Names the Marketing Studio data root that started this bridge; read only from outside.
    parser.add_argument('--home-data', help=argparse.SUPPRESS)
    args = parser.parse_args()
    handoff = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF'))
    shared = handoff['shared']
    if args.studio == 'blog':
        scripts = args.root / 'skills/blog-studio/scripts'
        sys.path.insert(0, str(scripts if scripts.is_dir() else args.root / 'scripts'))
        from studio_sync import gitstate
        if args.connect:
            print(json.dumps(connect_blog(gitstate, shared)), flush=True)
            return 0
        result, root = prepare_blog_workspace(gitstate, shared)
        if args.prepare:
            print(json.dumps(result), flush=True)
            return 0
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        return serve_blog(root) or 0
    sys.path.insert(0, str(args.root))
    from runner import gitstate, setup, studio
    if args.connect:
        print(json.dumps(connect_runner(args.studio, shared)), flush=True)
        return 0
    if args.prepare and gitstate.current() is not None:
        print(json.dumps(workspace_setup.prepare(gitstate, shared, args.studio,
                                                 runner_carry(args.studio))), flush=True)
        return 0
    # The native startup takes its singleton lock before serving. Setup needs the same
    # lease, so a launch cannot change an already-running studio's workspace.
    with studio.only_runner():
        setup.migrate()
        if args.prepare:
            print(json.dumps(workspace_setup.prepare(gitstate, shared, args.studio,
                                                     runner_carry(args.studio))), flush=True)
            return 0
        configure(gitstate, shared, args.studio)
    os.environ[studio.RESTART] = json.dumps({'token': handoff['token']})
    return studio.main(['serve'])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as failure:
        print(json.dumps({'error': str(failure)}), flush=True)
        raise SystemExit(2)
