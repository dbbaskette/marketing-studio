"""A Google Docs suggest-mode model closer than ReviewProvider, for the desk's Google sends:
one character list per body; a suggested line break splits its paragraph in the inline view
and a deleted break merges paragraphs once accepted (the surviving break's paragraph
properties win); an inline object is one character; inserted text takes its left
neighbour's style until updateTextStyle. Single tab, no tables. No live Google."""

import copy

import google_roundtrip as rt
import google_drive as gd
from test_google_suggestions import ReviewProvider


def u16(c):
    return rt.utf16(c)


PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00'
    b'\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe'
    b'\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82'
)


class Model(ReviewProvider):
    def __init__(self, doc, markdown=None):
        super().__init__()
        self.markdown = markdown
        self.images = {}  # contentUri: bytes; an address left out is not sent
        self.load(doc)

    def image(self, uri):
        if uri not in self.images:
            raise gd.GoogleError('Google did not send this image.', network=True)
        return self.images[uri]

    def teammate(self, words, before, ident='teammate', delete=None):
        """A teammate's pending suggestion: `words` inserted before the first `before`, and
        `delete` (words right after it) suggested for deletion."""
        text = ''.join(item['ch'] for item in self.items)
        at = text.index(before)
        if delete:
            gone = text.index(delete, at)
            for item in self.items[gone : gone + len(delete)]:
                item['del'] = ident + '-d'
            self.threads.append({'suggestionId': ident + '-d', 'status': 'OPEN'})
        style = self.items[at]['style']
        self.items[at:at] = [
            {'ch': c, 'style': dict(style), 'ins': ident, 'del': None} for c in words
        ]
        self.threads.append({'suggestionId': ident, 'status': 'OPEN'})
        self.rev += 1

    def load(self, doc):
        self.base = copy.deepcopy(doc)
        tab = self.base['tabs'][0]
        body = tab['documentTab']['body']['content']
        self.head = [b for b in body if 'sectionBreak' in b][:1]
        assert all('paragraph' in b or 'sectionBreak' in b for b in body), 'tables unsupported'
        items = []
        for b in body:
            if 'paragraph' not in b:
                continue
            p = b['paragraph']
            props = {k: v for k, v in p.items() if k != 'elements'}
            for e in p['elements']:
                if 'textRun' in e:
                    run = e['textRun']
                    for c in run['content']:
                        it = {
                            'ch': c,
                            'style': copy.deepcopy(run.get('textStyle', {})),
                            'ins': None,
                            'del': None,
                        }
                        if c == '\n':
                            it['para'] = copy.deepcopy(props)
                        items.append(it)
                else:
                    obj = {k: v for k, v in e.items() if k not in ('startIndex', 'endIndex')}
                    items.append({'ch': '￼', 'obj': obj, 'style': {}, 'ins': None, 'del': None})
        self.items = items
        self.doc = self.render('inline')
        self.doc['revisionId'] = doc.get('revisionId', 'r1')
        self.rev = 1

    # --- views -------------------------------------------------------------------------
    def render(self, mode):
        items = self.items
        if mode == 'without':
            items = [i for i in items if not i['ins']]
        elif mode == 'accepted':
            items = [i for i in items if not i['del']]
        blocks = copy.deepcopy(self.head) or [{'startIndex': 0, 'endIndex': 1, 'sectionBreak': {}}]
        at = 1
        current = []
        for it in items:
            current.append(it)
            if it['ch'] == '\n':
                blocks.append(self._para(current, at, mode))
                at = blocks[-1]['endIndex']
                current = []
        assert not current, 'text after the final break'
        doc = {k: copy.deepcopy(v) for k, v in self.base.items() if k != 'tabs'}
        tab = copy.deepcopy({k: v for k, v in self.base['tabs'][0].items() if k != 'documentTab'})
        dt = {
            k: copy.deepcopy(v)
            for k, v in self.base['tabs'][0]['documentTab'].items()
            if k != 'body'
        }
        dt['body'] = {'content': blocks}
        tab['documentTab'] = dt
        doc['tabs'] = [tab]
        return doc

    def _para(self, items, start, mode):
        props = copy.deepcopy(items[-1]['para'])
        elements = []
        at = start
        for it in items:
            n = u16(it['ch'])
            keep = mode == 'inline'
            if 'obj' in it:
                e = {'startIndex': at, 'endIndex': at + n, **copy.deepcopy(it['obj'])}
                if keep and (it['ins'] or it['del']):
                    key = next(iter(e.keys() - {'startIndex', 'endIndex'}))
                    if it['ins']:
                        e[key]['suggestedInsertionIds'] = [it['ins']]
                    if it['del']:
                        e[key]['suggestedDeletionIds'] = [it['del']]
                elements.append(e)
            else:
                sig = (
                    repr(sorted(it['style'].items())),
                    it['ins'] if keep else None,
                    it['del'] if keep else None,
                )
                last = elements[-1] if elements else None
                if last and 'textRun' in last and last['_sig'] == sig:
                    last['textRun']['content'] += it['ch']
                    last['endIndex'] += n
                else:
                    run = {'content': it['ch'], 'textStyle': copy.deepcopy(it['style'])}
                    if keep and it['ins']:
                        run['suggestedInsertionIds'] = [it['ins']]
                    if keep and it['del']:
                        run['suggestedDeletionIds'] = [it['del']]
                    elements.append(
                        {'startIndex': at, 'endIndex': at + n, 'textRun': run, '_sig': sig}
                    )
            at += n
        for e in elements:
            e.pop('_sig', None)
        return {'startIndex': start, 'endIndex': at, 'paragraph': {**props, 'elements': elements}}

    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        mode = 'inline' if inline else 'accepted' if accepted_preview else 'without'
        doc = self.render(mode)
        doc['revisionId'] = 'r' + str(self.rev)
        doc['suggestionsViewMode'] = (
            'SUGGESTIONS_INLINE'
            if inline
            else 'PREVIEW_SUGGESTIONS_ACCEPTED'
            if accepted_preview
            else 'PREVIEW_WITHOUT_SUGGESTIONS'
        )
        if comments:
            doc.update(
                commentsViewMode='COMMENTS_VIEW_MODE_INCLUDED',
                comments=copy.deepcopy(self.comments),
                suggestions=copy.deepcopy(self.threads),
            )
            doc['tabs'][0]['documentTab']['commentAnchors'] = copy.deepcopy(self.anchors)
        self.doc = self.render('inline')
        self.doc['revisionId'] = doc['revisionId']
        return doc

    def export(self, file_id, format):
        if format == 'md' and self.markdown is not None:
            return self.markdown.encode()
        return super().export(file_id, format)

    # --- writes ------------------------------------------------------------------------
    def _pos(self, index):
        """List position of the item starting at UTF-16 index (1-based body)."""
        at = 1
        for i, it in enumerate(self.items):
            if at == index:
                return i
            at += u16(it['ch'])
            if at > index:
                raise AssertionError('index splits a character: ' + str(index))
        if at == index:
            return len(self.items)
        raise AssertionError('index outside body: ' + str(index))

    def native_review_update(self, file_id, revision, requests):
        if 'r' + str(self.rev) != revision:
            raise gd.GoogleError('stale revision')
        self.writes += 1
        for req in requests:
            if 'insertComment' in req:
                c = req['insertComment']
                r = c['range']
                a, b = self._pos(r['startIndex']), self._pos(r['endIndex'])
                quote = ''.join(it['ch'] for it in self.items[a:b])
                cid = 'c' + str(len(self.comments))
                self.comments.append(
                    {
                        'commentId': cid,
                        'anchorId': 'a' + cid,
                        'headPost': {'content': c['content']},
                        'status': 'OPEN',
                        'plainTextQuote': quote,
                    }
                )
                self.anchors.append({'anchorId': 'a' + cid, 'ranges': [r]})
                continue
            if 'insertText' in req:
                x = req['insertText']
                p = self._pos(x['location']['index'])
                assert 0 <= p <= len(self.items) - 1, 'insert after the final break'
                sid = 's' + str(len(self.threads))
                self.threads.append({'suggestionId': sid, 'status': 'OPEN'})
                # Left neighbour's style (or right one at a paragraph start).
                left = self.items[p - 1] if p and self.items[p - 1]['ch'] != '\n' else self.items[p]
                style = copy.deepcopy(left['style'])
                # The paragraph being split: its break, at or after p.
                brk = next(it for it in self.items[p:] if it['ch'] == '\n')
                new = []
                for c in x['text']:
                    it = {'ch': c, 'style': copy.deepcopy(style), 'ins': sid, 'del': None}
                    if c == '\n':
                        it['para'] = copy.deepcopy(brk['para'])
                    new.append(it)
                self.items[p:p] = new
                continue
            if 'deleteContentRange' in req:
                r = req['deleteContentRange']['range']
                a, b = self._pos(r['startIndex']), self._pos(r['endIndex'])
                assert b > a
                assert b < len(self.items) or self.items[-1]['ch'] != '\n', 'final break deleted'
                sid = 's' + str(len(self.threads))
                self.threads.append({'suggestionId': sid, 'status': 'OPEN'})
                for it in self.items[a:b]:
                    if it['ins']:
                        raise AssertionError('deleting a pending insertion')
                    it['del'] = sid
                continue
            if 'updateTextStyle' in req:
                x = req['updateTextStyle']
                r = x['range']
                a, b = self._pos(r['startIndex']), self._pos(r['endIndex'])
                assert x['fields'] == '*'
                for it in self.items[a:b]:
                    it['style'] = copy.deepcopy(x['textStyle'])
                continue
            raise AssertionError(req)
        self.rev += 1
        return {'commentUpdateState': 'ALL_SAVED'}

    # --- review helpers ---------------------------------------------------------------
    def decide(self, accept_ids=None, reject_ids=None):
        """Accept or reject our suggestions by id (None = all)."""
        out = []
        for it in self.items:
            ins, dele = it['ins'], it['del']
            if ins:
                if accept_ids is None or ins in accept_ids:
                    it['ins'] = None
                elif reject_ids is None or ins in reject_ids:
                    continue
            if dele:
                if accept_ids is None or dele in accept_ids:
                    continue
                elif reject_ids is None or dele in reject_ids:
                    it['del'] = None
            out.append(it)
        # Merged paragraphs: a deleted break's paragraph takes the surviving break's props (already so).
        self.items = out
        for t in self.threads:
            if t['status'] == 'OPEN':
                sid = t['suggestionId']
                if accept_ids is None or sid in accept_ids:
                    t['status'] = 'ACCEPTED'
                elif reject_ids is None or sid in reject_ids:
                    t['status'] = 'REJECTED'
        self.rev += 1


