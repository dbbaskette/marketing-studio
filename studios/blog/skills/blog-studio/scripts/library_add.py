"""Add to library: files, a list of links and a Google Doc, in one sheet, with their role,
author and kind of post.

Files and a Google Doc are saved the way an upload is; links go through the library's own
`urls` import, one collection per site, with the fetch, scope check and size limits it
already has. The author is one typed name, none, or each post's own: then every post is
imported first, since a byline is known only once a page is fetched, and the results are
grouped by author afterwards for the person to rename, merge or complete. A post with no
byline, an organisation byline or several bylines is held and counted for nobody.
"""

import re

import blog_library
import management
import studio
import voice_links
from hub_store import HubError, encoded, sha

EACH = '*each'
FIELDS = {'operation', 'files', 'links', 'role', 'author', 'kind', 'expected'}
NO_ROLE = 'Choose facts or an example of the kind of post for these items.'


def ledger_path(root, operation):
    if not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9]{32}', operation):
        raise ValueError('An add-to-library operation ID is required.')
    directory = blog_library.folder(root) / 'adds'
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory / (operation + '.json')


def checked(root, data):
    """The request's role, author mode, kind and items, validated. Reads files and the
    Google Doc; reaches no other network."""
    if set(data) - FIELDS:
        raise ValueError('Unknown add-to-library field.')
    role = data.get('role')
    if role not in ('facts', 'example'):
        raise ValueError(NO_ROLE)
    author = data.get('author') or ''
    if author != EACH:
        author = studio.checked_author(author) if author else ''
    kind = data.get('kind') or ''
    fields = blog_library.library_fields(root, kind=kind or None)
    files = data.get('files') or []
    if not isinstance(files, list) or len(files) > management.MAX_UPLOAD_FILES:
        raise ValueError('Add at most %d files at once.' % management.MAX_UPLOAD_FILES)
    links = data.get('links') or ''
    if not isinstance(links, str):
        raise ValueError('Paste links or choose a text file with one link per line.')
    if not files and not links.strip():
        raise ValueError('Choose files, paste links or add a Google Doc link first.')
    entries = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError('Give each file a name and its content.')
        found = (management.checked_google if 'google' in entry else management.checked_upload)(
            root, entry
        )
        names = (
            voice_links.bylines(found['content']) if found['suffix'] in ('.html', '.htm') else []
        )
        found['bylines'] = names
        found['origin_kind'] = 'google-doc' if found.get('link') else 'upload'
        entries.append(found)
    if len({entry['filename'] for entry in entries}) != len(entries):
        raise ValueError('Add each file once.')
    sites = []
    parsed = None
    if links.strip():
        parsed = voice_links.parse(links)
        for site in parsed['sites']:
            chosen = voice_links.parse(links, site['site'])
            sites.append({**site, 'links': chosen['links']})
    return {
        'role': role,
        'author': author,
        'kind': kind,
        'kind_name': _kind_name(root, kind),
        'purposes': ['reference'] + (['inspiration'] if role == 'example' else []),
        'fields': fields,
        'entries': entries,
        'parsed': parsed,
        'sites': sites,
        'expected': sha(
            encoded(
                [
                    role,
                    author,
                    kind,
                    [
                        [entry['filename'], entry.get('link') or sha(entry['content'])]
                        for entry in entries
                    ],
                    [[site['site'], site['links']] for site in sites],
                ]
            )
        ),
    }


def _kind_name(root, kind):
    import styles

    return styles.name_of(root, kind) if kind else None


