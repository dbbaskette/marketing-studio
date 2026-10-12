"""Readable review comments and explicitly selected, revision-guarded edits."""
import json
import re
import time

import google_roundtrip as rt
import google_suggestions as gs
import studio
from google_drive import GoogleError, digest, encoded, write_new
from hub_store import contained, locked, write_json

# Waits before repeating a comment that Google refused only because of a rate limit.
RATE_LIMIT_WAITS = (2, 5, 10)
PULL_NEXT = 'Pull from Google Docs to save the verified wording and formatting locally and to the selected Hub.'


def unavailable(error):
    return isinstance(error, GoogleError) and error.review_unavailable


def marker(finding_id):
    return '[Blog Studio ' + finding_id + ']'


def label(numbers):
    return ('edits ' if len(numbers) > 1 else 'edit ') + ', '.join(map(str, numbers))


def section_names(doc, paragraphs):
    """Nearest heading above each body paragraph, for a comment's location line."""
    sections = {}
    for tab in rt.tabs(doc):
        tab_id = tab['tabProperties']['tabId']
        section = 'Opening'
        for (owner, start), paragraph in paragraphs.items():
            if owner != tab_id:
                continue
            if paragraph.get('paragraphStyle', {}).get('namedStyleType', '').startswith('HEADING_'):
                section = rt.paragraph_text(paragraph)[:-1]
            sections[(tab_id, start)] = section
    return sections


def comment_body(items):
    """The text of one review comment for one finding, or for a group of minor fixes in a paragraph."""
    first = items[0]
    numbers = [entry['number'] for entry in items]
    title = 'Edits ' + ', '.join(map(str, numbers)) if len(items) > 1 else 'Edit ' + str(numbers[0])
    body = title + ' · ' + first['section'] + '\nTab: ' + first['tab_title'] + '\n'
    for entry in items:
        finding = entry['finding']
        body += '\n' + ('Edit ' + str(entry['number']) + '\n' if len(items) > 1 else '')
        body += 'Current: ' + finding['before'] + '\n'
        if finding['kind'] == 'edit':
            body += 'Proposed: ' + (finding['after'] or '(delete this text)') + '\n'
        body += 'Why: ' + finding['reason'] + '\n'
    editable = [entry['number'] for entry in items if entry['finding']['kind'] == 'edit']
    if editable:
        body += '\nReview in Blog Studio: “Apply edits ' + ', '.join(map(str, editable)) + '.”\n'
    else:
        body += '\nDiscuss this feedback before deciding on wording.\n'
    return body + '\n'.join(marker(entry['finding']['id']) for entry in items)


def build(doc, findings, selected_tabs, start=1):
    """Numbered, readable comments. Numbers continue across a blog's review batches."""
    # Reuse exact-quote, overlap, scope, style and native-index validation.
    gs.validate(doc, findings, selected_tabs)
    paragraphs = rt.paragraphs(doc)
    sections = section_names(doc, paragraphs)
    titles = {tab['tabProperties']['tabId']: tab['tabProperties'].get('title', tab['tabProperties']['tabId'])
              for tab in rt.tabs(doc)}
    entries = []
    groups = []
    for number, finding in enumerate(findings, start):
        key, _ = rt.paragraph_at(doc, finding['tab_id'], finding['start_index'])
        entry = {'number': number, 'finding': finding, 'paragraph': rt.paragraph_text(paragraphs[key])[:-1],
                 'paragraph_start': key[1], 'section': sections[key], 'tab_title': titles[key[0]]}
        entries.append(entry)
        minor = bool(finding.get('minor')) and finding['kind'] == 'edit'
        group = next((g for g in groups if minor and g['minor'] and g['key'] == key and len(g['entries']) < 4), None)
        if group is None:
            group = {'key': key, 'minor': minor, 'entries': []}
            groups.append(group)
        group['entries'].append(entry)
    comments = []

    def render(items):
        body = comment_body(items)
        if len(body.encode()) > 2048:
            if len(items) > 1:
                for entry in items:
                    render([entry])
                return
            raise GoogleError('This review comment is too long; shorten the finding before posting.')
        first = items[0]
        finding = first['finding']
        grouped = len(items) > 1
        quote = first['paragraph'] if grouped else finding['before']
        anchor = first['paragraph_start'] if grouped else finding['start_index']
        span = {'tabId': finding['tab_id'], 'startIndex': anchor, 'endIndex': anchor + rt.utf16(quote)}
        comments.append({'numbers': [entry['number'] for entry in items], 'content': body, 'quote': quote, 'range': span})

    for group in groups:
        render(group['entries'])
    return {'entries': entries, 'comments': comments}


