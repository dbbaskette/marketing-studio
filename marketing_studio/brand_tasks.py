"""The one background task a working copy runs at a time (Extract or the assistant's
job), and Extract itself. marketing_studio.brand_store re-exports every name here."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time

from . import brand_skill
from .errors import WorkspaceError

from .brand_files import files_in, read_json
from .brand_terms import LIBRARIES, LINES, PREVIEW_HELP, VARIANT
from .brand_work import (
    LINE_WRITES, LIVE, TASKS, _read, folder_of, idle, inside, keep, record)


def _store():
    """marketing_studio.brand_store, read when called. Callers and tests replace names on it
    (LOCK, git, walk, write_json and others), and a call made here reaches what they put there."""
    from . import brand_store
    return brand_store


def begin(key: str, kind: str, job, part=None) -> dict:
    """Run `job(line, stop)` in the background as this working copy's one task."""
    with _store().LOCK:
        work = record(key)
        idle(key)
        stop = threading.Event()
        work['task'] = {'kind': kind, 'part': part, 'state': 'running', 'lines': [],
                        'detail': '', 'started': time.time(), 'ended': None}
        live = LIVE[key] = {'lines': [], 'kept': _store()._clock(), 'waiting': False}
        keep(work)

        def line(text):
            # Held in memory, where record() shows it at once, and written to work.json at
            # most every LINE_WRITES seconds: no walk of the working copy for a line.
            text = ' '.join(str(text).split())[:300]
            if not text:
                return
            with _store().LOCK:
                if LIVE.get(key) is not live:
                    return   # discarded meanwhile
                lines = live['lines']
                if not lines or lines[-1] != text:
                    lines.append(text)
                    del lines[:-LINES]
                    live['waiting'] = True
                if live['waiting'] and _store()._clock() - live['kept'] >= LINE_WRITES:
                    try:
                        keep(_read(key))
                    except WorkspaceError:
                        return

        def run():
            # Anything that ends the job, even SystemExit, still writes how it ended.
            ending, detail = 'failed', 'It ended unexpectedly, so nothing was kept from it. Run it again.'
            try:
                try:
                    job(line, stop)
                    ending, detail = 'done', ''
                except brand_skill.Stopped:
                    ending, detail = 'stopped', 'It was stopped before it finished, so nothing was kept from it.'
                except WorkspaceError as failure:
                    ending, detail = 'failed', str(failure)
                except Exception as failure:   # reported to the person, never lost
                    ending, detail = 'failed', f'{type(failure).__name__}: {failure}'
            finally:
                if stop.is_set() and ending == 'done':
                    ending, detail = 'stopped', 'It was stopped before it finished, so nothing was kept from it.'
                with _store().LOCK:
                    try:
                        # Every line is in it, as it was read while the task still ran.
                        current = _read(key)
                        if LIVE.get(key) is live and isinstance(current.get('task'), dict):
                            current['task'].update(state=ending, detail=detail, ended=time.time())
                            keep(current)
                    except (WorkspaceError, OSError):
                        pass   # discarded meanwhile
                    finally:
                        if LIVE.get(key) is live:
                            del LIVE[key]
                        if TASKS.get(key) is entry:
                            del TASKS[key]

        thread = threading.Thread(target=run, daemon=True, name=f'brands-{key}')
        entry = TASKS[key] = (thread, stop)
        thread.start()
        return work


def stop(key: str) -> None:
    running = TASKS.get(key)
    if running and running[0].is_alive():
        running[1].set()


def wait(key: str, seconds: float = 30) -> None:
    """For tests and for Save: until this working copy's task has ended."""
    running = TASKS.get(key)
    if running:
        running[0].join(seconds)



def guess_variant(name: str) -> str:
    return 'dark' if 'dark' in name.lower() else 'light'