def styled_paragraphs(doc):
    """[(kind, [(char, (bold, italic, link))])] of a native view."""
    out = []
    for b in doc['tabs'][0]['documentTab']['body']['content']:
        if 'paragraph' not in b:
            continue
        p = b['paragraph']
        named = p.get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
        kind = (
            'heading ' + named[-1]
            if named.startswith('HEADING')
            else ('bullet' if 'bullet' in p else 'text')
        )
        chars = []
        for e in p['elements']:
            if 'textRun' not in e:
                chars.append(('￼', None))
                continue
            st = e['textRun'].get('textStyle', {})
            for c in e['textRun']['content']:
                chars.append(
                    (
                        c,
                        (
                            bool(st.get('bold')),
                            bool(st.get('italic')),
                            (st.get('link') or {}).get('url'),
                        ),
                    )
                )
        out.append((kind, chars))
    return out


def reindex(blocks):
    """Indexes for body blocks whose paragraphs may hold objects, one index each."""
    start = 1
    for block in blocks:
        if 'paragraph' not in block:
            continue
        block['startIndex'] = start
        for element in block['paragraph']['elements']:
            element['startIndex'] = start
            start += rt.utf16(element['textRun']['content']) if 'textRun' in element else 1
            element['endIndex'] = start
        block['endIndex'] = start