def path(root, saved):
    return contained(gs.ledger(root), gs.operation_key(saved) + '.json')


def first_number(saved):
    return saved.get('number_start', 1)


def numbers_of(saved):
    return [entry['number'] for entry in saved['comment_plan']['entries']]


def index_path(directory):
    return studio.inside(directory, '.google-review.json')


def load_batch(root, key):
    """(plan path, plan, receipt) for one posted review batch, or None when its local record is gone."""
    plan_path = contained(gs.ledger(root), key + '.plan.json')
    if not plan_path.is_file():
        return None
    saved = studio.read_json(plan_path)
    receipt_path = path(root, saved)
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
    return plan_path, saved, receipt


def read_index(root, directory):
    """This computer's review batches for one blog, oldest first, and the next free edit number."""
    index = {'schema': 2, 'operations': [], 'next_number': 1}
    location = index_path(directory)
    if not location.is_file():
        return index
    value = studio.read_json(location)
    if value.get('schema') == 2:
        return value
    # Earlier runtimes kept a single pointer to the latest batch.
    if isinstance(value.get('operation'), str):
        index['operations'].append(value['operation'])
        batch = load_batch(root, value['operation'])
        if batch:
            index['next_number'] = max(numbers_of(batch[1]), default=0) + 1
    return index


def numbers_in_document(contents):
    """Edit numbers already used by Blog Studio comments in the Doc, from any computer."""
    used = []
    for content in contents:
        if not isinstance(content, str) or '[Blog Studio ' not in content:
            continue
        title = re.match(r'Edits? ([0-9][0-9, ]*) ·', content)
        if title:
            used.extend(int(number) for number in re.findall(r'[0-9]+', title[1]))
    return used


def next_number(client, root, directory, document_id, review_document):
    """Numbers continue per blog; comments already in the Doc are honoured when they can be listed."""
    highest = read_index(root, directory)['next_number'] - 1
    if 'comments' in review_document:
        contents = [thread.get('headPost', {}).get('content') for thread in review_document['comments']]
    else:
        try:
            contents = [thread.get('content') for thread in client.review_comments(document_id)]
        except GoogleError:
            contents = []  # Local numbering still applies; apply rechecks the Doc before posting.
    return max([highest, *numbers_in_document(contents)]) + 1


def register(root, directory, saved, key):
    """Record a batch when its first comment is about to be posted, keeping every batch reachable."""
    index = read_index(root, directory)
    if key in index['operations']:
        return
    numbers = numbers_of(saved)
    if numbers and min(numbers) < index['next_number']:
        raise GoogleError('Another review batch already uses these edit numbers. Make a fresh plan so its numbers '
                          'continue from ' + str(index['next_number']) + '.')
    index['operations'].append(key)
    index['next_number'] = max(index['next_number'], max(numbers, default=0) + 1)
    studio.write_json(index_path(directory), index)


def unregister(root, directory, key):
    index = read_index(root, directory)
    if key in index['operations']:
        index['operations'].remove(key)
        studio.write_json(index_path(directory), index)


