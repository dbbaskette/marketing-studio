"""Blog research through the shared research component, with Blog Studio's own rules.

What a caller needs to know
---------------------------
    record = plan(root, ident, {'purpose', 'scope', 'items'})
    record = record_result(root, ident, run, item_id, {'status', 'summary', 'limits', 'evidence'})
    found = status(root, ident)

- The research itself is studio_research's: harness-research keeps the record and report in
  the article's .harness-research/ folder, the plan is research/plan.json and plan.md, and
  the article's references are snapshots in research/sources/, which stay on this computer.
- Blog Studio's rules are kept here: the article's research policy decides whether public
  research is allowed; evidence comes only from references attached to the article at their
  exact revision, which the plan was made with; fact-check claims match DRAFT.md exactly;
  a planned reference with a newer revision makes the research stale.
- A finding may carry harness-research's optional one-line `headline`.
- Research saved by Blog Studio before it used harness-research (derived/research.json with
  no .harness-research/) is reported stale and is planned again; its report stays where it
  was. No network, models, or generated code here.
"""

from pathlib import Path
import re

import studio
from studio_research import project

VERDICTS = project.VERDICTS
SCOPE_LABELS = project.SCOPES
INPUTS = ('BRIEF.md', 'OUTLINE.md', 'DRAFT.md')
LEGACY = ('derived', 'research.json')
LEGACY_REPORT = ('derived', 'research-report.md')
LEGACY_NOTE = (
    'This research was saved before Blog Studio used harness-research. Plan it again to '
    'continue; the earlier report is still at derived/research-report.md.'
)
RESULT_KEYS = {'status', 'summary', 'limits', 'evidence'}


def nonempty(value, label, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} needs nonempty text (max {limit} characters).')
    return value


def tool():
    """The installed harness-research, found when research first needs it."""
    return project.tool()


def references(root, record):
    """Each reference attached to the article, at the revision it is pinned to, as the
    documents the research component takes, keyed by (source_id, revision)."""
    from hub_workspace import portable_origin

    found = {}
    for selected in record.get('sources', []):
        if 'reference' not in selected.get('purposes', []):
            continue
        folder, source = studio.item(root, 'sources', selected['source_id'])
        current = source['revision'] == selected['revision']
        if not current:
            folder = studio.inside(folder, 'revisions', str(selected['revision']))
            source = studio.read_json(folder / 'record.json')
        path = studio.inside(folder, 'content.md')
        text = path.read_text() if path.is_file() else ''
        origin = portable_origin(source['origin'])
        found[(selected['source_id'], selected['revision'])] = {
            'title': source['name'],
            'origin': origin,
            'text': text,
            'status': source['status'],
            'key': project.key(origin, text),
            'current': current,  # False once the source has a newer revision than the pin
        }
    return found


def keep(directory, record, answered):
    """Remember where the research is, in the article's record."""
    path = directory / project.RECORD
    record['research'] = {
        'engine': 'harness-research',
        'run': answered.get('run'),
        'path': project.RECORD.as_posix(),
        'plan': project.PLAN.as_posix(),
        'report': project.HARNESS_REPORT.as_posix(),
        'sha256': studio.digest(path.read_bytes()) if path.is_file() else None,
        'updated_at': studio.now(),
    }
    studio.persist(directory, 'articles', record)
    return record


