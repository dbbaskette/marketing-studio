"""Purpose-led Blog Studio research through the shared reviewed-bundle contract."""

import hashlib
import json
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

from studio_core import model_profiles, research_contract


def offered(source):
    """Whether research reads a selected source: a readable reference or uploaded file,
    never an example of the kind of post, which shows a shape and supplies no facts."""
    purposes = source['purposes']
    return (
        ('reference' in purposes or 'material' in purposes)
        and 'inspiration' not in purposes
        and source['status'] == 'ready'
    )


def generate(directory, run, payload, worker, *, seconds, stop):
    import blog_library
    from performance import extract

    started = time.monotonic()

    def call(phase, data, guidance, web=False):
        if stop.is_set():
            raise ValueError('Research stopped. Saved work is kept.')
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError('Research reached its time limit. The saved draft is kept.')
        selection = model_profiles.route(
            run,
            'Blog Studio',
            'research-' + phase,
            purpose='review' if phase == 'review' else 'research',
        )
        return worker(
            run['engine'],
            data,
            guidance,
            seconds=max(1, int(remaining)),
            web=web,
            stop=stop,
            model_selection=selection,
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

        for source in payload['sources']:
            if offered(source):
                capture(
                    'sources/' + source['id'] + '.txt',
                    source['origin'],
                    source['text'],
                    source['name'],
                    True,
                )
        allowed = payload['research_policy'] == 'web-allowed'
        brief = run['brief']
        task = {
            'topic': payload['title'],
            'audience': brief.get('audience') or 'Blog readers',
            'purpose': 'Inform a blog: '
            + (brief.get('goal') or 'explain the topic')
            + '. Prioritize the central argument, mechanisms and strongest objections.',
            'scope': 'Evidence, objections and qualifications for the blog goal: '
            + (brief.get('goal') or 'explain the topic'),
            'brief': brief,
            'manuscript': payload['documents'].get('manuscript'),
            'planning_document': payload['documents'].get('research-plan'),
            'requested_changes': payload.get('changes'),
            'source_mode': ('mixed' if sources else 'public') if allowed else 'selected',
        }
        gaps = []
        if allowed:
            discovery = call(
                'discovery',
                {'task': task},
                'Find primary public sources for this investigation using generic '
                'nonconfidential queries. Return content as JSON {"urls": ["https://..."]}. '
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
            for url in dict.fromkeys(urls):
                if stop.is_set() or time.monotonic() - started >= seconds:
                    raise ValueError(
                        'Research stopped or reached its time limit. Saved work is kept.'
                    )
                try:
                    parsed = urlsplit(blog_library.canonical(url))
                    content, origin, kind = blog_library.fetch(
                        url, 'https://' + parsed.netloc + '/', deadline=started + seconds
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
                    gaps.append({'url': url, 'reason': str(error)})

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
                                'Research could not produce valid evidence and report data after one correction attempt. Your manuscript and source access are unchanged. Retry research or continue editing locally.'
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
        return {
            'content': (directory / 'research/report.md').read_text(),
            'notes': 'Independent evidence and prose review completed for the saved research digest. '
            'The authored brief, evidence, source limitations and digest are retained in research/.',
        }