def current(client, saved):
    """Fresh inline view, after proving accepted text, formatting and the planned comments are unchanged."""
    inline, accepted = rt.read_views(client, saved['document_id'])
    if gs.signature(accepted) != saved['before_sha256']:
        raise GoogleError('Google changed; refresh the review before posting comments.')
    if build(inline, saved['findings'], saved['tab_ids'], first_number(saved)) != saved['comment_plan']:
        raise GoogleError('The comment plan differs from current Google content; no comments posted.')
    return inline


def read_threads(client, saved, backend):
    if backend == 'native-comments':
        doc = gs.review_read(client, saved['document_id'])
        anchors = gs.native_anchors(doc)
        return [{'id': thread.get('commentId'), 'content': thread.get('headPost', {}).get('content'),
                 'quote': thread.get('plainTextQuote'), 'resolved': thread.get('status') == 'RESOLVED',
                 'ranges': [r for anchor in anchors if anchor['anchorId'] == thread.get('anchorId') for r in anchor['ranges']]}
                for thread in doc.get('comments', [])]
    return [{'id': thread.get('id'), 'content': thread.get('content'),
             'quote': thread.get('quotedFileContent', {}).get('value'), 'resolved': thread.get('resolved', False),
             'deleted': thread.get('deleted', False), 'mine': thread.get('author', {}).get('me', False)}
            for thread in client.review_comments(saved['document_id'])]


def matches(thread, expected, backend):
    if not thread.get('id') or thread.get('deleted') or thread.get('content') != expected['content']:
        return False
    if backend != 'native-comments':
        return thread.get('quote') == expected['quote']
    in_range = any(all(r.get(k) == v for k, v in expected['range'].items()) for r in thread.get('ranges', []))
    return gs.quote_matches(thread.get('quote'), expected['quote']) and in_range


def finding_ids(saved, comment):
    by_number = {entry['number']: entry['finding']['id'] for entry in saved['comment_plan']['entries']}
    return [by_number[number] for number in comment['numbers']]


def posted(saved, comment, threads):
    """A planned comment is already in the Doc when a live thread carries all of its finding markers."""
    wanted = [marker(finding_id) for finding_id in finding_ids(saved, comment)]
    return any(not thread.get('deleted') and all(mark in (thread.get('content') or '') for mark in wanted)
               for thread in threads)


def any_marker(saved, threads):
    wanted = [marker(finding['id']) for finding in saved['findings']]
    return any(mark in (thread.get('content') or '') for mark in wanted for thread in threads)


def may_comment(client, saved):
    return client.metadata(saved['document_id']).get('capabilities', {}).get('canComment') is True


def create_comment(client, saved, comment, receipt, receipt_path, sleep):
    """Post one Drive comment. Rate limits are waited out; any other refusal is recorded as not posted."""
    for wait in (*RATE_LIMIT_WAITS, None):
        try:
            return client.create_review_comment(saved['document_id'], comment['content'], comment['quote'])
        except GoogleError as exc:
            if exc.rate_limited and wait is not None:
                sleep(wait)
                continue
            if exc.definite:
                # Google answered with a refusal, so this comment does not exist and can be sent on resume.
                receipt.pop('pending_comment', None)
                receipt['not_posted'] = {'numbers': comment['numbers'], 'status': exc.status}
                write_json(receipt_path, receipt)
                raise GoogleError('The comment for ' + label(comment['numbers']) + ' was not posted: ' + str(exc)
                                  + ' Earlier comments are in place. Run apply again to post the rest.',
                                  status=exc.status, labels=exc.labels) from None
            raise GoogleError('The comment for ' + label(comment['numbers']) + ' has an uncertain result: ' + str(exc)
                              + ' Run apply again; it posts only comments that are missing from the Doc.') from None


def require_unchanged_inputs(directory, record, target, saved):
    kind = saved['kind']
    if (target['document_id'] != saved['document_id'] or target['tab_ids'] != saved['tab_ids']
            or digest(encoded(record['google']['baselines'][kind])) != saved['baseline_sha256']
            or studio.artifact_fingerprint(directory, kind.upper() + '.md') != saved['local_sha256']):
        raise GoogleError('Local writing or linked baseline changed; refresh before sending review comments.')


