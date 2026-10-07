"""Author-facing routes, status, comparisons, and guarded local restoration."""
import difflib
import json
from pathlib import Path
import re
import studio
from hub_store import HubError, encoded, sha

ROUTES = {
    'research this topic': (['deep-research'], ['references/modules/blog-deep-research.md']),
    'deep research': (['deep-research'], ['references/modules/blog-deep-research.md']),
    'use only my sources': (['research-policy-supplied-only'], ['references/modules/blog-deep-research.md']),
    'show research': (['research-status'], ['references/modules/blog-deep-research.md']),
    **{text: (['research-evidence', 'factual-support'], ['references/modules/blog-fact-check.md'])
       for text in ('fact-check', 'fact check', 'check the facts')},
    'show evidence': (['editorial-evidence'], ['references/editorial/evidence.md']),
    'can we back this up': (['editorial-evidence'], ['references/editorial/evidence.md']),
    'package this for launch': (['editorial-package'], ['references/editorial/package.md']),
    'prepare a publication package': (['editorial-package'], ['references/editorial/package.md']),
    'this needs a diagram': (['editorial-visual'], ['references/editorial/visual.md']),
    'make a visual companion': (['editorial-visual'], ['references/editorial/visual.md']),
    'show review edits': (['google-review-list'], ['references/google/suggestions.md']),
    'push as suggestions': (['google-suggest'], ['references/google/suggestions.md']),
    'push as suggestions to google docs': (['google-suggest'], ['references/google/suggestions.md']),
    'push these as suggestions to google docs': (['google-suggest'], ['references/google/suggestions.md']),
    'push as comments': (['google-suggest'], ['references/google/suggestions.md']),
    'push changes to google': (['google-suggest'], ['references/google/suggestions.md']),
    'push changes to google docs': (['google-suggest'], ['references/google/suggestions.md']),
    'clear local caches': (['cache-clear'], ['references/workspace/performance.md']),
    'proofread': (['proofread'], ['references/modules/copy-editing.md']),
    'push to google docs': (['google-push'], ['references/modules/blog-google-handoff.md']),
    'pull from google docs': (['google-pull'], ['references/modules/blog-google-return.md']),
    'pull and proofread': (['google-pull', 'proofread'], ['references/modules/blog-google-return.md', 'references/modules/copy-editing.md']),
    'pull from google docs and proofread': (['google-pull', 'proofread'], ['references/modules/blog-google-return.md', 'references/modules/copy-editing.md']),
    'save and sync': (['hub-sync'], ['references/hub/sync.md']),
    'show status': (['status'], ['references/workspace/status.md']),
    'status': (['status'], ['references/workspace/status.md']),
    'show status card': (['status'], ['references/workspace/status.md']),
    'is everything saved': (['status'], ['references/workspace/status.md']),
    'which copy is newest': (['status'], ['references/workspace/status.md']),
    'continue': (['resume', 'status'], ['references/workspace/resume.md', 'references/workspace/status.md']),
    'what changed': (['changes'], ['references/workspace/changes.md']),
    'undo that edit': (['restore-preview'], ['references/workspace/changes.md']),
    'show my defaults': (['defaults-show'], ['references/workspace/defaults.md']),
    'change my defaults': (['defaults-edit'], ['references/workspace/defaults.md']),
}


def resolve(root, article_id=None, query=None):
    from experience import home
    if article_id:
        return studio.item(root, 'articles', article_id), None
    if not query:
        active = studio.inside(root, '.active-article.json')
        if active.exists():
            selected = studio.read_json(active)
            try: return studio.item(root, 'articles', selected['id']), None
            except (ValueError, KeyError, OSError):
                return None, {'status': 'choose-article', 'reason': 'Previously selected blog is unavailable.'}
    found = home(root, query=query or '', limit=10)
    if found['total'] == 1:
        return studio.item(root, 'articles', found['items'][0]['id']), None
    return None, {'status': 'choose-article', 'reason': 'Choose a blog or start one.',
                  'choices': found['items'], 'total': found['total']}


