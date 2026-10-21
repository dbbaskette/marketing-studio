"""Published posts as author voice samples, from a list of links.

The links go through the reference library's own `urls` import: the same scope check,
pinned fetch, size limits, extraction and Hub sharing. This module only reads the list,
derives its site scope, and classifies each saved post as a voice sample for the chosen
author once its byline (where the page shows one) agrees.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

import blog_library
import studio
from hub_store import HubError, encoded, sha

MAX_LIST_BYTES = 256 * 1024
MAX_SKIPPED = 20
LIST_WORDS = {'blog', 'blogs', 'link', 'links', 'post', 'posts', 'url', 'urls', 'list', 'articles'}
BYLINE_META = ('author', 'article:author', 'parsely-author', 'sailthru.author', 'dc.creator', 'byl')
BYLINE_CLASSES = {'byline', 'author', 'author-name', 'entry-author', 'post-author'}
LIST_MARKER = re.compile(r'^(?:[-*•+]|\d+[.)])\s+')
VOID = ('img', 'br', 'hr', 'input', 'link', 'meta', 'source', 'wbr')


def author_from_filename(name):
    """'darin-zook-blog-links.txt' -> 'Darin Zook': a suggestion the person can change."""
    stem = Path(str(name or '')).stem
    words = [w for w in re.split(r'[\s_.-]+', stem) if w and w.casefold() not in LIST_WORDS]
    return ' '.join(w[:1].upper() + w[1:] for w in words if not w.isdigit())[:200]


def site_of(scope):
    """'https://blogs.vmware.com/tanzu/' -> 'blogs.vmware.com/tanzu/'."""
    return scope.split('://', 1)[-1]


def scope_for(links):
    """The common host and folder of these links, never narrower than any link's folder."""
    paths = [[part for part in urlsplit(link).path.split('/') if part] for link in links]
    shortest = min(len(parts) for parts in paths)
    common = []
    # A link's last segment is the post itself, so the scope stops at its folder.
    for index in range(max(0, shortest - 1)):
        segment = paths[0][index]
        if any(parts[index] != segment for parts in paths):
            break
        common.append(segment)
    host = urlsplit(links[0]).hostname
    return 'https://' + host + '/' + ''.join(part + '/' for part in common)