def apply(client, root, saved, reserved=False, repost_missing=False, sleep=time.sleep):
    """Post the planned comments once. A repeated call resumes an interrupted batch by its in-Doc markers."""
    directory, record, target = gs.linked(root, saved['article'], saved['kind'])
    require_unchanged_inputs(directory, record, target, saved)
    store = gs.ledger(root)
    key = gs.operation_key(saved)
    again = 'Review already attempted; verify the existing result instead of reposting.'
    with locked(store):
        receipt_path = path(root, saved)
        markers = gs.marker_paths(store, saved)
        resuming = False
        if reserved:
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('status') != 'native-rejected' or receipt.get('operation') != key:
                raise GoogleError('An uncertain submission cannot switch to comments.')
        elif receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if not receipt.get('backend') or receipt.get('status') != 'submitting-comments':
                raise GoogleError(again)
            resuming = True
        elif any(mark.exists() for mark in markers):
            raise GoogleError(again)
        doc = current(client, saved)
        if not resuming and doc['revisionId'] != saved['revision_id']:
            raise GoogleError('Google changed after planning; refresh findings before posting.')
        if resuming:
            backend = receipt['backend']
        else:
            backend = 'native-comments'
            try:
                gs.review_read(client, saved['document_id'])
            except GoogleError as exc:
                if not unavailable(exc):
                    raise
                backend = 'drive-comments'
        # List the selected surface before sending, including resolved findings.
        existing = read_threads(client, saved, backend)
        if not resuming and any_marker(saved, existing):
            raise GoogleError('These findings already have review comments. Reconcile instead of reposting.')
        if backend == 'drive-comments' and not may_comment(client, saved):
            raise GoogleError('Google has not confirmed comment permission. Keep the review locally.')
        if studio.artifact_fingerprint(directory, saved['kind'].upper() + '.md') != saved['local_sha256']:
            raise GoogleError('Local writing changed during preflight.')
        if not resuming:
            register(root, directory, saved, key)
            receipt = {'status': 'submitting-comments', 'operation': key, 'document_id': saved['document_id'],
                       'backend': backend, 'posted': [], 'applied': []}
            if reserved:
                write_json(receipt_path, receipt)
            else:
                write_new(receipt_path, encoded(receipt))
                for mark in markers:
                    write_new(mark, key.encode())
            gs.keep_plan(store, saved)
        batch = {'client': client, 'root': root, 'directory': directory, 'saved': saved, 'receipt': receipt,
                 'receipt_path': receipt_path, 'resuming': resuming, 'repost_missing': repost_missing}
        if backend == 'native-comments':
            backend = post_native(batch, existing, doc)
            existing = []  # After a fallback the Drive surface was just checked for these findings.
        if backend == 'drive-comments':
            post_drive(batch, existing, sleep)
    return verify(client, root, saved)


def mark_submitted(batch):
    batch['receipt']['status'] = 'comments-submitted'
    write_json(batch['receipt_path'], batch['receipt'])