def preview(root, data):
    """What adding these items would do. Saves nothing; reads the files and the Doc."""
    found = checked(root, data)
    known = voice_links.library_rows(root)
    items = [
        {
            'key': entry['filename'],
            'kind': 'google-doc' if entry.get('link') else 'file',
            'title': entry['title'],
            'filename': entry.get('shown', entry['filename']),
            'link': entry.get('link'),
            'state': entry['status'],
            'chars': len(entry['text']) if entry['text'] else 0,
            'note': entry['note'],
            'bylines': entry['bylines'],
        }
        for entry in found['entries']
    ]
    for site in found['sites']:
        for link in site['links']:
            row = known.get(link)
            items.append(
                {
                    'key': link,
                    'kind': 'link',
                    'title': row['record'].get('name') if row else None,
                    'url': link,
                    'site': site['shown'],
                    'state': 'in-library' if row else 'new',
                    'chars': None,
                    'bylines': [row['record']['author']]
                    if row and row['record'].get('author')
                    else [],
                    'note': 'Already in the library; reused, not fetched again.'
                    if row
                    else 'Fetched once from ' + site['shown'] + '; its byline is read then.',
                }
            )
    parsed = found['parsed'] or {}
    return {
        'status': 'ready',
        'role': found['role'],
        'author': found['author'],
        'kind': found['kind'],
        'kind_name': found['kind_name'],
        'items': items,
        'sites': [
            {key: site[key] for key in ('site', 'scope', 'shown')} | {'links': len(site['links'])}
            for site in found['sites']
        ],
        'in_library': sum(item['state'] == 'in-library' for item in items),
        'to_fetch': sum(item['state'] == 'new' for item in items),
        **{
            key: parsed.get(key, 0 if key != 'skipped' else [])
            for key in ('duplicates', 'comments', 'upgraded', 'unusable', 'skipped')
        },
        'expected': found['expected'],
        'next_step': 'Check the items, their role, author and kind of post, then add them. '
        'Files and the Doc are saved now; each new link is fetched once and saved in the library.',
    }


def publish(root, ident, problems):
    """Publish one changed library item to the selected Team Hub without syncing: an
    operation's status() syncs once at the end, as a list of links import does, so a group
    of twenty is one fetch and push, not twenty. A refusal is noted, never raised."""
    from hub_workspace import active

    adapter = active(root)
    if adapter is None:
        return
    try:
        adapter._publish('sources', ident)
    except (HubError, OSError, ValueError) as exc:
        problems[ident] = str(exc)[:400]


def _collection_name(root, shown):
    return blog_library.unique_name(root, 'Links from ' + shown)


def add(root, data):
    """Add the checked items, or continue adding them. Files and the Doc are saved on the
    first call; each call then fetches at most one library batch of links. The same
    operation with the same request continues; a changed request is refused."""
    found = checked(root, data)
    if data.get('expected') != found['expected']:
        raise ValueError(
            'These items or your library changed since the check. Check them again before adding.'
        )
    path = ledger_path(root, data.get('operation'))
    fingerprint = found['expected']
    if path.exists():
        state = studio.read_json(path)
        if state['fingerprint'] != fingerprint:
            raise ValueError('This operation belongs to a different add-to-library request.')
    else:
        state = {
            'schema': 1,
            'fingerprint': fingerprint,
            'role': found['role'],
            'author': found['author'],
            'kind': found['kind'],
            'files': {},
            'sites': {},
            'created_at': studio.now(),
        }
        studio.write_json(path, state)
    staging = studio.inside(root, '.uploads')
    staging.mkdir(mode=0o700, exist_ok=True)
    from hub_workspace import active

    adapter = active(root)
    changed, problems = [], {}
    for entry in found['entries']:
        if entry['filename'] in state['files']:
            continue
        whose = _author_for(found['author'], entry['bylines'])
        fields = {**found['fields'], 'origin_kind': entry['origin_kind']}
        source = management.save_upload(
            root, staging, entry, found['purposes'], whose, analyze=False, library=fields
        )
        changed.append(source['id'])
        publish(root, source['id'], problems)
        state['files'][entry['filename']] = {
            'id': source['id'],
            'kind': 'google-doc' if entry.get('link') else 'file',
            'shown': entry.get('shown', entry['filename']),
            'link': entry.get('link'),
        }
        studio.write_json(path, state)
    known = voice_links.library_rows(root)
    budget = blog_library.MAX_BATCH
    for site in found['sites']:
        saved = state['sites'].get(site['site'])
        if saved is None:
            reused, fresh = {}, []
            for link in site['links']:
                row = known.get(link)
                if row:
                    ident = adapter._checkout(row['id']) if row['location'] == 'hub' else row['id']
                    reused[link] = ident
                    if _adopt(root, ident, found):
                        changed.append(ident)
                        publish(root, ident, problems)
                else:
                    fresh.append(link)
            manifest = None
            if fresh:
                draft = blog_library.normalize(
                    root,
                    {
                        'key': 'library-links-' + sha(encoded([path.stem, site['site']]))[:16],
                        'name': _collection_name(root, site['shown']),
                        'type': 'urls',
                        'scope': site['scope'],
                        'urls': fresh,
                    },
                )
                manifest = blog_library.preview(root, draft['key'], config=draft)
            saved = {
                'scope': site['scope'],
                'shown': site['shown'],
                'links': site['links'],
                'reused': reused,
                'preview': manifest['preview'] if manifest else None,
            }
            state['sites'][site['site']] = saved
            studio.write_json(path, state)
        if saved['preview'] and budget > 0:
            manifest = studio.read_json(blog_library.folder(root) / (saved['preview'] + '.json'))
            wanted = [
                entry['identity']
                for entry in manifest['candidates']
                if entry['identity'] not in manifest['results']
            ][:budget]
            if wanted:
                blog_library.import_batch(
                    root,
                    saved['preview'],
                    limit=blog_library.MAX_BATCH,
                    reader=blog_library.fetch,
                    selected=wanted,
                    analyze=False,
                    origin_kind='link',
                    defaults={
                        'purposes': found['purposes'],
                        'author': found['author'],
                        'kind': found['kind'],
                    },
                )
                budget -= len(wanted)
    return status(root, path.stem, changed=changed, problems=problems)