def parse(text, site=None):
    """Links from a pasted list or a .txt file: one per line, `#` comments and blanks ignored.

    Returns the chosen site's canonical links and what was left out, without saving anything.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Paste links or choose a text file with one link per line.')
    if len(text.encode()) > MAX_LIST_BYTES:
        raise ValueError('This list is larger than 256 KiB. Split it into smaller files.')
    links, skipped, seen = [], [], set()
    duplicates = comments = upgraded = unusable = 0
    for number, line in enumerate(text.splitlines(), 1):
        value = line.strip().lstrip('﻿')
        if not value:
            continue
        if value.startswith('#'):
            comments += 1
            continue
        value = LIST_MARKER.sub('', value).strip('<>').strip()
        try:
            if any(space in value for space in ' \t'):
                raise ValueError('Put one link on each line, with nothing after it.')
            if value.lower().startswith('http://'):
                value = 'https://' + value[7:]
                upgraded += 1
            elif not value.lower().startswith('https://'):
                raise ValueError('Not a web link: it does not start with https:// or http://.')
            link = blog_library.canonical(value)
        except ValueError as exc:
            unusable += 1
            if len(skipped) < MAX_SKIPPED:
                skipped.append({'line': number, 'text': value[:120], 'reason': str(exc)})
            continue
        if link in seen:
            duplicates += 1
            continue
        seen.add(link)
        links.append(link)
    if not links:
        raise ValueError('No usable links were found. Put one https:// link on each line.')
    hosts = {}
    for link in links:
        hosts.setdefault(urlsplit(link).hostname, []).append(link)
    sites = []
    for host, found in sorted(hosts.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        scope = scope_for(found)
        sites.append({'site': host, 'scope': scope, 'shown': site_of(scope), 'links': len(found)})
    result = {
        'duplicates': duplicates,
        'comments': comments,
        'upgraded': upgraded,
        'unusable': unusable,
        'skipped': skipped,
        'sites': sites,
    }
    if site:
        chosen = str(site).strip().lower().split('://', 1)[-1].split('/', 1)[0]
        if chosen not in hosts:
            raise ValueError(
                'None of these links are on ' + chosen + '. Choose one of the listed sites.'
            )
    elif len(hosts) > 1:
        return {
            **result,
            'status': 'choose-site',
            'links': [],
            'left_out': 0,
            'problem': 'These links come from '
            + str(len(hosts))
            + ' sites. A voice import reads one site at a time: choose the site to use now, '
            'or remove the other links.',
        }
    else:
        chosen = next(iter(hosts))
    chosen_links = hosts[chosen]
    if len(chosen_links) > blog_library.MAX_POSTS:
        raise ValueError(
            'This list has %d links from one site. Import at most %d at a time; split the file.'
            % (len(chosen_links), blog_library.MAX_POSTS)
        )
    scope = scope_for(chosen_links)
    return {
        **result,
        'status': 'ready',
        'site': chosen,
        'scope': scope,
        'shown_scope': site_of(scope),
        'links': chosen_links,
        'left_out': len(links) - len(chosen_links),
    }


class Bylines(HTMLParser):
    """Author names a page states about itself: JSON-LD, meta tags, rel=author and bylines."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = {'json-ld': [], 'meta': [], 'rel': [], 'class': []}
        self.open = []  # [tag, kind, text parts] for elements whose text is captured.
        self.script = None

    def handle_starttag(self, tag, attrs):
        values = {key: (value or '') for key, value in attrs}
        if tag == 'script' and values.get('type', '').strip().lower() == 'application/ld+json':
            self.script = []
            return
        if tag == 'meta':
            name = (values.get('name') or values.get('property') or '').strip().lower()
            if name in BYLINE_META:
                self.found['meta'].append(values.get('content', ''))
            return
        if tag in VOID:
            return
        kind = None
        if tag == 'a' and 'author' in values.get('rel', '').lower().split():
            kind = 'rel'
        elif (
            set(values.get('class', '').lower().split()) & BYLINE_CLASSES
            or values.get('itemprop', '').lower() == 'author'
        ):
            kind = 'class'
        if kind or self.open:
            self.open.append([tag, kind, []])

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.json_ld(''.join(self.script))
            self.script = None
            return
        if not any(entry[0] == tag for entry in self.open):
            return
        while self.open:
            name, kind, parts = self.open.pop()
            text = ' '.join(''.join(parts).split())
            if self.open:
                self.open[-1][2].append(' ' + text + ' ')
            if kind:
                self.found[kind].append(text)
            if name == tag:
                break

    def handle_data(self, data):
        if self.script is not None:
            if sum(map(len, self.script)) < blog_library.MAX_FETCH:
                self.script.append(data)
        elif self.open:
            self.open[-1][2].append(data)

    def json_ld(self, content):
        try:
            value = json.loads(content)
        except (ValueError, RecursionError):
            return

        def names(author):
            if isinstance(author, str):
                return [author]
            if isinstance(author, dict):
                # A publisher credited as the author (an Organization) is not a person
                # whose voice a post shows; the next byline source decides instead.
                kinds = author.get('@type')
                kinds = kinds if isinstance(kinds, list) else [kinds]
                if any(str(kind).casefold() in NOT_A_PERSON for kind in kinds):
                    return []
                return [author['name']] if isinstance(author.get('name'), str) else []
            if isinstance(author, list):
                return [name for entry in author[:10] for name in names(entry)]
            return []

        def walk(node, depth=0):
            if depth > 6:
                return
            if isinstance(node, list):
                for entry in node[:50]:
                    walk(entry, depth + 1)
            elif isinstance(node, dict):
                if 'author' in node:
                    self.found['json-ld'].extend(names(node['author']))
                for key, entry in node.items():
                    if key != 'author' and isinstance(entry, (dict, list)):
                        walk(entry, depth + 1)

        try:
            walk(value)
        except RecursionError:
            return