def post_native(batch, existing, doc):
    """One request of anchored native comments. Returns 'drive-comments' when Google needs the fallback."""
    client, saved, receipt = batch['client'], batch['saved'], batch['receipt']
    planned = saved['comment_plan']['comments']
    missing = [comment for comment in planned if not posted(saved, comment, existing)]
    if not missing:
        mark_submitted(batch)
        return None
    if batch['resuming'] and len(missing) == len(planned) and not batch['repost_missing']:
        raise GoogleError('The earlier comment request had an uncertain result and none of its comments are visible '
                          'yet. Check Google Docs; if they are absent, run apply again with --repost-missing.')
    requests = [{'insertComment': {'content': comment['content'], 'range': comment['range']}} for comment in missing]
    try:
        response = client.native_comments_update(saved['document_id'], doc['revisionId'], requests)
    except GoogleError as exc:
        if unavailable(exc):
            # Definite rejection only. No fallback following timeout/partial success.
            current(client, saved)
            receipt['backend'] = 'drive-comments'
            if any_marker(saved, read_threads(client, saved, 'drive-comments')):
                raise GoogleError('A review comment already exists; reconcile before continuing.')
            write_json(batch['receipt_path'], receipt)
            return 'drive-comments'
        if exc.definite and len(missing) == len(planned):
            # Google refused the only request, so nothing was posted and the findings stay usable.
            gs.release(batch['root'], saved)
            unregister(batch['root'], batch['directory'], gs.operation_key(saved))
            raise GoogleError(str(exc) + ' No comment was posted and this attempt was released; refresh and plan again.',
                              status=exc.status, labels=exc.labels) from None
        raise
    receipt['native_ack'] = response.get('commentUpdateState')
    mark_submitted(batch)
    return None


def post_drive(batch, existing, sleep):
    """Ordinary Drive comments, one request each, skipping any that are already in the Doc."""
    client, saved, receipt, receipt_path = batch['client'], batch['saved'], batch['receipt'], batch['receipt_path']
    if not may_comment(client, saved):
        raise GoogleError('Google has not confirmed comment permission. Keep the review locally.')
    uncertain = receipt.get('pending_comment')
    for comment in saved['comment_plan']['comments']:
        numbers = comment['numbers']
        if posted(saved, comment, existing):
            if not any(entry['numbers'] == numbers for entry in receipt['posted']):
                receipt['posted'].append({'numbers': numbers, 'recovered': True})
            if uncertain == numbers:
                receipt.pop('pending_comment', None)
                uncertain = None
            write_json(receipt_path, receipt)
            continue
        if uncertain == numbers and not batch['repost_missing']:
            raise GoogleError('The comment for ' + label(numbers) + ' had an uncertain result and is not visible in '
                              'the Doc yet. Check All Comments; if it is absent, run apply again with --repost-missing.')
        current(client, saved)
        receipt['pending_comment'] = numbers
        receipt.pop('not_posted', None)
        write_json(receipt_path, receipt)
        response = create_comment(client, saved, comment, receipt, receipt_path, sleep)
        if not response.get('id'):
            raise GoogleError('Comment result is uncertain; verify instead of reposting.')
        receipt['posted'].append({'id': response['id'], 'numbers': numbers})
        receipt.pop('pending_comment', None)
        uncertain = None
        write_json(receipt_path, receipt)
    mark_submitted(batch)


def verify(client, root, saved):
    receipt_path = path(root, saved)
    receipt = json.loads(receipt_path.read_text())
    backend = receipt['backend']
    before, _ = rt.read_views(client, saved['document_id'])
    threads = read_threads(client, saved, backend)
    after, accepted = rt.read_views(client, saved['document_id'])
    stable = before['revisionId'] == after['revisionId'] and gs.signature(accepted) == saved['before_sha256']
    results = []
    for comment in saved['comment_plan']['comments']:
        found = [thread for thread in threads if matches(thread, comment, backend)]
        only = found[0] if len(found) == 1 else None
        results.append({'numbers': comment['numbers'], 'verified': only is not None,
                        'thread_id': only['id'] if only else None,
                        'resolved': only.get('resolved', False) if only else False})
    acknowledged = receipt.get('native_ack') not in ('ALL_FAILED_UNKNOWN_REASON', 'NO_UPDATES_REQUESTED')
    good = stable and all(result['verified'] for result in results) and acknowledged
    editable = [str(entry['number']) for entry in saved['comment_plan']['entries'] if entry['finding']['kind'] == 'edit'][:2]
    if editable:
        say = 'Apply ' + ('edits ' if len(editable) > 1 else 'edit ') + ' and '.join(editable)
        next_action = 'Then say “' + say + '” for the items you choose.'
    else:
        next_action = 'Discuss the feedback before deciding on wording.'
    if good:
        message = ('Added ' + str(len(saved['findings'])) + ' proposed edits in ' + str(len(results))
                   + ' comments. Your document text is unchanged.')
    elif receipt.get('status') == 'submitting-comments' and stable:
        message = 'Some review comments are not posted yet. Run apply again; it posts only the missing ones.'
    else:
        message = 'Review posting is incomplete or Google changed. Inspect existing comments; do not repost.'
    where = 'Open Google Docs' + (' → All Comments' if backend == 'drive-comments' else '') + '. '
    result = {'status': 'verified-comments' if good else 'needs-reconciliation', 'mode': backend,
              'accepted_text_unchanged': stable, 'comments': results, 'operation': gs.operation_key(saved),
              'message': message, 'next_step': where + next_action}
    receipt['verification'] = result
    write_json(receipt_path, receipt)
    return result