def _author_for(mode, bylines):
    """The author a new item gets: the typed name, or in each-post mode its one byline."""
    if mode == EACH:
        return bylines[0] if len(bylines) == 1 else None
    return mode or None


def _adopt(root, ident, found):
    """A post already in the library takes this request's role, kind and typed author in a
    new revision, when any of them is new to it. True when it changed."""
    directory, record = studio.item(root, 'sources', ident)
    purposes = list(record.get('purposes') or [])
    purposes += [p for p in found['purposes'] if p not in purposes]
    metadata = {**(record.get('library') or {}), **found['fields']}
    author = record.get('author')
    if found['author'] not in ('', EACH) and not author:
        author = found['author']
    if (purposes, metadata, author) == (
        record.get('purposes'),
        record.get('library'),
        record.get('author'),
    ):
        return False
    blog_library.save_revision(directory, record)
    record.update(
        purposes=purposes, library=metadata, author=author, revision=record['revision'] + 1
    )
    studio.persist(directory, 'sources', record)
    return True


def _rows(root, state):
    """Every item of an operation as it is now: files first, then links by site."""
    rows = []
    for filename, saved in state['files'].items():
        rows.append(
            {
                'id': saved['id'],
                'kind': saved['kind'],
                'filename': saved.get('shown', filename),
                'link': saved.get('link'),
                'status': 'imported',
            }
        )
    for site in state['sites'].values():
        manifest = (
            studio.read_json(blog_library.folder(root) / (site['preview'] + '.json'))
            if site['preview']
            else {'results': {}}
        )
        for link in site['links']:
            row = {'kind': 'link', 'url': link, 'site': site['shown'], 'status': 'pending'}
            if link in site['reused']:
                row.update(id=site['reused'][link], status='in-library')
            else:
                saved = manifest['results'].get(link)
                if saved and saved['status'] == 'failed':
                    reason = saved.get('reason') or 'Not read.'
                    if reason == blog_library.OUT_OF_SCOPE:
                        reason = (
                            'This page has moved outside '
                            + site['shown']
                            + '; use its new address.'
                        )
                    row.update(status='failed', reason=reason)
                elif saved:
                    row.update(id=saved['id'], status='imported')
            rows.append(row)
    for row in rows:
        if row.get('id'):
            try:
                _, record = studio.item(root, 'sources', row['id'])
            except ValueError:
                row.update(status='failed', reason='This item is no longer in the library.')
                continue
            metadata = record.get('library') or {}
            row.update(
                title=record.get('name'),
                author=record.get('author') or None,
                bylines=metadata.get('bylines', []),
                role=blog_library.role_of(record),
                sample='voice-sample' in record.get('purposes', []),
                revision=record['revision'],
                text=record.get('status') == 'ready',
            )
    return rows


