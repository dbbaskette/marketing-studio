"""Purpose-led Blog Studio research through the shared reviewed-bundle contract."""

import hashlib
import json
from pathlib import Path
import tempfile
import time
from studio_core import model_profiles, research_contract, research_sites, research_view


def offered(source):
    """Whether research reads a selected source: a readable reference or uploaded file,
    never an example of the kind of post, which shows a shape and supplies no facts."""
    purposes = source['purposes']
    return (
        ('reference' in purposes or 'material' in purposes)
        and 'inspiration' not in purposes
        and source['status'] == 'ready'
    )


KINDS = ('facts', 'findings', 'prose')
# The run says how long a step may take; the research's limit covers all its rounds.
OUT_OF_TIME = 'Research ran out of the time a step may take.'


def research_from(payload):
    """Where this research may look: the run's saved choice, or, for a run saved before
    the choice had three parts, its research policy (supplied-only: your documents;
    web-allowed: your documents and the public web)."""
    chosen = payload.get('research_from')
    if not isinstance(chosen, dict):
        chosen = research_sites.legacy(payload.get('research_policy'))
    return research_sites.effective(chosen or {})


def grouped(case):
    """What the last saved check objected to, grouped by kind and verdict: each group's
    count, its first note and a few of its IDs, largest first within a kind, then the
    assessment when it asks for revision. Empty when the check said nothing readable."""
    try:
        review = json.loads((Path(case) / 'review.json').read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(review, dict):
        return []
    groups = []
    for kind in KINDS:
        found = {}
        for item in review.get(kind) or ():
            if not isinstance(item, dict) or item.get('verdict') in (None, 'supported'):
                continue
            verdict = str(item['verdict'])[:40]
            group = found.setdefault(
                verdict, {'kind': kind, 'verdict': verdict, 'count': 0, 'note': '', 'ids': []}
            )
            group['count'] += 1
            if item.get('id') and len(group['ids']) < 5:
                group['ids'].append(str(item['id'])[:80])
            note = ' '.join(str(item.get('note') or '').split())
            if note and not group['note']:
                group['note'] = research_contract.shortened(note, 300)
        groups += sorted(found.values(), key=lambda group: -group['count'])
    assessment = review.get('assessment')
    if isinstance(assessment, dict):
        asked = [
            name for name in ('coverage', 'usefulness') if assessment.get(name) == 'needs-revision'
        ]
        if asked:
            note = ' '.join(str(assessment.get('note') or '').split())
            groups.append(
                {
                    'kind': 'assessment',
                    'verdict': 'needs-revision',
                    'count': 1,
                    'note': research_contract.shortened(note, 300) if note else '',
                    'ids': [],
                    'asked': asked,
                }
            )
    return groups


def refusal_groups(refusal, case):
    """The refusal's own grouping when the shared contract gives one, else the case's."""
    given = getattr(refusal, 'groups', None)
    if isinstance(given, list) and given:
        # The shared formatter provides titles and counts, while this page needs the
        # original kind and verdict. Recover those from the same saved check.
        if any(isinstance(group, dict) and not group.get('kind') for group in given):
            detailed = grouped(case)
            if detailed:
                return detailed
        groups = []
        for group in given:
            if not isinstance(group, dict) or type(group.get('count')) is not int:
                groups = []
                break
            note = group.get('note') or (group.get('notes') or [''])[0]
            groups.append(
                {
                    'kind': str(group.get('kind') or 'objections')[:40],
                    'verdict': str(group.get('verdict') or '')[:40],
                    'count': group['count'],
                    'note': research_contract.shortened(str(note or ''), 300),
                    'ids': [str(ident)[:80] for ident in (group.get('ids') or [])[:5]],
                    **({'asked': list(group['asked'])} if group.get('asked') else {}),
                }
            )
        if groups:
            return groups
    return grouped(case)


def generate(directory, run, payload, worker, *, seconds, stop, progress=None):
    """Research the blog in `directory` and publish its reviewed bundle there. `progress`,
    when given, hears {'round', 'phase'} as each job starts (round 0 is public source
    discovery, before the first author) and {'job': ...} as each ends, with its seconds and
    the tokens and dollars its CLI reported."""
    import blog_library
    import blog_worker
    from performance import extract

    started = time.monotonic()
    rounds = [0]  # Author rounds so far; the shared contract allows ROUNDS of them.

    def tell(event):
        if progress is not None:
            progress(event)

    def call(phase, data, guidance, web=False):
        if stop.is_set():
            raise ValueError('Research stopped. Saved work is kept.')
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise blog_worker.WorkerFailure(OUT_OF_TIME, 'time-limit')
        selection = model_profiles.route(
            run,
            'Blog Studio',
            'research-' + phase,
            purpose='review' if phase == 'review' else 'research',
        )
        tell({'round': rounds[0], 'phase': phase})
        began, outcome = time.monotonic(), 'failed'
        with blog_worker.metered() as jobs:
            try:
                answer = worker(
                    run['engine'],
                    data,
                    guidance,
                    seconds=max(1, int(remaining)),
                    web=web,
                    stop=stop,
                    model_selection=selection,
                )
                outcome = 'kept'
                return answer
            finally:
                tokens = [job['tokens'] for job in jobs if job['tokens'] is not None]
                dollars = [job['dollars'] for job in jobs if job['dollars'] is not None]
                tell(
                    {
                        'job': {
                            'phase': phase,
                            'round': rounds[0],
                            'seconds': round(time.monotonic() - began, 1),
                            'tokens': sum(tokens) if tokens else None,
                            'dollars': round(sum(dollars), 4) if dollars else None,
                            'outcome': outcome,
                        }
                    }
                )

    sources = []
    with tempfile.TemporaryDirectory(prefix='blog-research-captures-') as scratch:
        folder = Path(scratch)

        def capture(name, origin, text, title, selected):
            path = folder / (hashlib.sha256(name.encode()).hexdigest() + '.txt')
            path.write_text(text)
            sources.append(
                {
                    'file': name,
                    'path': path,
                    'text': text,
                    'title': title,
                    'origin': origin,
                    'url': origin,
                    'offered': selected,
                }
            )

        chosen = research_from(payload)
        for source in payload['sources'] if chosen['documents'] else ():
            if offered(source):
                capture(
                    'sources/' + source['id'] + '.txt',
                    source['origin'],
                    source['text'],
                    source['name'],
                    True,
                )
        # Your documents count only when there are some to read.
        chosen = research_sites.effective(chosen, bool(sources))
        allowed = research_sites.fetches(chosen)
        brief = run['brief']
        task = {
            'topic': payload['title'],
            'audience': brief.get('audience') or 'Blog readers',
            'purpose': research_contract.purpose(
                'a blog',
                brief.get('goal') or 'explain the topic',
                'Prioritize the central argument, mechanisms and strongest objections.',
            ),
            'scope': 'Evidence, objections and qualifications for the blog goal: '
            + (brief.get('goal') or 'explain the topic')
            # Where it may look, for a run that saved its choice; older runs keep their words.
            + (
                '. ' + research_sites.scope_text(chosen)
                if isinstance(payload.get('research_from'), dict)
                else ''
            ),
            'brief': brief,
            'manuscript': payload['documents'].get('manuscript'),
            'planning_document': payload['documents'].get('research-plan'),
            'requested_changes': payload.get('changes'),
            'refresh': payload.get('refresh') is True,
            # Pages from your sites are public captures: documents and sites are mixed.
            'source_mode': research_sites.source_mode(chosen) if allowed else 'selected',
        }
        from blog_runner import planning_questions

        task['planning_questions'] = planning_questions(
            payload['documents'].get('research-plan') or ''
        )
        gaps = []
        if allowed:
            searching = research_sites.guidance(chosen)
            discovery = call(
                'discovery',
                {'task': task},
                'Find primary public sources for this investigation using generic '
                'nonconfidential queries. '
                + (searching + ' ' if searching else '')
                + 'Return content as JSON {"urls": ["https://..."]}. '
                'At most eight URLs. No invented citations. Do not return a report.',
                True,
            )
            urls = json.loads(discovery['content']).get('urls')
            if (
                not isinstance(urls, list)
                or len(urls) > 8
                or any(not isinstance(v, str) for v in urls)
            ):
                raise ValueError('Research source discovery returned an invalid source list.')
            # Every address and every redirect is asked whether this research may save it.
            scope, kept_out = research_sites.Scope(chosen), 0
            for url in dict.fromkeys(urls):
                if stop.is_set():
                    raise ValueError('Research stopped. Saved work is kept.')
                if time.monotonic() - started >= seconds:
                    raise blog_worker.WorkerFailure(OUT_OF_TIME, 'time-limit')
                try:
                    content, origin, kind = blog_library.fetch(
                        url, scope, deadline=started + seconds
                    )
                    suffix = (
                        '.html' if 'html' in kind else '.txt' if kind.startswith('text/') else ''
                    )
                    if not suffix:
                        raise ValueError('This public source needs a readable text version.')
                    extracted, _ = extract(directory, content, suffix)
                    text = extracted['text']
                    capture(
                        'sources/public-' + hashlib.sha256(content).hexdigest()[:24] + '.txt',
                        origin,
                        text,
                        origin,
                        False,
                    )
                except ValueError as error:
                    # A page off your sites is a source limit whose reason names them.
                    kept_out += isinstance(error, blog_library.Outside)
                    gaps.append({'url': url, 'reason': str(error)})
            if chosen['sites']:
                tell({'outside': {'count': kept_out, 'sites': list(chosen['sites'])}})

        def validate_author(value, data):
            # Validate with the actual pinned helper, in a disposable case. Never
            # coerce malformed prose or weaken citation/source checks to accept it.
            if not isinstance(value, dict):
                raise ValueError('Return a complete schema-2 dossier object.')
            for key in ('topic', 'audience', 'purpose', 'scope', 'source_mode'):
                value[key] = task[key]
            if any(f.get('author') != data['worker'] for f in value.get('facts', [])):
                raise ValueError('Every fact must identify the supplied author worker.')
            with tempfile.TemporaryDirectory(prefix='blog-research-validation-') as temp:
                case = Path(temp)
                for source in sources:
                    research_contract.write(case, source['file'], source['path'].read_bytes())
                research_contract.write(case, 'dossier.json', json.dumps(value))
                research_contract.Workflow(runtime).command(
                    case, 'save', 'dossier.json', data['worker']
                )

        def invoke(phase, guidance, data, offered, fetch):
            # Only the parent fetches and pins bytes; generated source text is never evidence.
            data['sources'] = [
                {
                    **{k: s[k] for k in ('file', 'origin', 'title', 'text')},
                    'permission': 'selected' if s['offered'] else 'public',
                }
                for s in sources
            ]
            data['source_limits'] = gaps
            if phase == 'author':
                rounds[0] += 1
                guidance += (
                    '\nDossier format: schema=2; sources, facts, findings, sections and brief '
                    'are arrays. sections and brief contain {id,title,blocks:[{text,kind,refs}]}. '
                    'kind is summary, inference, recommendation or gap. refs are fact/finding IDs. '
                    'Each fact has id, statement, author and citations:[{source,quote}]. '
                    'Each finding has id,title,summary:{text,kind,refs},support:[],counter:[], '
                    'implications:[],conditions:[],gaps:[]. Sources have id,file,origin,title,'
                    'publisher,permission,context (full or partial). Use exact captured quotes.'
                )
            answer = call(
                phase,
                data,
                guidance + '\n\nReturn the requested JSON in content. '
                'The parent runs the helper. Use only the captured sources supplied here; '
                'their full saved text is the original readable capture. '
                'Selected source permission is selected; public captures are public. '
                'Do not invent sources or claim live currency from a hash.',
            )
            if phase == 'author':
                allowed = {s['file']: s for s in data['sources']}
                for attempt in range(2):
                    try:
                        value = json.loads(answer['content'])
                        entries = value['sources']
                        if not isinstance(entries, list):
                            raise ValueError('Invalid source list')
                        for entry in entries:
                            captured = allowed.get(entry.get('file'))
                            if not captured or any(
                                entry.get(k) != captured[k] for k in ('permission', 'origin')
                            ):
                                raise ValueError('Invalid captured source metadata')
                        validate_author(value, data)
                        break
                    except (ValueError, KeyError, TypeError, AttributeError) as error:
                        if attempt:
                            raise ValueError(
                                'Research could not produce valid evidence and report data after one correction attempt. Your manuscript and source access are unchanged. Choose Try again, or Continue without research.'
                            ) from None
                        answer = call(
                            phase,
                            {
                                **data,
                                'validation_error': str(error),
                                'previous_output': answer['content'],
                            },
                            guidance
                            + '\nCorrect the validation_error in previous_output and return the complete dossier again. Copy file, origin and permission exactly from each supplied capture; do not invent or reclassify sources.',
                        )
            return answer['content'], sources

        # After an update the blog keeps the helper version it started with, while it is retained.
        runtime = research_contract.runtime_for(run.get('research_contract'))
        if runtime is None:
            raise ValueError(
                'Restore the saved Harness Research version before continuing this blog.'
            )
        research_contract.Workflow(runtime).run(directory, task, invoke, sources)
        research_contract.publish(directory / research_contract.CASE, directory / 'research')
        account = research_view.account(directory / 'research')
        check = account['check'] if account else {'said': research_view.UNCHECKED, 'note': ''}
        return {
            'content': (directory / 'research/report.md').read_text(),
            'notes': check['said'] + (' ' + check['note'] if check['note'] else ''),
        }