def show(root, article_id):
    """Every review batch posted for this blog from this computer, with blog-wide edit numbers."""
    directory, _ = studio.item(root, 'articles', article_id)
    reviews = []
    edits = []
    for key in read_index(root, directory)['operations']:
        batch = load_batch(root, key)
        if not batch:
            continue
        plan_path, saved, receipt = batch
        applied = receipt.get('applied', [])
        rows = [{'number': entry['number'], 'section': entry['section'], 'current': entry['finding']['before'],
                 'proposed': entry['finding'].get('after'), 'reason': entry['finding']['reason'],
                 'applied': entry['number'] in applied, 'plan': str(plan_path)}
                for entry in saved['comment_plan']['entries']]
        reviews.append({'plan': str(plan_path), 'operation': gs.operation_key(saved), 'mode': receipt.get('backend'),
                        'status': receipt.get('verification', {}).get('status', receipt.get('status')),
                        'applied': applied, 'edits': rows})
        edits.extend(rows)
    if not reviews:
        raise GoogleError('No review comments have been posted for this blog from this computer. '
                          'Numbered edits can be applied only where their review was posted.')
    latest = reviews[-1]
    return {'plan': latest['plan'], 'operation': latest['operation'], 'mode': latest['mode'], 'status': latest['status'],
            'applied': sorted(number for review in reviews for number in review['applied']),
            'edits': edits, 'reviews': reviews}


def require_selection(numbers):
    if not numbers or len(set(numbers)) != len(numbers) or any(type(number) is not int for number in numbers):
        raise GoogleError('Select unique edit numbers from this review.')


def apply_selected(client, root, article_id, numbers):
    """Apply numbered edits by blog. Numbers are unique per blog, so each one names exactly one batch."""
    require_selection(numbers)
    directory, _ = studio.item(root, 'articles', article_id)
    groups = []
    for key in read_index(root, directory)['operations']:
        batch = load_batch(root, key)
        chosen = [number for number in numbers if batch and number in numbers_of(batch[1])]
        if chosen:
            groups.append((batch[1], chosen))
    known = {number for _, chosen in groups for number in chosen}
    if known != set(numbers):
        unknown = ', '.join(str(number) for number in numbers if number not in known)
        raise GoogleError('Unknown edit number(s) ' + unknown + '. Use show-review to list this blog’s numbered edits.')
    results = [apply_edits(client, root, saved, chosen) for saved, chosen in groups]
    if len(results) == 1:
        return results[0]
    done = all(result['status'] == 'applied' for result in results)
    return {'status': 'applied' if done else 'applied-comments-unresolved', 'applied': sorted(numbers),
            'batches': results, 'next_step': PULL_NEXT}


def verified_threads(receipt):
    return {tuple(comment['numbers']): comment['thread_id'] for comment in receipt['verification']['comments']}