def extract_brand(found, key: str, tokens=None, templates=(), icons=()):
    """The job that runs Harness Brand's pack commands into a copy of the working pack and
    puts it in place only when every command has finished."""
    work = record(key)
    if work['kind'] != 'brand':
        raise WorkspaceError('That is an icon library: extract it as one.')
    here = inside(work)
    sources = here / 'sources'
    names = {item['name'] for item in files_in(sources)}
    if tokens is not None and tokens not in names:
        raise WorkspaceError('Choose the design-system export from the sources.')
    variants = []
    for item in templates:
        if not isinstance(item, dict) or item.get('source') not in names \
                or not str(item.get('source')).lower().endswith('.pptx'):
            raise WorkspaceError('Choose each template from the sources: a PowerPoint (.pptx) file.')
        if not isinstance(item.get('variant'), str) or not VARIANT.match(item['variant']):
            raise WorkspaceError('Name each variant in lower-case letters, digits and hyphens, '
                                 'starting with a letter, such as light or dark.')
        variants.append(item['variant'])
    if len(set(variants)) != len(variants):
        raise WorkspaceError('Give each template a variant of its own.')
    shelf = folder_of(key) / 'brands' / LIBRARIES
    for library in icons:
        if not isinstance(library, str) or not (shelf / library / 'library.zip').is_file():
            raise WorkspaceError(f'There is no icon library {library} to use.')
    pack = here / 'pack'
    if tokens is None and not (pack / 'tokens.json').is_file():
        raise WorkspaceError('Choose the design-system export: a pack is drafted from its tokens.')

    def job(line, stop):
        trial = folder_of(key) / 'brands' / work['id'] / '.pack-extracting'
        shutil.rmtree(trial, ignore_errors=True)
        shutil.copytree(pack, trial)
        outcome = {'tokens': tokens, 'templates': list(templates), 'icons': list(icons),
                   'previews': {}, 'draft': []}
        try:
            def command(*args):
                code, said = brand_skill.answer(found, list(args), env=brand_skill.environment(folder_of(key) / 'brands'), stop=stop, seconds=900)
                if code != 0:
                    raise WorkspaceError(brand_skill.said(json.dumps(said), code))
                return said
            if tokens is not None:
                line(f'Reading the tokens in {tokens}')
                made = command('pack', 'tokens', str(sources / tokens), '--into', str(trial),
                               '--replace', '--json')
                line(f"Found {made.get('colors')} colours ({made.get('dark')} with a dark value) and "
                     f"{made.get('styles')} type styles")
            for item in templates:
                line(f"Measuring {item['source']} as {item['variant']}")
                made = command('pack', 'measure', str(sources / item['source']), '--variant',
                               item['variant'], '--into', str(trial), '--replace', '--json')
                line(f"Measured {made.get('measured')} layouts, {made.get('used')} with an example slide")
            measured = read_json(trial / 'layouts.json', {}) or {}
            for variant in (measured.get('variants') or {}):
                line(f'Drawing the {variant} previews')
                try:
                    made = command('pack', 'previews', str(trial), '--variant', variant, '--json')
                    line(f"Drew {made.get('drawn')} previews for {variant}")
                    outcome['previews'][variant] = None
                except WorkspaceError as failure:
                    outcome['previews'][variant] = f'{failure} {PREVIEW_HELP}'
                    line(f'No previews for {variant}: {failure}')
            if not (trial / 'brand.json').is_file():
                line('Drafting brand.json, guide.md, the directions and the audit limits')
                args = ['pack', 'scaffold', str(trial), '--id', work['id'], '--name', work['name'],
                        '--json']
                if icons:
                    args[-1:-1] = ['--icons', ','.join(icons)]
                made = command(*args)
                outcome['draft'] = [str(each) for each in made.get('draft') or []]
            if stop.is_set():
                raise brand_skill.Stopped()
            with _store().LOCK:
                shutil.rmtree(pack)
                os.replace(trial, pack)
                current = record(key)
                current['extracted'] = {**outcome, 'at': time.time()}
                keep(current)
            line('Extracted. Review what came out below.')
        finally:
            shutil.rmtree(trial, ignore_errors=True)
    return job


def extract_library(found, key: str):
    work = record(key)
    if work['kind'] != 'library':
        raise WorkspaceError('That is a brand: extract it as one.')
    here = inside(work)
    sources = sorted(path for path in (here / 'sources').iterdir()
                     if not path.name.startswith('.')) if (here / 'sources').is_dir() else []
    if not sources:
        raise WorkspaceError('Add the icons first: SVG files, an icons.json or a ZIP archive of them.')

    def job(line, stop):
        trial = folder_of(key) / 'trial' / work['id']
        shutil.rmtree(trial.parent, ignore_errors=True)
        trial.mkdir(parents=True)
        try:
            line(f"Making the {work['name']} library from {len(sources)} source{'s' if len(sources) != 1 else ''}")
            code, made = brand_skill.answer(
                found, ['pack', 'icons', *map(str, sources), '--library', work['id'], '--name',
                        work['name'], '--kind', work['libraryKind'], '--into', str(trial),
                        '--replace', '--json'], stop=stop, seconds=900)
            if code != 0 or not isinstance(made, dict):
                raise WorkspaceError('pack icons did not make the library.')
            line(f"Made {made.get('icons')} {made.get('kind')} icons; left out {len(made.get('skipped') or [])}")
            if stop.is_set():
                raise brand_skill.Stopped()
            with _store().LOCK:
                for name in ('library.zip', 'contact-sheet.svg'):
                    if (trial / name).is_file():
                        os.replace(trial / name, here / name)
                current = record(key)
                current['extracted'] = {'icons': made.get('icons'), 'kind': made.get('kind'),
                                        'sources': made.get('sources') or [],
                                        'skipped': made.get('skipped') or [], 'at': time.time()}
                keep(current)
        finally:
            shutil.rmtree(trial.parent, ignore_errors=True)
    return job