NOT_A_PERSON = frozenset(('organization', 'brand', 'corporation', 'newsmediaorganization'))


def plain(name):
    """A name compared without case, accents, punctuation, a leading 'By', or word order."""
    text = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().casefold()
    words = re.sub(r'[^a-z0-9]+', ' ', text).split()
    if words[:1] == ['by']:
        words = words[1:]
    return words


def bylines(content):
    """Distinct author names a fetched page states, from the most reliable place that has any."""
    if not content:
        return []
    parser = Bylines()
    try:
        parser.feed(content.decode('utf-8', 'replace'))
        parser.close()
    except (AssertionError, ValueError):
        return []
    for kind in ('json-ld', 'meta', 'rel', 'class'):
        names, seen = [], set()
        for value in parser.found[kind]:
            value = ' '.join(str(value).split())
            if value.lower().startswith('by '):
                value = value[3:].strip()
            words = tuple(plain(value))
            if not words or len(value) > 80 or '://' in value or words in seen:
                continue
            seen.add(words)
            names.append(value)
        if names:
            return names[:5]
    return []


def same_author(byline, author):
    """True when every word of the shorter name appears in the longer one."""
    a, b = set(plain(byline)), set(plain(author))
    if not a or not b:
        return False
    small, large = sorted((a, b), key=len)
    return small <= large


def library_rows(root):
    """Saved library posts by every URL they are known under."""
    found = {}
    for row in blog_library.source_rows(root):
        metadata = row['record'].get('library') or {}
        for key in (metadata.get('identity'), metadata.get('canonical_url')):
            if isinstance(key, str) and key.startswith('https://'):
                found.setdefault(key, row)
    return found


def preview(root, data):
    """What an import of these links would do. Saves nothing and reaches no network."""
    author = studio.checked_author(data.get('author'))
    found = parse(data.get('text'), data.get('site'))
    if found['status'] != 'ready':
        return {**found, 'author': author}
    known = library_rows(root)
    posts = [
        {
            'url': link,
            'status': 'in-library' if link in known else 'new',
            'title': known[link]['record'].get('name') if link in known else None,
        }
        for link in found['links']
    ]
    in_library = sum(post['status'] == 'in-library' for post in posts)
    return {
        **{key: value for key, value in found.items() if key != 'links'},
        'author': author,
        'links': len(posts),
        'in_library': in_library,
        'to_fetch': len(posts) - in_library,
        'posts': posts,
        'expected': sha(encoded([author, found['scope'], posts])),
        'next_step': 'Check the site and author, then import. Each new page is fetched once from '
        + found['shown_scope']
        + ' and saved in the reference library; posts already there are reused.',
    }


def fingerprint(data):
    return sha(encoded([data.get('text'), data.get('author'), data.get('site') or '']))


def operation_for(text, author, site=None):
    """The same list, author and site always continue the same import (for chat and CLI)."""
    return sha(encoded(['voice-links', text, author, site or '']))[:32]


def ledger_path(root, operation):
    if not isinstance(operation, str) or not re.fullmatch(r'[a-f0-9]{32}', operation):
        raise ValueError('A voice import operation ID is required.')
    directory = blog_library.folder(root) / 'voice-links'
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory / (operation + '.json')


def collection_name(root, author):
    names = {str(c['name']).strip().casefold() for c in blog_library.collections(root).values()}
    base = 'Published posts by ' + author
    if base.casefold() not in names:
        return base
    dated = base + ' · ' + studio.now()[:10]
    for number in range(1, 100):
        name = dated if number == 1 else dated + ' (' + str(number) + ')'
        if name.casefold() not in names:
            return name
    raise ValueError('Too many collections share this author name. Rename one first.')