def live_thread(threads, receipt, comment):
    """The verified thread for a planned comment, if it is still there with the same text."""
    wanted = verified_threads(receipt).get(tuple(comment['numbers']))
    found = [thread for thread in threads
             if thread.get('id') == wanted and thread.get('content') == comment['content'] and not thread.get('deleted')]
    return found[0] if len(found) == 1 else None


def paragraph_edits(doc, entries, selected, receipt, numbers):
    """Whole-paragraph before/after for each paragraph touched by the selected edits."""
    edits = []
    applied = receipt.get('applied', [])
    for key in dict.fromkeys((entry['finding']['tab_id'], entry['paragraph_start']) for entry in selected):
        group = [entry for entry in entries if (entry['finding']['tab_id'], entry['paragraph_start']) == key]
        original = group[0]['paragraph']

        def projected(chosen):
            text = original
            for entry in sorted(group, key=lambda item: item['finding']['start_index'], reverse=True):
                if entry['number'] not in chosen:
                    continue
                finding = entry['finding']
                start = gs.position(original, finding['start_index'] - key[1])
                text = text[:start] + finding['after'] + text[start + len(finding['before']):]
            return text

        before = projected(applied)
        after = projected(set(applied) | set(numbers))
        found = [where for where, paragraph in rt.paragraphs(doc).items()
                 if where[0] == key[0] and rt.paragraph_text(paragraph) == before + '\n']
        if len(found) != 1:
            raise GoogleError('Google wording moved ambiguously or changed; refresh these findings.')
        edits.append({'tab_id': key[0], 'start_index': found[0][1], 'before': before, 'after': after})
    return edits


def apply_edits(client, root, saved, numbers):
    """Caller supplies the user's explicit selection; thread resolution is not approval."""
    require_selection(numbers)
    receipt_path = path(root, saved)
    with locked(gs.ledger(root)):
        receipt = json.loads(receipt_path.read_text())
        if receipt.get('verification', {}).get('status') != 'verified-comments':
            raise GoogleError('Verify the posted review comments before applying selected edits.')
        if receipt.get('edit_attempt'):
            raise GoogleError('An edit attempt needs reconciliation; use verify-edits, never repeat the write.')
        directory, _, target = gs.linked(root, saved['article'], saved['kind'])
        if target['document_id'] != saved['document_id'] or target['tab_ids'] != saved['tab_ids']:
            raise GoogleError('The linked Google document changed.')
        draft = saved['kind'].upper() + '.md'
        local = studio.artifact_fingerprint(directory, draft)
        entries = saved['comment_plan']['entries']
        selected = [entry for entry in entries if entry['number'] in numbers]
        if len(selected) != len(numbers) or any(entry['finding']['kind'] != 'edit' for entry in selected):
            raise GoogleError('Choose text-edit numbers; broader feedback needs an explicit wording decision.')
        if any(number in receipt.get('applied', []) for number in numbers):
            raise GoogleError('An edit was already applied.')
        doc = rt.inline_read(client, saved['document_id'])
        threads = read_threads(client, saved, receipt['backend'])
        for comment in saved['comment_plan']['comments']:
            if set(comment['numbers']) & set(numbers) and live_thread(threads, receipt, comment) is None:
                raise GoogleError('A selected review comment changed or disappeared; refresh the review.')
        planned = rt.build_plan(doc, paragraph_edits(doc, entries, selected, receipt, numbers))
        if studio.artifact_fingerprint(directory, draft) != local:
            raise GoogleError('Local writing changed during preflight.')
        # The state before the write is kept so a lost response can later be settled either way.
        receipt['edit_attempt'] = {'numbers': numbers, 'expected_sha256': planned['expected_sha256'],
                                   'before_sha256': rt.fingerprint(doc)}
        write_json(receipt_path, receipt)
        try:
            client.native_update(saved['document_id'], doc['revisionId'], planned['requests'])
        except GoogleError as exc:
            if exc.definite:
                receipt.pop('edit_attempt')
                write_json(receipt_path, receipt)
            raise
        if rt.verify(client, planned)['status'] != 'verified':
            raise GoogleError('Google wording or formatting could not be verified. Keep the comments open; do not retry.')
        return finish_edits(client, saved, receipt, receipt_path, numbers)