def route(root, text, article_id=None, destination=None):
    key = ' '.join(text.casefold().strip(' .?!').split())
    review_mode = 'auto'
    review_request = re.fullmatch(r'(?:push|send) (?:(?:feedback|changes|these|edits) )?(?:to google(?: docs)? )?as (comments|suggestions)(?: to google(?: docs)?)?', key)
    if review_request:
        review_mode = 'comments' if review_request[1] == 'comments' else 'auto'
        key = 'push as ' + review_request[1]
    global_routes = {
        'show our pipeline': ('editorial-board', 'references/editorial/board.md'),
        'show pipeline': ('editorial-board', 'references/editorial/board.md'),
        'show editorial board': ('editorial-board', 'references/editorial/board.md'),
        'open editorial desk': ('manage', 'references/editorial/management.md'),
        'what needs my attention': ('editorial-inbox', 'references/editorial/inbox.md'),
        'refresh our blog library': ('library-preview-refresh', 'references/editorial/library.md'),
        'learn from our old blogs': ('library-lessons', 'references/editorial/library.md'),
    }
    if key in global_routes:
        action, reference = global_routes[key]
        return {'status': 'routed', 'actions': [action], 'references': [reference], 'execution': 'Use the current installed operational runtime; keep existing writing pins.'}
    library_request = re.match(r'(import our (?:old|existing) blogs from|find our (?:previous|old) blogs about|what have we already said about)\s+(.+)', text.strip().rstrip('.?!'), re.I)
    if library_request:
        importing = library_request[1].casefold().startswith('import')
        return {'status': 'routed', 'actions': ['library-preview' if importing else 'library-find'],
                'references': ['references/editorial/library.md'], 'input': library_request[2],
                'execution': 'Preview and confirm bounded import scope.' if importing else 'Search a bounded catalog, then read selected passages.'}
    # Intake works with an empty workspace, before current-article resolution.
    intake = re.fullmatch(r'(?:start (?:a blog )?from (?:this |a )?google doc|use (?:this )?google doc as (?:my |a )?(?:draft|starting manuscript))(?:\s*:\s*(.+))?', text.strip().rstrip('.?!'), re.IGNORECASE)
    if intake:
        return {'status': 'routed', 'actions': ['google-start'],
                'references': ['references/google/start.md'],
                'document_input': intake[1], 'execution': 'Capture and inspect the selected Doc, then establish its manuscript and working baseline.'}
    if key in ('push', 'pull'):
        if destination is None:
            return {'status': 'needs-destination', 'question': 'Google Docs or the Team Hub?'}
        key = ('push to google docs' if key == 'push' else 'pull from google docs') if destination == 'google' else 'save and sync' if key == 'push' else 'refresh hub'
    if key == 'refresh hub':
        return {'status': 'routed', 'actions': ['hub-refresh'], 'references': ['references/hub/sync.md']}
    edit_numbers=None
    selected_edits=re.fullmatch(r'apply (?:edits?|suggestions?) ([0-9]+(?:\s*(?:,|and)\s*[0-9]+)*)',key)
    if selected_edits:
        edit_numbers=[int(n) for n in re.findall(r'[0-9]+',selected_edits[1])]
        key='show review edits'
    query = None
    if key.startswith('continue '):
        query = text.strip().rstrip('.?!')[9:].strip(' "“”')
        key = 'continue'
    if key not in ROUTES:
        return {'status': 'interpret-request', 'reason': 'Use normal skill intent routing; do not guess a destructive operation.'}
    actions, references = ROUTES[key]
    if edit_numbers is not None:actions=['google-apply-review-edits']
    if key.endswith('my defaults') or key == 'clear local caches':
        return {'status': 'routed', 'actions': actions, 'references': references}
    selected, question = resolve(root, article_id, query)
    if question: return question
    directory, record = selected
    kind = 'draft' if (directory / 'DRAFT.md').exists() else 'outline'
    base = record.get('google', {}).get('baselines', {}).get(kind)
    return {'status': 'routed', 'id': record['id'], 'title': record['title'], 'kind': kind,
            'actions': actions, 'references': references, 'edit_numbers':edit_numbers,
            **({'review_mode': review_mode} if 'google-suggest' in actions else {}),
            'linked_document': base['document']['url'] if base else None,
            'review_folder': record.get('writing_preferences', {}).get('review_folder'),
            'scope': 'spelling, grammar, punctuation; preserve meaning and voice' if 'proofread' in actions else 'requested operation',
            'execution': 'routing only; perform required capability, freshness, conflict, and save checks before claiming completion'}