def run(text, **style):
    return {'textRun': {'content': text, 'textStyle': style}}


def objects_doc():
    """A synthetic Doc with what blogs hold besides text: two images (one in a paragraph with
    words), a smart chip, a person chip, a page break, a line break, a footnote and a bold
    heading."""
    paragraphs = [
        ({'namedStyleType': 'NORMAL_TEXT'}, [run('An opening paragraph about harbours.\n')]),
        (
            {'namedStyleType': 'NORMAL_TEXT'},
            [{'inlineObjectElement': {'inlineObjectId': 'kix.one'}}, run('\n')],
        ),
        (
            {'namedStyleType': 'NORMAL_TEXT'},
            [
                run('See the chart '),
                {'inlineObjectElement': {'inlineObjectId': 'kix.two'}},
                run(' for the trend.\n'),
            ],
        ),
        ({'namedStyleType': 'HEADING_3'}, [run('Key Patterns\n', bold=True)]),
        (
            {'namedStyleType': 'NORMAL_TEXT'},
            [
                run('Read the '),
                {
                    'richLink': {
                        'richLinkId': 'r1',
                        'richLinkProperties': {
                            'title': 'Harbour plan',
                            'uri': 'https://docs.google.com/document/d/plan',
                        },
                    }
                },
                run(' with '),
                {
                    'person': {
                        'personId': 'p1',
                        'personProperties': {'name': 'Ada Lovelace', 'email': 'ada@example.com'},
                    }
                },
                run(' first.\n'),
            ],
        ),
        ({'namedStyleType': 'NORMAL_TEXT'}, [run('Line one\x0bline two of one paragraph.\n')]),
        (
            {'namedStyleType': 'NORMAL_TEXT'},
            [run('A page ends here.'), {'pageBreak': {}}, run('\n')],
        ),
        (
            {'namedStyleType': 'NORMAL_TEXT'},
            [
                run('Tides vary'),
                {'footnoteReference': {'footnoteId': 'f1', 'footnoteNumber': '1'}},
                run(' by season.\n'),
            ],
        ),
        ({'namedStyleType': 'NORMAL_TEXT'}, [run('We keep the plan simple and clear.\n')]),
        ({'namedStyleType': 'NORMAL_TEXT'}, [run('The end.\n')]),
    ]
    blocks = [{'startIndex': 0, 'endIndex': 1, 'sectionBreak': {}}]
    for style, elements in paragraphs:
        blocks.append({'paragraph': {'paragraphStyle': style, 'elements': elements}})
    reindex(blocks)

    def image(uri, title=''):
        return {
            'inlineObjectProperties': {
                'embeddedObject': {'title': title, 'imageProperties': {'contentUri': uri}}
            }
        }

    native = {
        'body': {'content': blocks},
        'inlineObjects': {
            'kix.one': image('https://lh3.googleusercontent.com/one'),
            'kix.two': image('https://lh3.googleusercontent.com/two', 'A trend chart'),
        },
        'footnotes': {
            'f1': {'content': [{'paragraph': {'elements': [run('Measured at noon.\n')]}}]}
        },
    }
    return {
        'documentId': 'fixture-doc',
        'revisionId': 'r1',
        'title': 'Harbour notes',
        'tabs': [{'tabProperties': {'tabId': 't.0', 'title': 'Notes'}, 'documentTab': native}],
    }