def finish_edits(client, saved, receipt, receipt_path, numbers):
    """Record verified edits, then resolve only the comments whose edits are now all applied."""
    receipt['applied'] = sorted(set(receipt.get('applied', [])) | set(numbers))
    receipt.pop('edit_attempt', None)
    write_json(receipt_path, receipt)
    backend = receipt['backend']
    resolved = []

    def unresolved(step):
        return {'status': 'applied-comments-unresolved', 'applied': numbers, 'resolved_comments': resolved,
                'next_step': step}

    # Resolve only fully applied groups, never comments containing pending edits.
    for comment in saved['comment_plan']['comments']:
        if not set(comment['numbers']) <= set(receipt['applied']):
            continue
        try:
            threads = read_threads(client, saved, backend)
        except GoogleError:
            return unresolved('Edits are verified, but comments could not be read. Do not repeat the edits.')
        thread = live_thread(threads, receipt, comment)
        if thread is None:
            return unresolved('Edits are verified; inspect changed or missing comments. Do not repeat the edits.')
        if thread.get('resolved'):
            continue
        if receipt.get('resolving') == thread['id']:
            return unresolved('An earlier resolution is uncertain; inspect it without repeating the request.')
        if backend == 'drive-comments' and not thread.get('mine'):
            return unresolved('Edits are verified; this account cannot resolve another author’s comment. '
                              'Pull the latest document.')
        receipt['resolving'] = thread['id']
        write_json(receipt_path, receipt)
        try:
            if backend == 'drive-comments':
                client.resolve_review_comment(saved['document_id'], thread['id'])
            else:
                latest = rt.inline_read(client, saved['document_id'])
                client.resolve_native_comment(saved['document_id'], thread['id'], latest['revisionId'])
            check = read_threads(client, saved, backend)
            if not any(item['id'] == thread['id'] and item.get('resolved') for item in check):
                raise GoogleError('Resolution could not be verified.')
        except GoogleError:
            return unresolved('Edits are verified. Inspect unresolved comments and pull the latest document; '
                              'do not repeat the edits.')
        resolved.append(thread['id'])
        receipt.pop('resolving', None)
        write_json(receipt_path, receipt)
    return {'status': 'applied', 'applied': numbers, 'resolved_comments': resolved, 'next_step': PULL_NEXT}


def verify_edits(client, root, saved):
    """Settle an edit whose response never arrived, and record the outcome so later edits can proceed."""
    receipt_path = path(root, saved)
    with locked(gs.ledger(root)):
        receipt = json.loads(receipt_path.read_text())
        attempt = receipt.get('edit_attempt')
        if not attempt:
            raise GoogleError('No uncertain edit attempt to verify.')
        now = rt.fingerprint(rt.inline_read(client, saved['document_id']))
        if now == attempt['expected_sha256']:
            # The write landed exactly as planned: record it and finish what a normal apply would have done.
            finished = finish_edits(client, saved, receipt, receipt_path, attempt['numbers'])
            status = 'applied-text-verified' if finished['status'] == 'applied' else finished['status']
            return {**finished, 'status': status, 'numbers': attempt['numbers']}
        if attempt.get('before_sha256') and now == attempt['before_sha256']:
            # The Doc is exactly as it was before the attempt, so nothing was written.
            receipt.pop('edit_attempt')
            write_json(receipt_path, receipt)
            return {'status': 'not-applied', 'numbers': attempt['numbers'],
                    'next_step': 'The earlier edit did not reach Google and was cleared. Apply the edits again when ready.'}
        return {'status': 'needs-reconciliation', 'numbers': attempt['numbers'],
                'next_step': 'Google matches neither the planned result nor the earlier text. Inspect the Doc and its '
                             'comments; do not repeat the write.'}