def hub_state(root, record):
    from hub_workspace import active
    output = {'status': 'local-only', 'last_confirmed_saved': None, 'url': None, 'observation': 'cached'}
    try:
        adapter = active(root)
        if adapter is None: return output
        output['status'] = 'not-shared'
        saved = adapter.state['items'].get('articles/' + record['id'])
        if not saved: return output
        output['last_confirmed_saved'] = saved.get('last_saved_to_hub')
        graph, remote_files, intents = adapter.hub.view()
        heads = graph['heads'].get(saved['item'], [])
        if len(heads) > 1:
            output['status'] = 'conflicted'
        else:
            try:
                payload = adapter._payload('articles', record['id'], read_only=True, projection=studio.item(root, 'articles', record['id']))[0]
                changed = sha(encoded(payload)) != saved['fingerprint']
            except HubError:
                changed = True
            pending = [i for i in intents if i['operation'] == saved['revision'] and i['state'] != 'published']
            if changed: output['status'] = 'local-changes-not-shared'
            elif pending: output['status'] = pending[-1]['state']
            elif heads != [saved['revision']]: output['status'] = 'newer-hub-revision'
            elif saved.get('last_saved_revision') == saved['revision']: output['status'] = 'shared'
            else: output['status'] = 'not-verified'
        # Link only to an existing generated main page, including renamed/colliding slugs.
        for path, body in remote_files.items():
            if (path.startswith('blogs/') and path.endswith('/README.md') and path.count('/') == 3
                    and any((head + '/record.json)').encode() in body.split(b'---\n\n', 1)[0] for head in heads)):
                output['url'] = adapter.hub.config['url'] + '/blob/main/' + path
                break
    except (HubError, OSError, ValueError, KeyError, TypeError):
        output['status'] = 'unknown'
        output['reason'] = 'Hub status is unavailable; local files are retained.'
    return output


def status(root, article_id=None, query=None, online=False, account=None, details=False):
    selected, question = resolve(root, article_id, query)
    if question: return question
    directory, record = selected
    from google_workflow import sync_status
    from hub_browse import safe
    kind = 'draft' if (directory / 'DRAFT.md').exists() else 'outline'
    local_kind = next((name for name in ('draft', 'outline', 'brief', 'original') if (directory / (name.upper() + '.md')).is_file()), kind)
    actual = studio.artifact_fingerprint(directory, local_kind.upper() + '.md')
    local = 'saved' if actual and actual == record.get('artifact_hashes', {}).get(local_kind) else 'uncheckpointed-changes' if actual else 'no-manuscript'
    try:
        google = sync_status(root, directory, record, kind, online, account)
    except (OSError, ValueError, KeyError, TypeError):
        target = record.get('google', {}).get('baselines', {}).get(kind, {}).get('document', {})
        google = {'status': 'not-checked', 'label': 'Not checked', 'document_url': target.get('url'),
                  'last_checked_at': None, 'last_successful_check_at': None,
                  'reason': 'Google status could not be read; inspect the connection or local observation cache.'}
    if not google['document_url']: google['label'] = 'Not linked'
    hub = hub_state(root, record)
    next_step = record.get('next_step') or 'Continue writing.'
    if hub['status'] in ('conflicted', 'newer-hub-revision'): next_step = 'Compare the shared versions before continuing.'
    elif google['status'] in ('google-changes', 'both-changed', 'pending-review'): next_step = google['next_step']
    elif hub['status'] in ('queued', 'pending-review', 'local-changes-not-shared'): next_step = 'Finish sharing the saved work with the Hub.'
    result = {'status': 'ready', 'id': record['id'], 'title': record['title'], 'stage': record['stage'],
              'local': local, 'hub': hub, 'google': {k: google[k] for k in ('label', 'status', 'document_url', 'last_checked_at', 'last_successful_check_at')},
              'next_step': next_step}
    if 'review_state' in google:result['google']['review_state']=google['review_state']
    lines = ['**' + safe(record['title']) + '**', safe(record['stage']) + ' · Google: ' + google['label'],
             'Local: ' + local.replace('-', ' ') + ' · Hub (last known): ' + hub['status'].replace('-', ' '),
             'Last checked: ' + str(google['last_checked_at'] or 'Not checked'),
             'Last confirmed saved to Hub: ' + str(hub['last_confirmed_saved'] or 'Not confirmed'),
             '**Next:** ' + safe(next_step)]
    links = []
    url = google['document_url']
    if isinstance(url, str) and re.fullmatch(r'https://docs\.google\.com/document/d/[A-Za-z0-9_-]{1,200}/edit', url):
        links.append('[Google Doc](' + url + ')')
    if hub['url']: links.append('[GitHub copy](' + hub['url'] + ')')
    if links: lines.append(' · '.join(links))
    result['card'] = '\n\n'.join(lines)
    if details: result['details'] = {'voice': record['voice'], 'guidance': record.get('guidance'), 'google_reason': google['reason'], 'hub_observation': 'Cached Hub state; last-confirmed time is historical. Refresh the Hub for a current remote comparison.'}
    return result


