"""Existing Google manuscript intake for the authenticated Blog Studio page."""

import re
import uuid
from urllib.parse import urlsplit

import google_drive as drive
import google_roundtrip as roundtrip
import google_workflow as workflow
from editorial import mapping
import studio
from manuscript_preview import text_only


def document_id(value):
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError('Paste a Google Doc link or document ID.')
    value = value.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{1,200}', value):
        return drive.identifier(value)
    parsed = urlsplit(value)
    match = re.fullmatch(r'/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{1,200})(?:/.*)?', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc != 'docs.google.com' or not match:
        raise ValueError('Use an https://docs.google.com/document/d/… link or document ID.')
    return drive.identifier(match[1])


def linked(root, file_id):
    matches = []
    for path in sorted(studio.inside(root, 'articles').iterdir()):
        if not path.is_dir() or path.name.startswith('.'):
            continue
        _, record = studio.item(root, 'articles', path.name)
        baselines = mapping(mapping(record.get('google')).get('baselines'))
        if any(
            mapping(mapping(base).get('document')).get('document_id') == file_id
            for base in baselines.values()
        ):
            matches.append(record)
    if len(matches) > 1:
        raise ValueError('Several blogs link to this Doc. Choose the saved blog before continuing.')
    if matches:
        record = matches[0]
        return {
            'status': 'already-linked',
            'id': record['id'],
            'title': record['title'],
            'linked_document': 'https://docs.google.com/document/d/' + file_id + '/edit',
        }
    return None


def material(root, value):
    """Read a Google Doc as one of a blog's files: its title, link and text. The capture is
    read with this computer's Google sign-in and nothing of it stays in staging."""
    file_id = document_id(value)
    folder = studio.inside(drive.staging_root(root, create=True), 'material-' + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    try:
        snapshot = folder / 'snapshot'
        roundtrip.capture(drive.Client(drive.account_for(root)), file_id, None, snapshot)
        body = (snapshot / 'document.md').read_text()
        native = studio.read_json(snapshot / 'native.json')
    finally:
        drive.discard(root, folder)
    text = text_only(body)
    if not text.strip():
        raise ValueError('This Google Doc has no text to read.')
    title = ' '.join(str(native.get('title') or '').split())[:200] or 'Google Doc'
    link = 'https://docs.google.com/document/d/' + file_id + '/edit'
    return {'title': title, 'link': link, 'markdown': body, 'text': text}


def fingerprint(snapshot):
    return drive.digest(
        drive.encoded(
            {
                name: studio.read_json(snapshot / name)
                for name in ('snapshot.json', 'observation.json')
            }
        )
    )


def preview(root, data):
    if set(data) != {'url'}:
        raise ValueError('Provide only the Google Doc link to preview.')
    file_id = document_id(data['url'])
    existing = linked(root, file_id)
    if existing:
        return existing
    token = uuid.uuid4().hex
    folder = studio.inside(drive.staging_root(root, create=True), 'desk-' + token)
    folder.mkdir(mode=0o700)
    snapshot = folder / 'snapshot'
    try:
        result = roundtrip.capture(drive.Client(drive.account_for(root)), file_id, None, snapshot)
        body = (snapshot / 'document.md').read_text()
        content = text_only(body)
        if not content.strip() or len(content) > 200_000:
            raise ValueError('Choose a readable Google manuscript up to 200,000 characters.')
        native = studio.read_json(snapshot / 'native.json')
        title = str(native.get('title') or 'Google Doc')[:500]
        value = {
            'status': 'preview',
            'preview': token,
            'title': title,
            'linked_document': 'https://docs.google.com/document/d/' + file_id + '/edit',
            'summary': result['summary'],
            'expected': fingerprint(snapshot),
        }
        studio.write_json(folder / 'preview.json', value)
        return {**value, 'content': content, 'images_omitted': content != body}
    except BaseException:
        drive.discard(root, folder)
        raise


def start(root, data):
    if set(data) != {'preview', 'expected', 'title', 'confirmed'} or data['confirmed'] is not True:
        raise ValueError(
            'Preview the Doc and confirm that the manuscript matches before importing.'
        )
    token = data['preview']
    if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{32}', token):
        raise ValueError('Choose a Google Doc preview from this workspace.')
    folder = studio.inside(drive.staging_root(root), 'desk-' + token)
    path = folder / 'preview.json'
    if not path.is_file():
        raise ValueError('This Google Doc preview expired. Preview the link again.')
    saved = studio.read_json(path)
    if not isinstance(data['expected'], str) or data['expected'] != saved['expected']:
        raise ValueError('This preview changed. Preview the Google Doc again before importing.')
    if saved.get('result'):
        return saved['result']
    existing = linked(root, document_id(saved['linked_document']))
    if existing:
        drive.discard(root, folder / 'snapshot')
        saved['result'] = existing
        studio.write_json(path, saved)
        return existing
    title = data['title']
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
        raise ValueError('Use a blog title between 1 and 500 characters.')
    snapshot = folder / 'snapshot'
    if fingerprint(snapshot) != saved['expected']:
        raise ValueError('This capture changed. Preview the Google Doc again before importing.')
    observation = studio.read_json(snapshot / 'observation.json')
    # The page has shown the manuscript and structure summary. This explicit
    # confirmation satisfies the same inspection requirement as the chat route.
    observation['structure_verified'] = True
    studio.write_json(snapshot / 'observation.json', observation)
    args = studio.parser().parse_args(
        [
            '--root',
            str(root),
            'google',
            'start',
            '--title',
            title.strip(),
            '--snapshot',
            str(snapshot),
        ]
    )
    try:
        result = workflow.start(root, args)
    except BaseException:
        if snapshot.is_dir():
            observation['structure_verified'] = False
            studio.write_json(snapshot / 'observation.json', observation)
        raise
    public = {key: result[key] for key in ('id', 'title', 'status', 'linked_document')}
    from management import share, receipt

    if result['status'] == 'started-from-google':
        _, record = studio.item(root, 'articles', result['id'])
        shared = share(root, 'article', record)
        public['receipts'] = [receipt(root, 'Google manuscript', shared, 'article')]
    saved['result'] = public
    studio.write_json(path, saved)
    return public