def groups_of(rows):
    """The saved items by author, variants folded with same_author; held items apart."""
    groups, held = [], []
    for row in rows:
        if not row.get('id') or row.get('status') == 'failed':
            continue
        if not row.get('author'):
            names = row.get('bylines') or []
            held.append(
                {
                    'id': row['id'],
                    'title': row.get('title'),
                    'url': row.get('url'),
                    'bylines': names,
                    'reason': 'Several bylines: ' + ', '.join(names)
                    if len(names) > 1
                    else 'No byline on the page.'
                    if row['kind'] == 'link'
                    else 'No author.',
                }
            )
            continue
        group = next(
            (g for g in groups if voice_links.same_author(row['author'], g['author'])), None
        )
        if group is None:
            group = {'author': row['author'], 'ids': [], 'samples': [], 'learnable': []}
            groups.append(group)
        group['ids'].append(row['id'])
        if row.get('sample') and row.get('text'):
            group['samples'].append(row['id'])
    for group in groups:
        group['count'] = len(group['ids'])
        group['learnable'] = group['samples'][:10]
    groups.sort(key=lambda g: (-g['count'], g['author'].casefold()))
    return groups, held


def status(root, operation, sync=True, changed=(), problems=None):
    """Where an add-to-library operation stands: every item, the authors and what is next.
    With a Team Hub selected it syncs once, for everything this request published, unless
    links are still to come or `sync` is False (a read before changes)."""
    path = ledger_path(root, operation)
    if not path.is_file():
        raise ValueError('This add-to-library operation is not known here. Check the items again.')
    state = studio.read_json(path)
    rows = _rows(root, state)
    groups, held = groups_of(rows)
    counts = {
        name: sum(r['status'] == name for r in rows)
        for name in ('imported', 'in-library', 'failed', 'pending')
    }
    counts['samples'] = sum(bool(r.get('sample')) for r in rows)
    words = []
    if counts['pending']:
        words.append(
            '%d links are still to add; continue to fetch the next batch.' % counts['pending']
        )
    if held:
        words.append(
            '%d posts have no single byline; say whose they are, or leave them as references.'
            % len(held)
        )
    if groups and state['author'] == EACH and not counts['samples']:
        words.append(
            'Mark the posts as voice samples by their authors, then learn a voice from any group.'
        )
    elif any(g['learnable'] for g in groups):
        words.append(
            'Learn a voice from a group: choose up to ten samples, then confirm they may be analyzed.'
        )
    if counts['failed']:
        words.append('Failed links can be tried again by checking the list again.')
    result = {
        'operation': operation,
        'state': 'importing' if counts['pending'] else 'saved',
        'role': state['role'],
        'author': state['author'],
        'kind': state['kind'],
        'kind_name': _kind_name(root, state['kind']),
        'items': rows,
        'counts': counts,
        'remaining': counts['pending'],
        'groups': groups,
        'held': held,
        'changed': list(changed),
        'next_step': ' '.join(words) or 'Every item is in the library.',
    }
    if problems:
        result['sharing_problems'] = problems
    from hub_workspace import active

    adapter = active(root)
    if sync and adapter and not counts['pending']:
        try:
            result['hub_sync'] = adapter.hub.sync()
        except (HubError, OSError):
            result['hub_sync'] = {'status': 'local-saved-not-shared'}
    sync = result.get('hub_sync', {'status': 'local-only'})
    result['sharing'] = sync.get('status', 'local-saved-not-shared')
    result['sharing_message'] = management.SHARING_MESSAGES.get(
        result['sharing'], 'Saved locally; Hub sync needs attention. Retry Hub sync in chat.'
    )
    return result