def check_plan(directory, record, supplied):
    """Blog Studio's rules for a plan; returns the questions as the component takes them."""
    if not isinstance(supplied, dict) or set(supplied) != {'purpose', 'scope', 'items'}:
        raise ValueError('Research plan needs purpose, scope and items.')
    if supplied['purpose'] not in ('planning', 'fact-check') or supplied['scope'] not in (
        'supplied-only',
        'public-web',
    ):
        raise ValueError('Choose planning/fact-check and supplied-only/public-web.')
    if supplied['scope'] == 'public-web' and record.get('research_policy') == 'supplied-only':
        raise ValueError(
            'This article is limited to supplied sources. Keep that scope or obtain an explicit policy change.'
        )
    if supplied['scope'] == 'public-web' and record.get('research_policy') != 'web-allowed':
        raise ValueError(
            'Choose uploaded sources only or uploaded sources plus external research before public lookup; save web-allowed for the latter.'
        )
    items = supplied['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValueError('Plan 1–30 focused research questions.')
    seen = set()
    draft = (directory / 'DRAFT.md').read_text() if (directory / 'DRAFT.md').is_file() else ''
    questions = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'id', 'question', 'public_query', 'claim'}:
            raise ValueError(
                'Each item needs id, question, public_query (text or null) and claim (quote/start or null).'
            )
        key = studio.identifier(item['id'])
        if key in seen:
            raise ValueError('Research item IDs must be unique.')
        seen.add(key)
        nonempty(item['question'], 'Question')
        query = item['public_query']
        if query is not None:
            nonempty(query, 'Public query', 500)
            if supplied['scope'] != 'public-web':
                raise ValueError('Supplied-only research cannot contain public queries.')
            if re.search(r'https?://|[/\\]|@', query):
                raise ValueError(
                    'Public queries cannot contain URLs, file paths or email addresses.'
                )
        claim = item['claim']
        if claim is not None:
            if (
                not isinstance(claim, dict)
                or set(claim) != {'quote', 'start'}
                or type(claim['start']) is not int
                or claim['start'] < 0
            ):
                raise ValueError(
                    'Claim needs an exact manuscript quote and nonnegative character start.'
                )
            quote = nonempty(claim['quote'], 'Claim')
            if draft[claim['start'] : claim['start'] + len(quote)] != quote:
                raise ValueError(
                    'Claim does not match this draft. Refresh its wording and location.'
                )
            claim = {'file': 'DRAFT.md', 'quote': quote, 'start': claim['start']}
        if supplied['purpose'] == 'fact-check' and claim is None:
            raise ValueError('Fact-check questions must map to an exact draft claim.')
        questions.append(
            {'id': key, 'question': item['question'], 'public_query': query, 'claim': claim}
        )
    return questions


def plan(root, ident, supplied):
    directory, record = studio.item(root, 'articles', ident)
    questions = check_plan(directory, record, supplied)
    sources = project.snapshot(directory, references(root, record).values())
    handed = project.build_plan(
        record['title'],
        supplied['purpose'],
        supplied['scope'],
        questions,
        sources,
        [name for name in INPUTS if (directory / name).is_file()],
    )
    answered = project.save_plan(
        directory, handed, allow_web=supplied['scope'] == 'public-web', research=tool()
    )
    return keep(directory, record, answered)


def plan_from_draft(root, ident, text):
    """Save a plan the guided run's worker drafted ({topic, items}), with Blog Studio's rules:
    planning research, public queries only for a web-allowed article, the article's title as
    its topic so a redrafted plan keeps the findings of unchanged questions."""
    from studio_research import steps

    _, record = studio.item(root, 'articles', ident)
    draft = steps.draft_plan(text)
    web = record.get('research_policy') == 'web-allowed'
    items = [
        {
            'id': item['id'],
            'question': item['question'],
            'public_query': item['public_query'] if web else None,
            'claim': None,
        }
        for item in draft['items']
    ]
    return plan(
        root,
        ident,
        {'purpose': 'planning', 'scope': 'public-web' if web else 'supplied-only', 'items': items},
    )


def evidence(record, citation, attached, planned):
    """One passage, checked against the attached reference it quotes, in the shape
    harness-research records. As in every studio, research cites what it was planned with."""
    required = {'source_id', 'revision', 'quote', 'start', 'locator'}
    if not isinstance(citation, dict) or set(citation) != required:
        raise ValueError('Evidence needs source_id, revision, exact quote/start and locator.')
    pinned = next(
        (
            s
            for s in record['sources']
            if s['source_id'] == citation['source_id'] and 'reference' in s['purposes']
        ),
        None,
    )
    if not pinned or pinned['revision'] != citation['revision']:
        raise ValueError('Attach this exact source revision as a factual reference first.')
    reference = attached[(citation['source_id'], citation['revision'])]
    if reference['key'] not in planned:
        raise ValueError(
            'This reference was attached after the research was planned. Plan the research again to include it.'
        )
    quote = nonempty(citation['quote'], 'Evidence quote', 12000)
    start = citation['start']
    if (
        type(start) is not int
        or start < 0
        or reference['text'][start : start + len(quote)] != quote
        or reference['status'] != 'ready'
    ):
        raise ValueError('Evidence must quote an available, pinned reference passage exactly.')
    nonempty(citation['locator'], 'Evidence location', 1000)
    return {
        'file': (project.SOURCES / (reference['key'] + '.md')).as_posix(),
        'title': reference['title'],
        'origin': reference['origin'],
        'quote': quote,
        'start': start,
        'locator': citation['locator'],
        'source_id': reference['key'],
    }