def start(root, data, path, reader):
    """Check the shown preview, then set the new links up as one draft `urls` collection."""
    shown = preview(root, data)
    if shown['status'] != 'ready':
        raise ValueError(shown['problem'])
    if data.get('expected') is not None and data['expected'] != shown['expected']:
        raise ValueError(
            'These links or your library changed since the check. '
            'Check the links again before importing.'
        )
    known = library_rows(root)
    from hub_workspace import active

    adapter = active(root)
    reused = {}
    for post in shown['posts']:
        if post['status'] == 'in-library':
            row = known[post['url']]
            # A post only the Team Hub holds is checked out here, as a library import does.
            reused[post['url']] = (
                adapter._checkout(row['id']) if row['location'] == 'hub' else row['id']
            )
    fresh = [post['url'] for post in shown['posts'] if post['status'] == 'new']
    manifest = None
    if fresh:
        draft = blog_library.normalize(
            root,
            {
                'key': 'voice-links-' + path.stem[:16],
                'name': collection_name(root, shown['author']),
                'type': 'urls',
                'scope': shown['scope'],
                'urls': fresh,
            },
        )
        manifest = blog_library.preview(root, draft['key'], reader=reader, config=draft)
    state = {
        'schema': 1,
        'fingerprint': fingerprint(data),
        'author': shown['author'],
        'scope': shown['scope'],
        'links': [post['url'] for post in shown['posts']],
        'reused': reused,
        'preview': manifest['preview'] if manifest else None,
        'created_at': studio.now(),
    }
    studio.write_json(path, state)
    return state


def classify(directory, record, author):
    """Mark one saved post as this author's voice sample. False when it already is one."""
    purposes = list(record.get('purposes') or [])
    library = dict(record.get('library') or {})
    if 'voice-sample' not in purposes:
        purposes.append('voice-sample')
    if (
        purposes == record.get('purposes')
        and record.get('author') == author
        and (not library or library.get('author') == author)
    ):
        return False
    blog_library.save_revision(directory, record)
    record['purposes'] = purposes
    record['author'] = author
    if library:
        library['author'] = author
        record['library'] = library
    record['revision'] += 1
    studio.persist(directory, 'sources', record)
    return True


def sample_status(root, ident, author, kept, changed):
    """Classify one saved post unless its byline names someone else and it was not kept."""
    directory, record = studio.item(root, 'sources', ident)
    found = {'title': record.get('name')}
    original = record.get('original_path') or ''
    content = b''
    if original.endswith(('.html', '.htm')):
        path = studio.inside(directory, original)
        content = path.read_bytes() if path.is_file() else b''
    names = bylines(content)
    saved_author = record.get('author')
    if not names and saved_author and saved_author != author:
        names = [saved_author]  # Someone already said whose post this is.
    found['byline'] = names
    if record.get('status') != 'ready':
        return {**found, 'no_text': True, 'reason': 'No readable text was found on this page.'}
    if names and not any(same_author(name, author) for name in names):
        found['mismatch'] = True
        if not kept:
            return found
        found['kept'] = True
    if classify(directory, record, author):
        changed.append(record['id'])
    return {**found, 'sample': True}


def next_step(counts, samples, author):
    words = []
    if counts['pending']:
        words.append(
            '%d links are still to import; continue to fetch the next batch.' % counts['pending']
        )
    if counts['mismatch']:
        words.append(
            'Posts whose byline names someone else are left out; keep any that %s wrote.' % author
        )
    if counts['failed']:
        words.append('Failed links can be tried again; nothing else is fetched twice.')
    if samples:
        words.append(
            'Next, learn or update the voice from these samples: choose up to ten, then confirm '
            'they may be analyzed. The voice stays provisional until you audition and confirm it.'
        )
    return ' '.join(words) or 'No post could be used as a voice sample yet.'