def _mine(root, operation, ids):
    """The ids among this operation's saved items, in the order given."""
    state = studio.read_json(ledger_path(root, operation))
    known = {row['id'] for row in _rows(root, state) if row.get('id')}
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(v, str) or v not in known for v in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError('Choose items this add-to-library operation saved.')
    return ids


def set_author(root, data):
    """Rename a group, merge one into another, or say whose a held post is: the named items
    take the author in a new revision. The library entry keeps its published byline."""
    if set(data) != {'operation', 'ids', 'author'}:
        raise ValueError('Name the items and their author.')
    author = studio.checked_author(data.get('author'))
    changed, problems = [], {}
    for ident in _mine(root, data['operation'], data.get('ids')):
        directory, record = studio.item(root, 'sources', ident)
        if record.get('author') == author:
            continue
        blog_library.save_revision(directory, record)
        record.update(author=author, revision=record['revision'] + 1)
        studio.persist(directory, 'sources', record)
        changed.append(ident)
        publish(root, ident, problems)
    return status(root, data['operation'], changed=changed, problems=problems)


def mark_samples(root, data):
    """voice-sample on every post in each named group, through source-purpose: a new source
    revision that stales no run which pinned the source. `authors` limits it to some groups."""
    from advanced_tools import source_purpose

    if set(data) - {'operation', 'authors'}:
        raise ValueError('Unknown sample field.')
    current = status(root, data['operation'], sync=False)
    wanted = data.get('authors')
    if wanted is not None and (
        not isinstance(wanted, list) or any(not isinstance(v, str) for v in wanted)
    ):
        raise ValueError('Name the author groups to mark.')
    changed, problems = [], {}
    for group in current['groups']:
        if wanted is not None and group['author'] not in wanted:
            continue
        for ident in group['ids']:
            try:
                result = source_purpose(
                    root,
                    {
                        'action': 'source-purpose',
                        'source': ident,
                        'purpose': 'voice-sample',
                        'author': group['author'],
                    },
                )
            except ValueError:
                continue  # A post without text cannot be a sample; it stays a reference.
            if result['changed']:
                changed.append(ident)
                publish(root, ident, problems)
    return status(root, data['operation'], changed=changed, problems=problems)


SELECTION_ACTIONS = ('style-learn', 'voice-learn', 'blog')


LEARN_LIMIT = 10  # What a learn sheet takes, and a learning job reads.


def selection(root, data):
    """The library screen's three actions on a selection. Nothing is saved, marked or shared
    here, and nothing starts a job (a Team Hub row is checked out to be read, as a library
    import does). style-learn and voice-learn return the readable items as candidates for
    the learn sheet, the first ten, naming those left out and those without text; the
    purposes are added only when the learning job is confirmed. voice-learn needs whose
    writing it is: the items' own author when every item names the same one, else an
    explicit author; one item's author is never given to another. blog returns the items
    as the files of a new blog, each an example, for the page to tick."""
    if set(data) - {'action', 'ids', 'author'} or data.get('action') not in SELECTION_ACTIONS:
        raise ValueError('Choose a library action: learn a style, learn a voice, or start a blog.')
    entries = data.get('ids')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
        raise ValueError('Select one to fifty library items.')
    ids = []
    for entry in entries:
        # A local item by its ID, or {id, location} for a row the catalog lists from the Hub.
        if isinstance(entry, dict) and set(entry) - {'location'} == {'id'}:
            ids.append(blog_library.local_item(root, entry['id'], entry.get('location', 'local')))
        elif isinstance(entry, str):
            ids.append(blog_library.local_item(root, entry))
        else:
            raise ValueError('Choose a local or shared library item.')
    if len(set(ids)) != len(ids):
        raise ValueError('Select one to fifty library items.')
    rows = []
    for ident in ids:
        directory, record = studio.item(root, 'sources', ident)
        if studio.is_material(root, directory, record):
            raise ValueError('A file uploaded for one blog is not a library item.')
        rows.append((directory, record))
    action = data['action']
    if action == 'blog':
        files = []
        for directory, record in rows:
            content = directory / 'content.md'
            text = content.read_text() if content.is_file() else ''
            files.append(
                {
                    'id': record['id'],
                    'filename': record['name'],
                    'state': 'ready'
                    if record.get('status') == 'ready' and text.strip()
                    else 'pending',
                    'chars': len(text),
                    'role': 'inspiration',
                    'library': True,
                }
            )
        return {'action': action, 'files': files}
    readable, skipped = [], []
    for directory, record in rows:
        content = directory / 'content.md'
        if record.get('status') == 'ready' and content.is_file() and content.read_text().strip():
            readable.append(record)
        else:
            skipped.append(
                {
                    'id': record['id'],
                    'name': record['name'],
                    'reason': 'It has no readable text yet.',
                }
            )
    if not readable:
        raise ValueError('None of these items has readable text to learn from yet.')
    chosen, left_out = readable[:LEARN_LIMIT], readable[LEARN_LIMIT:]
    author = data.get('author')
    if action == 'voice-learn':
        named = [record['author'] for record in chosen if record.get('author')]
        if author:
            author = studio.checked_author(author)
        elif named and len(named) == len(chosen):
            author = named[0]
        else:
            raise ValueError('Say whose writing these items are before learning a voice.')
        if any(not voice_links.same_author(name, author) for name in named):
            raise ValueError(
                'These items are by more than one author. Select posts by one author, or '
                'learn a style from them instead.'
            )
    return {
        'action': action,
        'candidates': [
            {'id': r['id'], 'name': r['name'], 'author': r.get('author') or ''} for r in chosen
        ],
        'author': author if action == 'voice-learn' else None,
        'left_out': [{'id': r['id'], 'name': r['name']} for r in left_out],
        'skipped': skipped,
    }