def record_result(root, ident, run, item_id, supplied):
    directory, record = studio.item(root, 'articles', ident)
    saved = project.read_record(directory)
    if saved is None:
        raise ValueError('Plan the research before recording results.')
    if saved.get('scope') == 'public-web' and record.get('research_policy') == 'supplied-only':
        raise ValueError(
            'This article is now limited to supplied sources. Refresh the plan with that scope.'
        )
    attached = references(root, record)
    project.snapshot(directory, attached.values())
    research = tool()
    current = project.status(directory, research)
    if current['run'] != run or current['status'] == 'stale':
        raise ValueError(
            'Research plan changed or manuscript is stale. Refresh the plan before recording results.'
        )
    if item_id not in {i['id'] for i in saved.get('items', [])}:
        raise ValueError('Unknown research item.')
    if (
        not isinstance(supplied, dict)
        or not RESULT_KEYS <= set(supplied) <= RESULT_KEYS | {'headline'}
        or supplied['status'] not in VERDICTS
    ):
        raise ValueError('Result needs status, summary, limits and evidence.')
    nonempty(supplied['summary'], 'Research summary', 12000)
    nonempty(supplied['limits'], 'Coverage limits', 4000)
    if not isinstance(supplied['evidence'], list) or len(supplied['evidence']) > 20:
        raise ValueError('Use at most 20 exact passages per item.')
    planned = project.planned(directory)
    citations = [evidence(record, c, attached, planned) for c in supplied['evidence']]
    if supplied['status'] in ('supported', 'contradicted') and not citations:
        raise ValueError(
            'Supported/contradicted research requires a traceable passage; missing evidence stays unresolved.'
        )
    answered = project.record(
        directory, run, item_id, {**supplied, 'evidence': citations}, research
    )
    return keep(directory, record, answered)


def status(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    saved = project.read_record(directory)
    if saved is None:
        if studio.inside(directory, *LEGACY).is_file():
            return {
                'id': ident,
                'status': 'stale',
                'legacy': True,
                'report': str(studio.inside(directory, *LEGACY_REPORT)),
                'note': LEGACY_NOTE,
            }
        return {'id': ident, 'status': 'not-started'}
    planned = project.planned(directory)
    try:
        attached = references(root, record)
        project.snapshot(directory, attached.values())
    except (ValueError, OSError):
        attached = None  # a reference that cannot be read is a gap harness-research reports
    found = project.status(directory, tool())
    stale = found['status'] == 'stale' or attached is None
    stale |= saved.get('scope') == 'public-web' and record.get('research_policy') == 'supplied-only'
    stale |= any(r['key'] in planned and not r['current'] for r in (attached or {}).values())
    scope = saved.get('scope')
    return {
        **found,
        'id': ident,
        'status': 'stale' if stale else found['status'],
        'purpose': saved.get('purpose'),
        'scope': scope,
        'scope_label': SCOPE_LABELS.get(scope, scope),
        'report': str(directory / project.HARNESS_REPORT),
        'file': str(directory / project.RECORD),
        'plan': str(directory / project.PLAN),
        'engine': 'harness-research',
        'assessment': 'Research coverage only; does not mark the factual-support review current.',
    }


def add_parser(groups):
    actions = groups.add_parser('research').add_subparsers(dest='action', required=True)
    for action in ('plan', 'record', 'status'):
        p = actions.add_parser(action)
        p.add_argument('--id', required=True)
        if action != 'status':
            p.add_argument('--file', required=True)
        if action == 'record':
            p.add_argument('--run', required=True)
            p.add_argument('--item', required=True)


def command(root, args):
    if args.action == 'status':
        return status(root, args.id)
    value = studio.read_json(Path(args.file))
    if args.action == 'plan':
        return plan(root, args.id, value)
    return record_result(root, args.id, args.run, args.item, value)