def run(root, data, reader=None, delay=0.25):
    """Import (or continue importing) a list of links and classify them as voice samples.

    One call fetches at most one library batch (25 posts). Repeating the same request
    continues it; already-saved posts are reused, never fetched or copied again. `keep`
    names posts whose byline differs that the person still wants as samples, and
    `retry` fetches failed links again.
    """
    reader = reader or blog_library.fetch
    if set(data) - {'operation', 'text', 'author', 'site', 'expected', 'keep', 'retry'}:
        raise ValueError('Unknown voice import field.')
    keep = data.get('keep') or []
    if not isinstance(keep, list) or any(not isinstance(v, str) for v in keep):
        raise ValueError('Choose the posts to keep from this import.')
    retry = data.get('retry', False)
    if not isinstance(retry, bool):
        raise ValueError('Choose whether to retry failed links.')
    path = ledger_path(root, data.get('operation'))
    if path.exists():
        state = studio.read_json(path)
        if state['fingerprint'] != fingerprint(data):
            raise ValueError('This operation belongs to a different list of links.')
    else:
        state = start(root, data, path, reader)
    author = state['author']
    manifest = None
    if state['preview']:
        manifest_path = blog_library.folder(root) / (state['preview'] + '.json')
        manifest = studio.read_json(manifest_path)
        results = manifest['results']
        wanted = [
            entry['identity']
            for entry in manifest['candidates']
            if (
                results.get(entry['identity'], {}).get('status') == 'failed'
                if retry
                else entry['identity'] not in results
            )
        ][: blog_library.MAX_BATCH]
        if wanted:
            blog_library.import_batch(
                root,
                state['preview'],
                limit=blog_library.MAX_BATCH,
                retry=retry,
                reader=reader,
                delay=delay,
                selected=wanted,
                analyze=False,
            )
            manifest = studio.read_json(manifest_path)
    from hub_workspace import active

    adapter = active(root)
    rows, changed = [], []
    for link in state['links']:
        row = {'url': link, 'status': 'pending', 'sample': False}
        ident = state['reused'].get(link)
        if ident:
            row['status'] = 'in-library'
        elif manifest is not None:
            saved = manifest['results'].get(link)
            if saved and saved['status'] == 'failed':
                reason = saved.get('reason') or 'Not read.'
                if reason == blog_library.OUT_OF_SCOPE:
                    reason = (
                        'This page has moved outside '
                        + site_of(state['scope'])
                        + '; use its new address.'
                    )
                row.update(status='failed', reason=reason)
            elif saved:
                ident = saved['id']
                row['status'] = 'imported'
        if ident:
            row['id'] = ident
            row.update(sample_status(root, ident, author, link in keep, changed))
        rows.append(row)
    if adapter:
        for ident in changed:
            try:
                adapter._publish('sources', ident)
            except (HubError, OSError, ValueError) as exc:
                next(r for r in rows if r.get('id') == ident)['sharing'] = str(exc)[:400]
    counts = {
        name: sum(r['status'] == name for r in rows)
        for name in ('imported', 'in-library', 'failed', 'pending')
    }
    counts['mismatch'] = sum(bool(r.get('mismatch')) and not r['sample'] for r in rows)
    counts['no_text'] = sum(bool(r.get('no_text')) for r in rows)
    counts['samples'] = sum(r['sample'] for r in rows)
    samples = [r['id'] for r in rows if r['sample']]
    result = {
        'operation': path.stem,
        'author': author,
        'scope': state['scope'],
        'shown_scope': site_of(state['scope']),
        'links': len(rows),
        'remaining': counts['pending'],
        'counts': counts,
        'samples': samples,
        'results': rows,
        'next_step': next_step(counts, samples, author),
    }
    if adapter:
        try:
            result['hub_sync'] = adapter.hub.sync()
        except (HubError, OSError):
            result['hub_sync'] = {
                'status': 'local-saved-not-shared',
                'next_step': 'Retry Hub sync; do not repeat the import.',
            }
    return result


def command(root, args):
    """`library voice-links`: check the list, or with --import, import and classify it."""
    path = Path(args.file).expanduser()
    if not path.is_file() or path.stat().st_size > MAX_LIST_BYTES:
        raise ValueError('Choose a text file of links up to 256 KiB.')
    text = path.read_text(encoding='utf-8')
    author = args.author or author_from_filename(path.name)
    if not author:
        raise ValueError('Name the author these posts belong to with --author.')
    data = {'text': text, 'author': author, 'site': args.site}
    if not args.do_import:
        return preview(root, data)
    data.update(
        operation=operation_for(text, author, args.site),
        keep=args.keep or [],
        retry=args.retry,
    )
    return run(root, data)