def mark_for_learning(root, data):
    """At a confirmed learning job, the chosen items that are not samples yet become samples,
    each in a new source revision through source-purpose; a voice sample takes the voice's
    name only when the item names no author. Every item is checked first, so a refusal marks
    nothing; the Team Hub then syncs once."""
    from advanced_tools import source_purpose

    purpose = 'voice-sample' if data['kind'] == 'voice-learn' else 'style-sample'
    samples, name = data.get('samples'), data.get('name')
    if (
        not isinstance(samples, list)
        or not 1 <= len(samples) <= LEARN_LIMIT
        or any(not isinstance(v, str) for v in samples)
        or len(set(samples)) != len(samples)
    ):
        return []  # The learning job refuses the list itself, with its own words.
    wanted = []
    for ident in samples:
        directory, record = studio.item(root, 'sources', ident)
        if purpose in record.get('purposes', []):
            continue
        if studio.is_material(root, directory, record):
            raise ValueError('A file uploaded for one blog is not a library item.')
        content = directory / 'content.md'
        if (
            record.get('status') != 'ready'
            or not content.is_file()
            or not content.read_text().strip()
        ):
            raise ValueError(record['name'] + ' has no readable text to learn from yet.')
        saved = (record.get('author') or '').strip()
        if purpose == 'voice-sample' and saved and not voice_links.same_author(saved, name or ''):
            raise ValueError(
                record['name'] + ' is by ' + saved + '. Learn ' + saved + '’s voice from it, '
                'or untick it.'
            )
        wanted.append(ident)
    changed, problems = [], {}
    for ident in wanted:
        result = source_purpose(
            root,
            {
                'action': 'source-purpose',
                'source': ident,
                'purpose': purpose,
                **({'author': name} if purpose == 'voice-sample' else {}),
            },
        )
        if result['changed']:
            changed.append(ident)
            publish(root, ident, problems)
    from hub_workspace import active

    adapter = active(root)
    if adapter and changed:
        try:
            adapter.hub.sync()
        except (HubError, OSError):
            pass  # Saved here; the next sync shares the new revisions.
    return changed


def route(root, name, data):
    if name == 'library-selection':
        return selection(root, data)
    if name == 'library-add-preview':
        return preview(root, data)
    if name == 'library-add':
        return add(root, data)
    if name == 'library-add-author':
        return set_author(root, data)
    if name == 'library-add-samples':
        return mark_samples(root, data)
    raise ValueError('Unknown management action.')
