"""Purpose-led Blog Studio research through the shared reviewed-bundle contract."""

import hashlib
import json
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

from studio_core import model_profiles, research_contract


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
            if 'reference' in source['purposes'] and source['status'] == 'ready':
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

        def invoke(phase, guidance, data, offered, fetch):
            # Only the parent fetches and pins bytes; generated source text is never evidence.
            data['sources'] = [
                {k: s[k] for k in ('file', 'origin', 'title', 'text')} for s in sources
            ]
            data['source_limits'] = gaps
            answer = call(
                phase,
                data,
                guidance + '\n\nReturn the requested JSON in content. '
                'The parent runs the helper. Use only the captured sources supplied here; '
                'their full saved text is the original readable capture. '
                'Selected source permission is selected; public captures are public. '
                'Do not invent sources or claim live currency from a hash.',
            )
            return answer['content'], sources

        saved = research_contract.snapshot()
        if saved != run.get('research_contract'):
            raise ValueError(
                'Restore the saved Harness Research version before continuing this blog.'
            )
        research_contract.Workflow().run(directory, task, invoke, sources)
        research_contract.publish(directory / research_contract.CASE, directory / 'research')
        return {
            'content': (directory / 'research/report.md').read_text(),
            'notes': 'Independent evidence and prose review completed for the saved research digest. '
            'The authored brief, evidence, source limitations and digest are retained in research/.',
        }