def histories(directory, kind):
    folder = studio.inside(directory, 'history')
    return sorted((p for p in folder.glob(kind + '-*.md') if p.is_file() and not p.is_symlink()), key=lambda p: p.name)


def history_file(directory, kind, name):
    if not re.fullmatch(kind + r'-[A-Za-z0-9_.-]+\.md', name):
        raise ValueError('Choose a listed history revision for this artifact.')
    path = studio.inside(directory, 'history', name)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Selected revision is unavailable.')
    return path


def text_diff(before, after, limit=20):
    left, right = before.splitlines(), after.splitlines()
    changes = []
    for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if tag == 'equal': continue
        headings = [line.lstrip('# ').strip() for line in left[:a+1] if line.startswith('#')]
        changes.append({'section': headings[-1] if headings else 'Opening', 'operation': tag,
                        'before_lines': [a+1, b], 'after_lines': [c+1, d],
                        'before': '\n'.join(left[a:b])[:2000], 'after': '\n'.join(right[c:d])[:2000]})
    return {'text_changed': before != after, 'changed_blocks': len(changes), 'changes': changes[:limit], 'truncated': len(changes) > limit}


def changes(root, args):
    selected, question = resolve(root, args.id)
    if question: return question
    directory, record = selected
    current_path = studio.inside(directory, args.kind.upper() + '.md')
    if not current_path.is_file(): raise ValueError('No saved artifact to compare.')
    current = current_path.read_text()
    history = histories(directory, args.kind)
    revisions = [{'revision': p.name, 'sha256': studio.digest(p.read_bytes())} for p in history[-30:]]
    events = record.get('artifact_events', [])
    for row in revisions:
        match = next((e for e in reversed(events) if e.get('before') == row['revision']), None)
        if match: row['before_operation'] = match.get('label', 'save')
    result = {'id': record['id'], 'kind': args.kind, 'revisions': revisions,
              'history_truncated': len(history) > 30, 'google': 'not-checked', 'hub': hub_state(root, record)}
    if args.against == 'hub':
        from hub_workspace import active
        adapter = active(root)
        if adapter is None: raise ValueError('Select a Team Hub for this comparison.')
        saved = adapter.state['items'].get('articles/' + record['id'])
        if not saved: raise ValueError('This article has no shared checkpoint.')
        graph = adapter.hub.graph(include_local=False)
        heads = graph['heads'].get(saved['item'], [])
        if len(heads) != 1:
            return {**result, 'baseline': saved['revision'], 'hub_heads': heads,
                    'status': 'conflicted' if len(heads) > 1 else 'unavailable'}
        def shared_text(revision):
            snapshot = adapter.hub.read(saved['item'], revision)
            name = 'artifacts/' + args.kind.upper() + '.md'
            if name not in snapshot['paths']: raise ValueError('Shared artifact is unavailable.')
            return Path(snapshot['paths'][name]).read_text()
        baseline, remote = shared_text(saved['revision']), shared_text(heads[0])
        return {**result, 'baseline': saved['revision'], 'remote_revision': heads[0],
                'local': text_diff(baseline, current), 'remote': text_diff(baseline, remote),
                'status': 'both-changed' if current != baseline and remote != baseline else 'compared',
                'note': 'Cached Hub comparison; refresh first for current remote state. No revision selected or overwritten.'}
    if args.google_file or args.observation:
        if not args.google_file or not args.observation: raise ValueError('Supply both returned Google text and its observation.')
        from google_workflow import observation, compare
        body = studio.read_text(args.google_file)
        obs = observation(studio.read_json(Path(args.observation)), body)
        compared = compare(directory, record, args.kind, obs, body)
        baseline = Path(compared['baseline_file']).read_text()
        same_text = obs['content_sha256'] == record['google']['baselines'][args.kind]['document']['content_sha256']
        result.update(baseline='saved Google transfer', google=compared['status'],
                      native_changed=compared['format_changed'], format_changed=compared['format_changed'] if same_text else None,
                      observed_at=obs['observed_at'], local=text_diff(baseline, current), remote=text_diff(baseline, body),
                      note='Accepted text only; suggestions/comments are separate. Observation time does not prove ongoing freshness.')
        return result
    base = history_file(directory, args.kind, args.revision) if args.revision else history[-1] if history else None
    if base:
        result.update(baseline=base.name, local=text_diff(base.read_text(), current))
    else: result.update(baseline=None, note='No previous local text checkpoint.')
    # Compare the last two captured Google formatting observations, not Markdown spacing guesses.
    transfers = record.get('google', {}).get('transfers', {})
    captured = [t for t in transfers.values() if t.get('kind') == args.kind and t.get('document', {}).get('format_sha256')]
    captured.sort(key=lambda t: t['document'].get('observed_at', ''))
    result['format_changed'] = None
    if len(captured) > 1:
        a, b = captured[-2:]
        if a['document']['document_id'] == b['document']['document_id'] and a['document']['tab_ids'] == b['document']['tab_ids']:
            result['format_changed'] = (a['document']['format_sha256'] != b['document']['format_sha256']) if a['document']['content_sha256'] == b['document']['content_sha256'] else None
            result['format_baseline'] = [a['document']['observed_at'], b['document']['observed_at']]
    return result


def restore(root, args):
    directory, record = studio.item(root, 'articles', args.id)
    path = history_file(directory, args.kind, args.revision)
    target = studio.inside(directory, args.kind.upper() + '.md')
    if not target.is_file(): raise ValueError('No current artifact; inspect history before restoring.')
    body, before = path.read_text(), target.read_text()
    if not body.strip(): raise ValueError('Cannot restore an empty artifact.')
    hub = hub_state(root, record)
    guard = studio.digest(json.dumps({'record': record, 'current': before, 'restore': body, 'hub': hub}, sort_keys=True).encode())
    if not args.apply:
        return {'id': record['id'], 'status': 'preview', 'revision': args.revision, 'expected': guard,
                'changes': text_diff(before, body), 'hub': hub,
                'scope': 'Restore text only; retain current voice, sources, rules, and guidance pins. Google remains unchanged.'}
    if args.expected != guard:
        raise ValueError('Article, history, or Hub state changed. Preview the restore again.')
    if hub['status'] in ('conflicted', 'newer-hub-revision', 'unknown'):
        raise ValueError('Resolve or inspect Hub state before restoring this article.')
    if args.kind == 'draft' and record['stop_point'] in ('outline', 'brief'):
        raise ValueError('The selected task stops before drafting.')
    saved = studio.save_artifact(directory, args.kind, body, record, label='restore ' + args.revision)
    if args.kind == 'draft':
        for review in record['reviews'].values(): review['status'] = 'stale'
    studio.persist(directory, 'articles', record)
    return {**record, 'status': 'restored', 'saved_artifact': saved, 'google_written': False}


def add_parser(groups):
    select = groups.add_parser('select');select.add_argument('--id', required=True)
    status_p = groups.add_parser('status');status_p.add_argument('--id');status_p.add_argument('--query')
    status_p.add_argument('--online', action='store_true');status_p.add_argument('--account')
    status_p.add_argument('--details', action='store_true');status_p.add_argument('--format', choices=('json', 'markdown'), default='json')
    routing = groups.add_parser('route');routing.add_argument('request');routing.add_argument('--id')
    routing.add_argument('--destination', choices=('google', 'hub'))
    change = groups.add_parser('changes');change.add_argument('--id');change.add_argument('--kind', choices=('draft', 'outline'), default='draft')
    change.add_argument('--revision');change.add_argument('--google-file');change.add_argument('--observation')
    change.add_argument('--against', choices=('local', 'hub'), default='local')
    defaults = groups.add_parser('defaults').add_subparsers(dest='action', required=True)
    show = defaults.add_parser('show');show.add_argument('--id')
    from writing_defaults import KEYS
    for action in ('set', 'reset'):
        p = defaults.add_parser(action);p.add_argument('--scope', choices=('personal', 'team'), default='personal')
        p.add_argument('--key', choices=KEYS, required=True);p.add_argument('--value', required=action == 'set')


def command(root, args):
    if args.group == 'route': return route(root, args.request, args.id, args.destination)
    if args.group == 'status': return status(root, args.id, args.query, args.online, args.account, args.details)
    if args.group == 'changes': return changes(root, args)
    if args.group == 'select':
        _, record = studio.item(root, 'articles', args.id)
        studio.write_json(studio.inside(root, '.active-article.json'), {'id': record['id']})
        return {'status': 'selected', 'id': record['id'], 'title': record['title']}
    from writing_defaults import command as defaults_command
    return defaults_command(root, args)
