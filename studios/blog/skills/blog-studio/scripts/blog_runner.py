"""One blog pipeline shared by conversation guidance and the local browser runner."""

import json
import difflib
import os
from pathlib import Path
import re
import shutil
import threading
import tempfile
import time
from types import SimpleNamespace
import uuid

import studio
import blog_worker
import editorial
import claims_map
from studio_core import (
    model_profiles,
    research_contract,
    research_sites,
    research_view,
    review_policy,
    stops,
)
from studio_core.preferences import ready as shared_ready

APPLY_REQUEST = (
    'Apply only the findings in the review below. Edit only the passages they name; '
    "change nothing else. Keep the author's voice, qualifiers, numbers, links and quotations."
)
STATE = 'derived/blog-run.json'
# A from-files run embeds the uploaded files; past this many JSON characters of source
# text, each file is excerpted to its share and the run says which ones were.
SOURCE_BUDGET = 240_000
STAGES = {
    'angles': (
        'Angles',
        'derived/blog-angles.md',
        'Read the uploaded files and the author’s note about them. Propose three distinct blog '
        'angles the files can support. Return each as a `## Title` heading followed by one '
        'line in this shape: the audience · the point it makes · Leans on <file names>. '
        'Say which files were excerpted or have no text. Do not outline or draft the blog.',
    ),
    'research-plan': (
        'Research questions',
        'derived/blog-research-plan.md',
        'Plan focused research questions for the brief. Say what evidence is needed.',
    ),
    'research': (
        'Research findings',
        'derived/blog-research.md',
        'Research the approved questions. Cite evidence, contradictions and unanswered questions. '
        'With supplied sources only, use only those sources. Explicitly label missing evidence.',
    ),
    'claims-map': (
        'Claims in your material',
        'derived/blog-claims-map.md',
        'List each claim the supplied material makes, with the source that makes it and its exact passage. Judge none of them and do not research.',
    ),
    'outline': (
        'Outline',
        'OUTLINE.md',
        'Make an argument outline: reader problem, thesis, section purpose, evidence, caveats and ending.',
    ),
    'draft': (
        'Draft',
        'DRAFT.md',
        'Write the blog from the approved outline, evidence and voice. Avoid invented author experience.',
    ),
    'review': (
        'Review',
        'derived/blog-review.md',
        'Review the saved draft for factual support, argument, voice and wording. '
        'List actionable findings with passages and proposed changes. Do not rewrite the draft. '
        'Distinguish your judgment from completed mechanical checks; unresolved facts stay unresolved.',
    ),
    'package': (
        'Handoff',
        'derived/blog-package.md',
        'Prepare a publication handoff: selected title, alternative titles, excerpt, suggested '
        'description, links to check and unresolved review findings. Do not publish anything.',
    ),
}
GUIDES = {
    'angles': 'modules/blog-argument-outline.md',
    'claims-map': 'modules/blog-claims-map.md',
    'research-plan': 'modules/blog-research-plan.md',
    'research': 'modules/blog-deep-research.md',
    'outline': 'modules/blog-argument-outline.md',
    'draft': 'modules/blog-write.md',
    'review': 'modules/copy-editing.md',
    'package': 'modules/blog-repurpose.md',
}
ENGINES = {}
DEFAULTS = {
    'engine': 'codex',
    'seconds': 600,
    # Where research looks for a new blog: your documents, your sites (the shared list) and
    # the public web. None ticked is no research.
    'research': {'documents': True, 'sites': False, 'web': False},
    'tone': 'Clear, conversational and specific',
    'author': '',
}
MODES = ('write', 'outline', 'from-outline', 'ideas', 'revise', 'review', 'from-files')
# How long new writing runs, beside its kind of post: the usual length by default. It names
# no style and no capability, so it reads true for any kind of post, chosen or not.
LENGTHS = {
    'style': '',
    'short': 'Length: about half the usual length for this kind of post. Keep each main '
    'point’s what and why; cut secondary detail before any qualifier.',
    'deep': 'Length: about twice the usual length for this kind of post, with one worked '
    'example or proof point from the material for each main point. Develop; do not pad or '
    'invent.',
}
# Length takes effect only where an outline or a draft is written new.
NO_LENGTH = (
    'Length is for new writing, so a review, a revision or three ideas takes none. '
    'Nothing was started.'
)
MATERIAL_ELSEWHERE = (
    'This blog’s uploaded files stay on the computer that added them. Continue it there, '
    'or start it again here from your files.'
)
# Research that stopped before its check accepted it (refused, out of time, a failed job) is
# kept beside the blog for Try again: the draft dossier, the check's last review and the
# captures they cite. It stays on this computer: the Team Hub skips dot folders, and the
# folder's own ignore file keeps it out of a shared studios repository. Its kept.json ties it
# to the research stage it came from: that stage's input pin and saved version. Research saved
# any other way (chat, a teammate, a handover) or changed inputs let it go.
RESEARCH_DRAFT = Path('.studio-research-draft')
DRAFT_TIE = 'kept.json'
DRAFT_ONLY = ('.gitignore', DRAFT_TIE)  # Never handed on into a research case.


def private(folder):
    """Readable by this account only: folders 0700, files 0600."""
    folder.chmod(0o700)
    for parent, folders, files in os.walk(folder, followlinks=False):
        for name in folders:
            (Path(parent) / name).chmod(0o700)
        for name in files:
            (Path(parent) / name).chmod(0o600)


def keep_research(directory, case, tie):
    """Keep `case` as the blog's research draft, tied to `tie` (the research stage's pin and
    saved version) and replacing an earlier one. True when kept, False when the case saved
    nothing to continue from, or the reason it could not be kept; then no older draft is
    left either, so a message saying so stays true."""
    for leftover in directory.glob(RESEARCH_DRAFT.name + '-*'):
        # What an interrupted keep left behind.
        if (
            re.fullmatch(r'[0-9a-f]{32}', leftover.name[len(RESEARCH_DRAFT.name) + 1 :])
            and leftover.is_dir()
            and not leftover.is_symlink()
        ):
            shutil.rmtree(leftover, ignore_errors=True)
    if not (case / '.harness-research' / 'synthesis.json').is_file():
        return False
    kept = directory / RESEARCH_DRAFT
    pending = directory / (RESEARCH_DRAFT.name + '-' + uuid.uuid4().hex)
    try:
        pending.mkdir(mode=0o700)
        (pending / '.gitignore').write_text('*\n')  # Ignored before anything else lands.
        research_contract.copy_case(case, pending)
        for name in DRAFT_ONLY[1:]:
            (pending / name).unlink(missing_ok=True)
        tie = tie or {}
        (pending / DRAFT_TIE).write_text(
            json.dumps(
                {
                    'schema': 1,
                    'basis': tie.get('basis'),
                    'hash': tie.get('hash'),
                    'at': studio.now(),
                }
            )
        )
        private(pending)
        if kept.exists():
            shutil.rmtree(kept)
        pending.rename(kept)
        return True
    except (OSError, ValueError) as error:
        shutil.rmtree(kept, ignore_errors=True)
        return str(error)[:160] or 'it could not be copied'
    finally:
        shutil.rmtree(pending, ignore_errors=True)


def research_draft(directory, tie):
    """Whether the blog's kept research draft still belongs to its research stage."""
    draft = directory / RESEARCH_DRAFT
    if not tie or not (draft / '.harness-research' / 'synthesis.json').is_file():
        return False
    try:
        saved = json.loads((draft / DRAFT_TIE).read_text())
    except (OSError, ValueError):
        return False
    return (
        isinstance(saved, dict)
        and saved.get('basis') == tie['basis']
        and saved.get('hash') == tie['hash']
    )


def fitted(said, then='', limit=500):
    """`said` and `then` within the limit an error keeps, cutting `said` rather than `then`."""
    room = limit - (len(then) + 1 if then else 0)
    if len(said) > room:
        said = said[: max(0, room - 1)].rstrip() + '…'
    return (said + ' ' + then).strip() if then else said


def outside_words(outside):
    """'2 pages were outside your sites (...) and were not saved.', or None."""
    if not isinstance(outside, dict) or type(outside.get('count')) is not int:
        return None
    listed = [site for site in outside.get('sites') or () if isinstance(site, str)]
    return research_sites.outside(max(0, outside['count']), listed)


def research_refusal(refusal, case):
    """What the independent check objected to, for the run screen: counts by kind and
    verdict with the first note of each, and the cause when the contract names one."""
    import synthesis_research

    groups = synthesis_research.refusal_groups(refusal, case)[:12]
    cause = getattr(refusal, 'cause', None)
    return {
        'rounds': getattr(refusal, 'rounds', research_contract.ROUNDS),
        'count': sum(group['count'] for group in groups),
        'groups': groups,
        'cause': research_contract.shortened(str(cause), 300) if cause else None,
        'at': studio.now(),
    }


def refusal_words(refusal):
    if refusal['cause']:
        return refusal['cause']
    said = (
        'The research check still objected after '
        + str(refusal['rounds'])
        + ' rounds of writing and checking'
    )
    if not refusal['count']:
        return said + ', and did not say what.'
    count, groups = refusal['count'], len(refusal['groups'])
    return (
        f'{said}: {count} objection'
        + ('' if count == 1 else 's')
        + f' in {groups} group'
        + ('' if groups == 1 else 's')
        + '.'
    )


FAILURES = ('cli', 'time-limit', 'research-check')


def said_path(root, ident):
    """Where this computer keeps what a blog's last failed CLI wrote to stderr."""
    return studio.inside(
        root, '.blog-runs', 'diagnostics', 'cli', studio.identifier(ident) + '.json'
    )


def keep_said(root, ident, stage, engine_name, said):
    """Keep the last lines a failed CLI wrote, readable by this account only, beside the
    run's other local state: never in the blog's folder, a Team Hub or a shared repository."""
    path = said_path(root, ident)
    for folder in (path.parent.parent, path.parent):
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.chmod(0o700)
    studio.write_json(
        path,
        {
            'schema': 1,
            'at': studio.now(),
            'stage': stage,
            'engine': engine_name,
            # Redacted again here: whatever raised the failure, no secret or prompt is kept.
            'said': [
                blog_worker.secretless(str(line))[:500]
                for line in said
                if 'DOCUMENT DATA' not in str(line)
            ][-blog_worker.SAID_LINES :],
        },
    )
    path.chmod(0o600)


def read_said(root, ident):
    try:
        path = said_path(root, ident)
        said = studio.read_json(path).get('said') if path.is_file() else None
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(said, list):
        return None
    return [line for line in said if isinstance(line, str)][-blog_worker.SAID_LINES :] or None


def research_cost(jobs):
    """What the last research attempt took: its jobs, rounds and seconds, with tokens and
    dollars only when the CLI reported them for every job. None before any job ended."""
    if not isinstance(jobs, list) or not jobs:
        return None

    def total(key):
        values = [job.get(key) for job in jobs]
        if any(not isinstance(value, (int, float)) for value in values):
            return None
        return round(sum(values), 4) if key == 'dollars' else sum(values)

    return {
        'jobs': len(jobs),
        'rounds': max((job.get('round') or 0) for job in jobs),
        'seconds': round(sum(float(job.get('seconds') or 0) for job in jobs), 1),
        'tokens': total('tokens'),
        'dollars': total('dollars'),
        # Jobs whose CLI reported tokens or dollars, so a partial count can be said as one.
        'reported': sum(
            any(isinstance(job.get(key), (int, float)) for key in ('tokens', 'dollars'))
            for job in jobs
        ),
    }


def research_kept_words(kept, refused):
    """What happened to the research made so far, in a sentence for the stop message."""
    if kept is True:
        return (
            'The draft report and the check’s notes are kept on this computer; Try again '
            'continues from them.'
            if refused
            else 'The research so far is kept on this computer; Try again continues from it.'
        )
    if kept:
        return (
            'The draft could not be kept here ('
            + kept
            + '), so Try again starts the research again.'
        )
    return ''


RESEARCH_DEFAULT = (
    'Choose where research may look for new blogs: your documents, your sites and/or the '
    'public web, or none of them for no research.'
)
# The words research used before it had three parts, for a writing default saved then.
OLD_RESEARCH = ('none', 'supplied-only', 'web-allowed')
# Only Harness Research checks each saved page against your sites. Without it, research
# would be one job with the assistant's open web search, so your sites alone are refused.
NEEDS_HARNESS_RESEARCH = (
    'Research from your sites needs Harness Research, which this computer does not have. '
    'Open Status to see how to add it, or tick the public web.'
)


def searches_web(payload):
    """Whether a plain research job may use the assistant's web search: only when its
    research may look on the public web. Your sites alone never open it; a run saved before
    research_from keeps its policy."""
    if payload.get('research_policy') != 'web-allowed':
        return False
    chosen = payload.get('research_from')
    return bool(chosen.get('web')) if isinstance(chosen, dict) else 'research_from' not in payload


def research_default(value):
    """The writing default for research: whether a new blog researches your documents,
    your sites and the public web. Older words read as they were meant."""
    if value in OLD_RESEARCH:
        found = research_sites.legacy(value) or {}
        return {
            'documents': bool(found.get('documents')),
            'sites': False,
            'web': bool(found.get('web')),
        }
    if (
        not isinstance(value, dict)
        or set(value) != {'documents', 'sites', 'web'}
        or any(type(member) is not bool for member in value.values())
    ):
        raise ValueError(RESEARCH_DEFAULT)
    return dict(value)


def research_words():
    """The sentences the desk start says when its research choice is incomplete."""
    return {
        'empty': research_sites.EMPTY,
        'no_documents': research_sites.NO_DOCUMENTS,
        'no_sites': research_sites.NO_SITES,
    }


def settings(root, data=None):
    """Shared settings come only from studios config; writing limits stay local."""
    import studios_config

    path = studio.inside(root, '.blog-run-settings.json')
    migration_notice, migration_problem = studios_config.migrate(root)
    shared, read_problem = studios_config.read()
    shared_problem = read_problem or migration_problem
    saved = studio.read_json(path) if path.is_file() else {}
    private = {
        key: value
        for key, value in saved.get('defaults', {}).items()
        if key in DEFAULTS and key not in ('engine', 'author')
    }
    try:
        private['research'] = research_default(private.get('research', DEFAULTS['research']))
    except ValueError:
        private['research'] = dict(DEFAULTS['research'])
    base = {**DEFAULTS, **private}
    agent = shared.get('assistant', {}).get('agent')
    name = shared.get('person', {}).get('name')
    if agent in ('codex', 'claude'):
        base['engine'] = agent
    if isinstance(name, str) and len(name) <= 200:
        base['author'] = name
    import writing_defaults

    features = studio.features(root)
    if data is not None:
        data = dict(data)
        # Blog Studio's own switches, saved with the form when it shows them, checked
        # against what it showed; a form that does not show them keeps what is saved.
        features_given = 'features' in data
        if features_given:
            if 'features_before' not in data:
                raise ValueError('Reload the displayed settings before saving these switches.')
            shown_features = data.pop('features_before')
            wanted = data.pop('features')
            if (
                not isinstance(wanted, dict)
                or set(wanted) != set(studio.FEATURES)
                or any(type(value) is not bool for value in wanted.values())
            ):
                raise ValueError('Choose on or off for each switch.')
            if shown_features != features:
                raise ValueError(
                    'These switches changed since these settings were shown. Reload the '
                    'settings before saving.'
                )
            features = dict(wanted)
        elif 'features_before' in data:
            raise ValueError('Save the displayed writing settings only.')
        # The personal default voice: a confirmed profile at a revision, or none. It lives in
        # the private writing defaults, beside the other personal values, never in a Hub. It
        # is checked with the rest of the form, against the voice the form showed, and saved
        # only once the shared settings are, so a refused form changes nothing.
        voice_given = 'voice' in data
        voice = data.pop('voice', None)
        if voice_given and not features['voice']:
            raise ValueError(studio.VOICES_OFF)  # The default voice is an older voice tool.
        if voice_given:
            if 'voice_before' not in data:
                raise ValueError('Reload the displayed settings before saving the default voice.')
            shown = data.pop('voice_before')
            current = writing_defaults.personal(root)['values'].get('voice')
            if shown != (current if isinstance(current, dict) else None):
                raise ValueError(
                    'The default voice changed since these settings were shown. Reload the '
                    'settings before saving.'
                )
            if voice is not None and not (
                isinstance(voice, dict) and set(voice) == {'profile_id', 'revision'}
            ):
                raise ValueError('Choose a listed voice, or none.')
            if voice is not None and not any(
                found['id'] == voice['profile_id']
                for found in writing_defaults.confirmed_voices(root)
            ):
                raise ValueError('Choose a confirmed voice for the default, or none.')
        elif 'voice_before' in data:
            raise ValueError('Save the displayed writing settings only.')
        before = data.pop(
            'shared_before',
            {
                'engine': shared.get('assistant', {}).get('agent'),
                'author': shared.get('person', {}).get('name'),
            },
        )
        if not isinstance(before, dict) or set(before) != {'engine', 'author'}:
            raise ValueError('Reload the displayed shared settings before saving.')
        if set(data) != set(DEFAULTS):
            raise ValueError('Save the displayed writing settings only.')
        if data['engine'] not in ('codex', 'claude'):
            raise ValueError('Choose a listed assistant.')
        data['research'] = research_default(data['research'])
        if type(data['seconds']) is not int or not 30 <= data['seconds'] <= 3600:
            raise ValueError('Choose a step limit between 30 and 3600 seconds.')
        for key, maximum in (('tone', 2000), ('author', 200)):
            text(data[key], key, maximum)
        changes = {}
        displayed_engine = (
            before['engine'] if before['engine'] in ('codex', 'claude') else DEFAULTS['engine']
        )
        if data['engine'] != displayed_engine:
            changes['assistant'] = {'agent': data['engine']}
        if data['author'] != (before['author'] or DEFAULTS['author']):
            changes['person'] = {'name': data['author']}
        expected = {}
        if 'assistant' in changes:
            expected['assistant'] = {'agent': before['engine']}
        if 'person' in changes:
            expected['person'] = {'name': before['author']}
        shared = studios_config.update(changes, expected=expected)
        private = {key: value for key, value in data.items() if key not in ('engine', 'author')}
        studio.write_json(path, {'schema': 1, 'defaults': private, 'features': features})
        if voice_given:
            writing_defaults.set_personal(root, 'voice', voice)
        base = {
            **data,
            'engine': shared.get('assistant', {}).get('agent')
            if shared.get('assistant', {}).get('agent') in ('codex', 'claude')
            else DEFAULTS['engine'],
            'author': shared.get('person', {}).get('name') or DEFAULTS['author'],
        }
        saved = {'defaults': private}
    review_level = review_policy.effective(shared, read_problem)
    personal = writing_defaults.personal(root)['values'].get('voice')
    return {
        'configured': bool(saved) or shared_ready(shared),
        'defaults': base,
        'voice': personal if isinstance(personal, dict) else None,
        'voices': writing_defaults.confirmed_voices(root),
        'features': studio.features(root),
        'review_level': review_level,
        'shared_before': {
            'engine': shared.get('assistant', {}).get('agent'),
            'author': shared.get('person', {}).get('name'),
        },
        'shared_problem': shared_problem,
        'migration_notice': migration_notice,
        'workspace': str(root),
        # Your sites: the shared list, edited in Shared settings. A start form offers it,
        # and a site added there is for that blog only.
        'research_sites': research_sites.defaults(shared),
        'research_words': research_words(),
    }


def text(value, label, maximum=2000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'Use {label} text up to {maximum} characters.')
    return value.strip()


def load(root, ident):
    directory, record = studio.item(root, 'articles', ident)
    path = studio.inside(directory, STATE)
    if not path.is_file():
        raise ValueError('This blog has no step-by-step run. Open it from Blogs.')
    run = studio.read_json(path)
    if run.get('schema') not in (1, 2, 3) or run.get('approval') not in ('page', 'conversation'):
        raise ValueError('This run needs a newer Blog Studio runtime.')
    if run.get('schema') == 2 and not run.get('review_policy'):
        raise ValueError('This run is missing its saved review level. Restore its run record.')
    if run.get('schema') == 3 and (run.get('research_contract') or {}).get('schema') != 2:
        raise ValueError('This run is missing its saved research contract. Restore its run record.')
    return directory, record, run


def same_source(folder, source, revision):
    """Whether a newer source revision carries the pinned one's words unchanged.

    Marking a source as a sample, or naming its author, gives it a new revision without
    changing what a blog read from it. The payload takes its purposes from the blog's own
    pin, so a run accepts that revision when the name, status, origin and text equal the
    pinned revision's saved copy. Without that copy it cannot tell, and refuses."""
    saved = folder / 'revisions' / str(revision)
    if not isinstance(revision, int) or not (saved / 'record.json').is_file():
        return False
    try:
        pinned = studio.read_json(saved / 'record.json')
    except (OSError, ValueError):
        return False
    if any(pinned.get(key) != source.get(key) for key in ('name', 'status', 'origin')):
        return False
    then, now = saved / 'content.md', folder / 'content.md'
    if then.is_file() != now.is_file():
        return False
    return not now.is_file() or then.read_bytes() == now.read_bytes()


def pinned_source(folder, source, revision):
    """(record, text) of the source revision a blog pinned, for every source a blog reads.

    The current revision, or a newer one with the same words, reads from the source itself.
    An older revision reads from its saved copy under revisions/<n>/, so a later revision (a
    finished blog kept again, a corrected text) never changes what a blog already read.
    Without that copy a run cannot tell what it read, and refuses."""
    path = folder / 'content.md'
    if revision == source['revision'] or same_source(folder, source, revision):
        return source, path.read_text() if path.is_file() else ''
    saved = folder / 'revisions' / str(revision)
    if (
        isinstance(revision, int)
        and (saved / 'record.json').is_file()
        and (saved / 'content.md').is_file()
    ):
        try:
            return studio.read_json(saved / 'record.json'), (saved / 'content.md').read_text()
        except (OSError, ValueError):
            pass
    raise ValueError('A selected source changed. Reattach its current revision in chat first.')


def inputs(root, record, run):
    """Exact selected context. Never silently replace a pinned voice with its latest revision."""
    sources = []
    from hub_workspace import portable_origin

    pinned = {selected['source_id'] for selected in record['sources']}
    for selected in record['sources']:
        if 'material' in selected['purposes'] or selected['source_id'] in record.get(
            'material', []
        ):
            try:
                studio.item(root, 'sources', selected['source_id'])
            except ValueError:
                raise ValueError(MATERIAL_ELSEWHERE) from None
        folder, current = studio.item(root, 'sources', selected['source_id'])
        source, content = pinned_source(folder, current, selected['revision'])
        sources.append(
            {
                'id': 'source-' + studio.digest((source['name'] + content).encode())[:12],
                'name': source['name'],
                'origin': portable_origin(source['origin']),
                'purposes': selected['purposes'],
                'status': source['status'],
                'text': content,
            }
        )
    voice = dict(record['voice'])
    if voice.get('mode') == 'profile':
        folder, _ = studio.item(root, 'profiles', voice['profile_id'])
        folder = studio.inside(folder, 'revisions', str(voice['revision']))
        voice['guide'] = (folder / 'VOICE.md').read_text()
        voice['rules'] = (folder / 'rules.json').read_text()
        voice.pop('profile_id')
        voice.pop('revision')
    # Shared context is an explicit selection, not the entire Hub or other authors' work.
    shared = []
    if record.get('hub_context'):
        from hub_workspace import active

        adapter = active(root)
        if adapter is None and not (root / 'hub.json').is_file():
            raise ValueError('The selected team context needs its Team Hub. Reconnect it in chat.')
        for ref in record['hub_context']['selected']:
            if adapter is None:
                migrated = studio.read_json(
                    studio.inside(root, '.shared', 'memory', ref['revision'] + '.json')
                )
                shared.append({'kind': migrated['kind'], 'body': migrated['body']})
                continue
            revision = adapter.hub.graph()['revisions'][ref['revision']]
            materialized = adapter.hub.read(ref['item'], ref['revision'])
            shared.append(
                {
                    'kind': revision['kind'],
                    'body': Path(materialized['paths']['BODY.md']).read_text(),
                }
            )
    if set(record.get('material', [])) - pinned:
        raise ValueError(MATERIAL_ELSEWHERE)  # A Team Hub copy carries no uploaded files.
    sources = excerpted(sources, SOURCE_BUDGET, run_terms(record, run))
    # An example of the kind of post shows its shape; it has no citable source ID.
    examples = [
        {key: value for key, value in source.items() if key != 'id'}
        for source in sources
        if 'inspiration' in source['purposes']
    ]
    sources = [source for source in sources if 'inspiration' not in source['purposes']]
    if any('messaging' in source['purposes'] for source in sources):
        # Approved messaging is the announcement's own claims; the rest is evidence to cite.
        # Only a run with messaging says so, so saved pins hold for every other run.
        for source in sources:
            source['stance'] = 'messaging' if 'messaging' in source['purposes'] else 'evidence'
    payload = {
        'title': record['title'],
        'author': record.get('author', ''),
        'brief': run['brief'],
        'voice': voice,
        'sources': sources,
        'preferences': record.get('writing_preferences', {}),
        'memory': record.get('memory', {}),
        'team_context': shared,
        'research_policy': record['research_policy'],
        'guidance': (record.get('guidance') or {}).get('revision'),
    }
    if examples:
        payload['examples'] = examples  # Only when there are any, so saved pins hold.
    if record.get('research_from') is not None:
        # Where research may look, with the sites this blog pinned. A run saved before the
        # choice had three parts has none, so its pins hold.
        payload['research_from'] = record['research_from']
    if run.get('brand'):
        payload['brand'] = run['brand']
    if record.get('style'):
        import styles

        # Only when pinned: a run without a style keeps the stage pins it saved before styles.
        payload['style'] = styles.pinned(root, record['style'])
    if len(json.dumps(payload)) > 300_000:
        raise ValueError(
            'Selected context is too large for one writing job. Use focused excerpts in chat.'
        )
    return payload


def encoded_size(value):
    return len(json.dumps(value))


STOPWORDS = frozenset(
    'about after again also because been before being blog could does each file files from '
    'have into just more most much need only other over post same should some such than '
    'that their them then there these they this those through very want what when where '
    'which while will with would your uploaded write writing'.split()
)


def terms(*texts):
    """Words worth matching in a file: four letters or more, without common words."""
    words = []
    for value in texts:
        for word in re.findall(r'[^\W\d_]{4,}', str(value or '').casefold()):
            if word not in words and word not in STOPWORDS:
                words.append(word)
    return words[:12]


def run_terms(record, run):
    """What the person typed about the files and, once chosen, the angle: never defaults."""
    chosen = run.get('chosen_angle') or {}
    brief = run.get('brief') or {}
    return terms(
        run.get('files_note') or brief.get('goal', ''),
        chosen.get('title', ''),
        chosen.get('says', ''),
    )


def fit(text, limit, wanted=()):
    """The head of a text, then the paragraphs that mention the wanted words, then the rest,
    within a limit of JSON characters. Cuts are marked so the worker sees them."""
    if encoded_size(text) <= limit:
        return text
    spans = [(m.start(), m.end()) for m in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text)]
    chosen, used = {}, 0
    mark = encoded_size('\n\n[…]\n\n')

    def take(index, allowance, cut):
        nonlocal used
        start, end = spans[index]
        piece = text[start:end]
        size = encoded_size(piece)
        if size > allowance:
            if not cut:
                return False  # Whole paragraphs first; a later pass may cut one to fit.
            piece = piece[: max(0, len(piece) - (size - allowance))]
            while piece and encoded_size(piece) > allowance:
                piece = piece[: len(piece) * 9 // 10]
            if not piece:
                return False
            while piece and encoded_size(piece + ' […]') > allowance:
                piece = piece[: len(piece) * 9 // 10]
            if not piece:
                return False
            piece += ' […]'
        chosen[index] = piece
        used += encoded_size(piece) + mark
        return True

    order = list(range(len(spans)))
    matched = [
        index
        for index in order
        if any(word in text[spans[index][0] : spans[index][1]].casefold() for word in wanted)
    ]
    passes = ((order, limit // 2, False), (matched, limit, False), (order, limit, True))
    for sequence, allowance, cut in passes:
        for index in sequence:
            if index in chosen:
                continue
            if used + mark >= allowance or not take(index, allowance - used - mark, cut):
                break
    parts, previous = [], None
    for index in sorted(chosen):
        if previous is not None and index != previous + 1 and not parts[-1].endswith('[…]'):
            parts.append('[…]')
        parts.append(chosen[index])
        previous = index
    if previous is not None and previous != len(spans) - 1 and not parts[-1].endswith('[…]'):
        parts.append('[…]')
    return '\n\n'.join(parts)


def excerpted(sources, budget, wanted=()):
    """Sources within a shared budget: small files whole, large ones excerpted to a fair share."""
    sizes = {source['id']: encoded_size(source['text']) for source in sources}
    if sum(sizes.values()) <= budget:
        return sources
    shares, remaining = {}, budget
    pending = sorted(sources, key=lambda source: sizes[source['id']])
    for position, source in enumerate(pending):
        share = min(sizes[source['id']], remaining // (len(pending) - position))
        shares[source['id']] = share
        remaining -= share
    result = []
    for source in sources:
        if sizes[source['id']] <= shares[source['id']]:
            result.append(source)
            continue
        text = fit(source['text'], shares[source['id']], wanted)
        result.append(
            {
                **source,
                'text': text,
                'excerpted': True,
                'total_chars': len(source['text']),
                'kept_chars': len(text),
            }
        )
    return result


def basis(root, directory, record, run, stage, context=None, research=None):
    """A stage's input pin. Pass the serialised inputs() and research manifest to reuse them."""
    if context is None:
        context = json.dumps(inputs(root, record, run), sort_keys=True)
    previous = {}
    if run.get('mode') == 'from-outline':
        previous['supplied_outline'] = studio.artifact_fingerprint(directory, 'OUTLINE.md')
    for name in run['pipeline']:
        if name == stage:
            break
        previous[name] = studio.artifact_fingerprint(directory, STAGES[name][1])
    if run.get('research_contract') and 'research' in previous and run['stages'].get('research'):
        if research is None:
            _, research = research_contract.read_bundle(directory / 'research')
        previous['research_digest'] = research['digest']
    original = studio.artifact_fingerprint(directory, 'ORIGINAL.md')
    if run['existing'] and stage != 'draft':
        previous['manuscript'] = studio.artifact_fingerprint(directory, 'DRAFT.md') or original
    # Byte-for-byte json.dumps([inputs, previous, original], sort_keys=True), so saved pins hold.
    pinned = '[' + context + ', ' + json.dumps(previous, sort_keys=True) + ', '
    return studio.digest((pinned + json.dumps(original) + ']').encode())


def voice_name(root, record):
    """The pinned voice's current name, for listings; None for a described tone."""
    voice = record.get('voice') or {}
    if voice.get('mode') != 'profile':
        return None
    try:
        return studio.item(root, 'profiles', voice['profile_id'])[1]['name']
    except (ValueError, KeyError):
        return None


def style_name(root, record):
    """The pinned style's current name, for listings; None when the run has no style."""
    if not record.get('style'):
        return None
    import styles

    return styles.name_of(root, record['style']['style_id'])


def planning_questions(text):
    """Read a bounded plan from the tool-less planning worker."""
    questions, seen = [], set()
    for line in text.splitlines():
        match = re.fullmatch(r'- \*\*([a-z0-9][a-z0-9-]{0,39})\*\*:\s*(.+)', line.strip())
        if match and match[1] not in seen:
            seen.add(match[1])
            questions.append({'id': match[1], 'question': ' '.join(match[2].split())})
            if len(questions) == 8:
                break
    return questions


def research_price(root, directory, run):
    if not run.get('research_contract') or not run['stages'].get('research', {}).get('hash'):
        return None
    local = studio.inside(root, '.blog-runs', directory.name + '.json')
    saved = studio.read_json(local) if local.is_file() else {}
    jobs = (saved.get('research') or {}).get('jobs') or []
    priced = all(job.get('dollars') is not None for job in jobs)
    attempts = {}
    for job in jobs:
        if job.get('phase') in ('author', 'review'):
            name = f'research:{job["phase"]}-{job.get("round") or 1}'
            attempts.setdefault(name, []).append(
                {**job, 'dollars': job.get('dollars') if priced else None}
            )
    after = run['pipeline'][run['pipeline'].index('research') + 1 :]
    redone = [
        'the ' + STAGES[name][0].lower()
        for name in after
        if run['stages'].get(name, {}).get('hash')
    ]
    return research_view.price(attempts, redone, drafted=True, recorded=research_cost(jobs))


def survey(root, ident, listing=False):
    """Stage states. A listing skips the version token and next document a decision needs."""
    from google_handoff import pending_link

    directory, record, run = load(root, ident)
    research, bundle_problem = None, False
    if run.get('research_contract') and run['stages'].get('research'):
        try:
            _, research = research_contract.read_bundle(directory / 'research')
        except (OSError, ValueError, KeyError, TypeError):
            research, bundle_problem = {'digest': None}, True
    # Selected context is read and serialised once; every stage pin reuses it.
    payload = inputs(root, record, run)
    context = json.dumps(payload, sort_keys=True)
    bases = {}

    def pin(name):
        if name not in bases:
            bases[name] = basis(root, directory, record, run, name, context, research)
        return bases[name]

    rows, next_stage, upstream = [], None, False
    for name in run['pipeline']:
        saved = run['stages'].get(name, {})
        current = studio.artifact_fingerprint(directory, STAGES[name][1])
        changed = bool(saved) and (
            saved.get('hash') != current
            or saved.get('basis') != pin(name)
            or name == 'research'
            and bundle_problem
        )
        status = (
            'pending'
            if saved.get('status') == 'pending'
            else 'stale'
            if saved and (changed or upstream)
            else saved.get('status', 'pending')
        )
        if status != 'approved':
            upstream = True
            if next_stage is None:
                next_stage = name
        rows.append(
            {
                'stage': name,
                'label': STAGES[name][0],
                'status': status,
                'path': STAGES[name][1],
                'notes': saved.get('notes', ''),
                'accepted_by': saved.get('accepted_by'),
                # Accepted by the saved review level, not the person; it needs no approval.
                'auto_accepted': status == 'approved'
                and saved.get('accepted_by') == 'review-policy',
                'request': saved.get('request', ''),
            }
        )
    # What is left: the stages not yet approved, and the first of them that stops for the
    # person under this run's own level. The angles always do: the person picks one.
    left = [row['stage'] for row in rows if row['status'] != 'approved']
    stops_ahead = review_policy.ahead(
        run,
        'blog',
        [stage for stage in left if stage != 'angles'],
        last=run['pipeline'][-1],
        first='outline' if 'outline' in run['pipeline'] else 'draft',
    )
    next_gate = 'angles' if 'angles' in left else (stops_ahead[0] if stops_ahead else None)
    ahead = {
        'steps_left': len(left),
        'next_gate': next_gate,
        'next_stop': STAGES[next_gate][0] if next_gate else None,
    }
    # What moves the run on: the person's decision on a submitted document, or a submission.
    awaits = None
    if next_stage:
        submitted = next(row for row in rows if row['stage'] == next_stage)['status'] == 'draft'
        awaits = 'decision' if submitted else 'submission'
    content, revision = '', None
    if next_stage and not listing:
        path = studio.inside(directory, STAGES[next_stage][1])
        content = path.read_text() if path.is_file() else ''
    if not listing:
        revision = studio.digest(
            (
                studio.inside(directory, STATE).read_bytes()
                + (
                    (directory / 'run.json').read_bytes()
                    if (directory / 'run.json').is_file()
                    else b''
                )
                + json.dumps(
                    [
                        [
                            row,
                            studio.artifact_fingerprint(directory, row['path']),
                            pin(row['stage']),
                        ]
                        for row in rows
                    ],
                    sort_keys=True,
                ).encode()
            )
        )
    where = research_from(record, run)
    return {
        'id': ident,
        'title': record['title'],
        'google': editorial.doc_link(record),
        'google_pending': pending_link(record),
        'approval': run['approval'],
        'engine': run['engine'],
        'model_mode': (run.get('model_profiles') or {}).get('mode', 'single'),
        'review_level': review_policy.level(run),
        'seconds': run['seconds'],
        'stages': rows,
        'next': next_stage,
        'ahead': ahead,
        'awaits': awaits,
        'complete': next_stage is None,
        # Every stage was approved once, though an edit since may read as stale: a blog
        # finished and then edited in the manuscript editor. Its DRAFT.md is the latest text.
        'finished': all(
            run['stages'].get(name, {}).get('status') == 'approved' for name in run['pipeline']
        ),
        'content': content,
        'expected': revision,
        'directory': str(directory),
        'brief': run['brief'],
        'voice_name': voice_name(root, record),
        'voice_mode': (record.get('voice') or {}).get('mode'),
        'voice_profile': (record.get('voice') or {}).get('profile_id'),
        'voice_revision': (record.get('voice') or {}).get('revision'),
        'style_name': style_name(root, record),
        'existing': run['existing'],
        'editor_check': run.get('editor_check'),
        'mode': run.get('mode', 'review' if run['existing'] else 'write'),
        'brand': {key: run['brand'][key] for key in ('skill', 'version', 'brand', 'variant')}
        if run.get('brand')
        else None,
        'decisions': run.get('decisions', [])[-30:],
        'publication': (record.get('editorial') or {}).get('publication_url') or None,
        # Whether Finish kept the blog in the team library, for the Done card.
        'library': run.get('library') if next_stage is None else None,
        # Files cut to the run's budget, by name, so the page and chat can say so.
        'excerpted': [
            source['name']
            for source in payload['sources'] + payload.get('examples', [])
            if source.get('excerpted')
        ],
        # Reviewed research through the shared contract, rather than a plain writing job.
        'research_contract': bool(run.get('research_contract')),
        'research_price': research_price(root, directory, run),
        # When and where the person continued without research, for chat and the page.
        'research_skipped': run.get('research_skipped'),
        # Where its research may look, with the sites it pinned, and that said in words.
        'research_from': where,
        'research_says': research_says(where),
        # Whether Finish has a draft to keep in the team library (see keep_finished).
        'keeps_draft': None if listing else has_draft(directory, run),
        # What a kept research draft must still match: the research stage's input pin and
        # saved version. Only while the run waits on its research.
        'research_tie': {
            'basis': pin('research'),
            'hash': run['stages'].get('research', {}).get('hash'),
        }
        if not listing and next_stage in RESEARCH_STAGES and 'research' in run['pipeline']
        else None,
    }


def note_decision(directory, run, event):
    """Append one decision to the run, keeping its previous state in history."""
    path = studio.inside(directory, STATE)
    if path.exists():
        studio.atomic(
            studio.inside(directory, 'history', 'editorial-run-' + uuid.uuid4().hex + '.json'),
            path.read_bytes(),
        )
    run.setdefault('decisions', []).append({'event': event, 'at': studio.now()})
    studio.write_json(path, run)


def save(root, directory, record, run, event):
    import desk

    desk.refuse_on_desk(directory)  # A blog on the desk keeps its run as it was, read-only.
    note_decision(directory, run, event)
    record['next_step'] = (
        'Continue the guided blog on the page.'
        if run['approval'] == 'page'
        else 'Continue the guided blog in chat.'
    )
    studio.persist(directory, 'articles', record)
    from management import share, receipt

    from team_workspace import saved

    saved(root, record['id'], event)
    result = share(root, 'article', record)
    receipt(root, 'Guided blog', result, 'article')


def review_level(root, data):
    """Settings' Where new work stops: write the level new work starts at in every studio,
    refused when another studio changed the one the page read. Answers the settings."""
    import studios_config

    if not isinstance(data, dict) or set(data) != {'level', 'seen'}:
        raise ValueError('Give the level and the level the page read.')
    review_policy.change(studios_config.update, data['level'], data['seen'])
    return settings(root)


def redo(found, jobs):
    """What Ask for changes at each writing stage draws again: that stage and every one
    after it, with what they took the last time each ran on this computer. The research
    stages keep their own words."""
    stages = [row['stage'] for row in found['stages']]
    last = {}
    for job in jobs or ():
        if isinstance(job, dict) and job.get('stage'):
            last[job['stage']] = job
    shown = {}
    for at, stage in enumerate(stages):
        if stage in RESEARCH_STAGES or stage == 'angles':
            continue
        again = stages[at:]
        ran = [last.get(name) for name in again]
        recorded = all(ran)
        seconds = sum(float(job.get('seconds') or 0) for job in ran) if recorded else None
        dollars = [job.get('dollars') for job in ran] if recorded else [None]
        priced = None if None in dollars else round(sum(dollars), 4)
        shown[stage] = {
            'stages': again,
            'says': stops.redone('the ' + STAGES[stage][0].lower(), len(again), seconds, priced),
        }
    return shown


def research_scope(research, sources):
    """Supplied-only research has nothing to read without supplied sources."""
    return 'none' if research == 'supplied-only' and not sources else research


def research_from(record, run):
    """Where this blog's research may look: {'documents', 'sites', 'web'}, or None for no
    research. A run saved before the choice had three parts reads its research policy:
    supplied-only is your documents, web-allowed your documents and the public web."""
    if run.get('research_skipped'):
        return None
    if 'research_from' in record:
        value = record['research_from']
        return research_sites.effective(value) if isinstance(value, dict) else None
    stages = set(run.get('pipeline') or ())
    if (run.get('after_angles') or {}).get('research') == 'web-allowed':
        stages.add('research')
    if not stages & set(RESEARCH_STAGES) and run.get('mode') != 'from-files':
        return None
    return research_sites.legacy(record.get('research_policy'))


def research_says(value):
    """'Research from your documents and 2 of your sites (...).', or 'No research.'"""
    return 'Research ' + research_sites.summary(value) + '.' if value else 'No research.'


def chosen_research(data, mode):
    """(research, chosen): the research policy word this blog starts with, and where its
    research may look in the shared shape before documents are counted, or None for no
    research. A form sends research_from; the older research words are still read."""
    if 'research_from' in data:
        if 'research' in data:
            raise ValueError('Choose where research may look, or no research, not both.')
        chosen = research_sites.choice(data['research_from'])
        return ('web-allowed' if research_sites.fetches(chosen) else 'supplied-only'), chosen
    research = data.get(
        'research', 'none' if mode in ('revise', 'review', 'ideas') else 'supplied-only'
    )
    if research not in OLD_RESEARCH:
        raise ValueError('Choose supplied sources, public research, or no research.')
    if mode == 'from-files' and research == 'none':
        research = 'supplied-only'  # The files are the sources; the web is the only option.
    return research, research_sites.legacy(research)


def create(root, data, approval='conversation'):
    data = dict(data)
    defaults = settings(root)['defaults']
    data.setdefault('engine', defaults['engine'])
    data.setdefault('author', defaults['author'])
    if 'brand' not in data:
        import brand_skill

        for key, value in brand_skill.defaults().items():
            data.setdefault(key, value)
    allowed = {
        'id',
        'title',
        'author',
        'audience',
        'goal',
        'tone',
        'profile',
        'style',
        'sources',
        'research',
        'stop',
        'engine',
        'seconds',
        'mode',
        'manuscript',
        'outline_text',
        'brand',
        'variant',
        'point',
        'revision',
        'library',
        'length',
        'research_from',
    }
    if set(data) - allowed:
        raise ValueError('Unknown new-blog field.')
    mode = data.get('mode', 'write')
    if mode not in MODES:
        raise ValueError(
            'Choose write, outline, from-outline, ideas, revise, review or from-files.'
        )
    # I know the point: a blog from files that starts at the outline instead of three angles.
    point = data.get('point', False)
    if point not in (True, False):
        raise ValueError('Say whether you know the point: true or false.')
    if point and mode != 'from-files':
        raise ValueError('The point you know starts a blog from files.')
    outline_text = text(
        data.get('outline_text', ''), 'outline', 200_000, required=mode == 'from-outline'
    )
    manuscript = None
    if data.get('manuscript'):
        if mode not in ('revise', 'review'):
            raise ValueError('Choose revise or review to start from a manuscript.')
        if data.get('id'):
            raise ValueError('Choose a saved blog or a supplied manuscript, not both.')
        folder, source = studio.item(root, 'sources', data['manuscript'])
        path = studio.inside(folder, 'content.md')
        if source['status'] != 'ready' or not path.is_file() or not path.read_text().strip():
            raise ValueError('Choose a draft with readable text.')
        manuscript = path.read_text()
        if len(manuscript) > 200_000:
            raise ValueError('Use a manuscript up to 200,000 characters.')
    if mode in ('revise', 'review') and not (data.get('id') or manuscript):
        raise ValueError('Choose an existing blog or upload a draft first.')
    engine = data.get('engine', 'codex')
    if engine not in ('codex', 'claude'):
        raise ValueError('Choose Codex or Claude.')
    seconds = data.get('seconds', 600)
    if type(seconds) is not int or not 30 <= seconds <= 3600:
        raise ValueError('Choose a step time limit between 30 and 3600 seconds.')
    research, chosen = chosen_research(data, mode)
    stop = data.get('stop', 'package')
    if mode in ('outline', 'ideas'):
        stop = 'outline'
    elif mode == 'review':
        stop = 'review'
    elif mode == 'revise' and stop == 'outline':
        raise ValueError('A revision starts at draft. Choose draft, review or the handoff.')
    if stop not in ('outline', 'draft', 'review', 'package'):
        raise ValueError('Choose outline, draft, review or the handoff.')
    length = data.get('length', 'style')
    if length not in LENGTHS:
        raise ValueError('Choose a length: the usual length, short or in depth.')
    if length != 'style' and (mode in ('revise', 'review', 'ideas') or manuscript):
        raise ValueError(NO_LENGTH)
    from_files = mode == 'from-files'
    angles_first = from_files and not point
    brief = {
        'goal': text(data.get('goal', ''), 'goal', required=not angles_first)
        or 'Write a blog from the uploaded files.',
        'audience': text(data.get('audience', ''), 'audience', 500, required=not angles_first)
        or 'To be chosen with the angle.',
    }
    import brand_skill

    if not isinstance(data.get('brand', ''), str) or not isinstance(data.get('variant', ''), str):
        raise ValueError('Choose a listed brand and variant.')
    title = text(
        data.get('title', ''), 'title', 500, required=not data.get('id') and not angles_first
    )
    if from_files:
        title = title or 'From my files'
        if data.get('id') or manuscript or outline_text:
            raise ValueError('Write from my files starts a new blog from uploaded files.')
    profile = data.get('profile') or None
    revision = data.get('revision')
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ValueError('Choose a saved revision of the voice profile.')
    if profile:
        studio.voice_pin(root, profile, revision)
    elif revision is not None:
        raise ValueError('A voice revision needs its profile.')
    tone = text(data.get('tone', ''), 'tone')
    # Beside a voice, the tone is a nudge only when the person changed the usual one.
    nudge = '' if tone == defaults.get('tone') else tone
    style = data.get('style') or None
    if style:
        # Refused here if retired or unknown. Checking writes nothing: a starter is copied
        # into the workspace only once the whole request has passed, below.
        studio.style_check(root, style)
    sources = data.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 50 or len(set(sources)) != len(sources):
        raise ValueError('Select at most 50 different sources.')
    for source in sources:
        studio.item(root, 'sources', source)
    # Library items read with a role for this blog only; the library record is not changed.
    picked = library_picks(root, data.get('library', []), sources)
    if from_files:
        readable = [
            source
            for source in sources + list(picked)
            if studio.item(root, 'sources', source)[1]['status'] == 'ready'
        ]
        if not readable:
            raise ValueError('Upload at least one file with text first.')
    existing = bool(data.get('id') or manuscript)
    if data.get('id'):
        directory, record = studio.item(root, 'articles', data['id'])
        if studio.inside(directory, STATE).exists():
            raise ValueError('This blog already has a guided run. Open that run instead.')
        existing = (directory / 'DRAFT.md').is_file() or (directory / 'ORIGINAL.md').is_file()
        if mode in ('revise', 'review') and not existing:
            raise ValueError('This blog has no saved manuscript to revise or review.')
        if existing and stop in ('outline', 'draft') and mode != 'revise':
            raise ValueError('An existing draft starts at review. Choose review or the handoff.')
        if existing and length != 'style':
            raise ValueError(NO_LENGTH)
    else:
        # No profile key: the default voice applies. An empty one is "No particular voice":
        # the described tone. An ID pins that voice.
        chose = 'profile' in data
        args = SimpleNamespace(
            action='create',
            id=None,
            title=title,
            mode='existing'
            if manuscript
            else 'outline-only'
            if stop == 'outline'
            else 'first-draft',
            profile=profile,
            author=text(data.get('author', ''), 'author', 200) or None,
            voice='tone' if chose else None,
            tone=(nudge if profile else tone) if chose else None,
            audience=brief['audience'],
            blog_type=None,
            review_folder=None,
            stop='outline' if stop == 'outline' else 'review',
            research='supplied-only' if research == 'none' else research,
        )
        ident = studio.new_id(title)
        record = studio.article_record(root, args, ident)
        if not chose and record['voice']['mode'] == 'preserve' and manuscript:
            # A revise or review keeps the manuscript's own voice unless one is picked.
            record['voice'] = {'mode': 'preserve', 'tone': nudge}
        elif not chose and record['voice']['mode'] != 'profile':
            record['voice'] = {'mode': 'tone', 'tone': tone}  # No default voice to apply.
        elif not chose and nudge:
            record['voice']['tone'] = nudge  # A nudge on top of the default voice.
        directory = studio.inside(root, 'articles', ident)
    if data.get('id') and mode == 'from-outline' and not existing:
        record['mode'] = 'from-outline'
        record['stop_point'] = stop
    for source in sources + list(picked):
        _, source_record = studio.item(root, 'sources', source)
        record['sources'] = [s for s in record['sources'] if s['source_id'] != source] + [
            {
                'source_id': source,
                'revision': source_record['revision'],
                'purposes': picked.get(source, source_record['purposes']),
            }
        ]
    if profile:
        record['voice'] = {'mode': 'profile', **studio.voice_pin(root, profile, revision)}
        if nudge:
            record['voice']['tone'] = nudge
    if style:
        record['style'] = studio.style_check(root, style)
    record['research_policy'] = 'supplied-only' if research == 'none' else research
    record.pop('research_from', None)
    # Your documents count only when there are some: the files, or readable selected facts.
    given = from_files or bool(
        chosen
        and chosen['documents']
        and claims_map.material(inputs(root, record, {'brief': brief})['sources'])
    )
    found = research_sites.effective(chosen, given) if chosen else None
    if found and not (found['documents'] or found['sites'] or found['web']):
        found = None  # Only your documents, and none were given: no research, as before.
    if found and found['sites'] and not found['web'] and research_contract.snapshot() is None:
        raise ValueError(NEEDS_HARNESS_RESEARCH)
    research = (
        'none'
        if found is None
        else 'web-allowed'
        if research_sites.fetches(found)
        else 'supplied-only'
    )
    record['research_policy'] = 'supplied-only' if research == 'none' else research
    # The run's choice, with the exact list of sites it uses: a later change to the shared
    # list never changes a blog that has started.
    record['research_from'] = found
    if from_files and research == 'supplied-only':
        research = 'none'  # The files are read at every step; only the web adds research stages.
    pipeline = (
        []
        if research == 'none'
        else ['claims-map']
        if research == 'supplied-only'
        else ['research-plan', 'research']
    )
    pipeline += (
        (['draft', 'review', 'package'] if mode == 'revise' else ['review', 'package'])
        if existing
        else ['draft', 'review', 'package']
        if mode == 'from-outline'
        else ['outline', 'draft', 'review', 'package']
    )
    pipeline = pipeline[: pipeline.index(stop) + 1]
    if from_files:
        record['stop_point'] = stop
        record['mode'] = 'from-files'
    if angles_first:
        # Three angles first; the chosen one starts the pipeline above (see choose_angle).
        pipeline = ['angles']
    run = {
        'schema': 1,
        'approval': approval,
        'engine': engine,
        'seconds': seconds,
        'brief': brief,
        'existing': existing,
        'mode': mode,
        'pipeline': pipeline,
        'stages': {},
        'length': length,
    }
    if from_files:
        run['angles'] = angles_first
        if angles_first:
            run['after_angles'] = {'research': research, 'stop': stop}
        # What the person said about the files: their note, or the title and point they know.
        run['files_note'] = (
            text(data.get('goal', ''), 'goal') if angles_first else title + '\n' + brief['goal']
        )
    # The uploaded files this blog pinned; a deletion keeps them with it.
    record['material'] = [
        entry['source_id'] for entry in record['sources'] if 'material' in entry['purposes']
    ]
    import studios_config

    # Where this blog stops is the shared level. A shared file that cannot be read gives the
    # built-in defaults, and never more autonomy than Step by step.
    shared, problem = studios_config.read()
    assistant = shared.get('assistant') or {}
    same_agent = assistant.get('agent') == engine
    contract = research_contract.snapshot() if research != 'none' else None
    if contract:
        run['research_contract'] = contract
    run['review_policy'] = (
        {'schema': 1, 'level': 'step_by_step'} if problem else review_policy.snapshot(shared)
    )
    if review_policy.level(run) != 'step_by_step':
        run['schema'] = 2
    if contract:
        run['schema'] = 3
    run['model_profiles'] = model_profiles.snapshot(
        shared,
        engine,
        assistant.get('model') if same_agent else None,
        assistant.get('effort') if same_agent else None,
    )
    # The brand writes the run's author voice beside its own naming rules: the voice the form
    # chose or the default one, once it is settled. A tone-only or preserved voice gives none.
    pinned = record.get('voice') or {}
    handoff = (
        studio.voice_handoff(root, pinned['profile_id'], pinned.get('revision'))
        if pinned.get('mode') == 'profile' and pinned.get('profile_id')
        else None
    )
    selected_brand = brand_skill.snapshot(data.get('brand', ''), data.get('variant', ''), handoff)
    if selected_brand:
        run['brand'] = selected_brand
    inputs(root, record, run)  # Refuse unusable context before creating a partial blog.
    if style:
        record['style'] = studio.style_pin(root, style, record['style']['revision'])
    if not data.get('id'):
        directory.mkdir()
        studio.write_json(studio.inside(root, '.active-article.json'), {'id': record['id']})
    if outline_text:
        studio.save_artifact(directory, 'outline', outline_text, record, 'author supplied outline')
    if manuscript:
        studio.save_artifact(directory, 'original', manuscript, record, 'supplied manuscript')
        studio.save_artifact(directory, 'draft', manuscript, record, 'supplied manuscript')
    save(root, directory, record, run, 'Created from ' + approval)
    return survey(root, record['id'])


LIBRARY_ROLES = {
    'facts': ['reference'],
    'example': ['reference', 'inspiration'],
    'messaging': ['reference', 'messaging'],
}


def library_picks(root, chosen, sources):
    """{id: purposes} for library items read with a role for one blog: `[{id, role}]`, or
    `[{id, role, location}]` for a row the catalog lists from the Team Hub, which is checked
    out here first. Each is a library item (never a file uploaded for one blog), no more than
    50 with the sources, and none of them twice."""
    import blog_library

    if not isinstance(chosen, list) or len(chosen) + len(sources) > 50:
        raise ValueError('Pick at most 50 library items and sources together.')
    picked = {}
    for entry in chosen:
        if (
            not isinstance(entry, dict)
            or set(entry) - {'location'} != {'id', 'role'}
            or not isinstance(entry['id'], str)
            or entry['role'] not in LIBRARY_ROLES
        ):
            raise ValueError(
                'Each library item needs its id and a role: facts, messaging or example.'
            )
        ident = blog_library.local_item(root, entry['id'], entry.get('location', 'local'))
        if ident in picked or ident in sources:
            raise ValueError('Pick each library item once.')
        directory, record = studio.item(root, 'sources', ident)
        if studio.is_material(root, directory, record):
            raise ValueError('A file uploaded for one blog is not a library item.')
        picked[ident] = list(LIBRARY_ROLES[entry['role']])
    return picked


def guard(root, ident, expected, page=False):
    found = survey(root, ident)
    if found['approval'] == 'page' and not page:
        raise ValueError(
            'This blog is decided on the page. Open its run to approve or return it to chat.'
        )
    if page and found['approval'] != 'page':
        raise ValueError('This blog is decided in chat. Choose Run this from here first.')
    if not expected or expected != found['expected']:
        raise ValueError('This blog changed. Reload its run and compare before deciding.')
    return found


def submit(root, ident, stage, result, expected, page=False):
    import desk

    # A blog on the desk keeps its run as it ended: a late result writes nothing at all.
    desk.refuse_on_desk(studio.item(root, 'articles', ident)[0])
    found = guard(root, ident, expected, page)
    if found['next'] != stage:
        raise ValueError('Finish the current stage before submitting another.')
    result = blog_worker.validate(result)
    if stage == 'angles' and len(angles(result['content'])) != 3:
        raise ValueError('Return exactly three angles, each under its own ## heading.')
    directory, record, run = load(root, ident)
    if stage == 'research' and run.get('research_contract'):
        research_contract.read_bundle(directory / 'research')
        if result['content'] != (directory / 'research/report.md').read_text():
            raise ValueError('Submit the saved, independently reviewed research report.')
    if stage == 'review' and run.get('editor_check'):
        from manuscript_editor import record_review

        result = record_review(root, directory, record, run, result)
    if stage == 'claims-map':
        said = claims_map.problems(
            result['content'], claims_map.material(inputs(root, record, run)['sources'])
        )
        if said:
            raise ValueError(
                'The claims map quoted passages that are not in your material: ' + said[0]
            )
    pin = basis(root, directory, record, run, stage)
    filename = STAGES[stage][1]
    preservation = None
    saved_path = studio.inside(directory, filename)
    unchanged = saved_path.is_file() and saved_path.read_text() == result['content']
    if stage == 'draft' and (directory / 'DRAFT.md').is_file():
        from text_checks import preserve

        preservation = preserve((directory / 'DRAFT.md').read_text(), result['content'])
    if stage in ('outline', 'draft'):
        studio.save_artifact(directory, stage, result['content'], record, 'guided run')
    else:
        path = studio.inside(directory, filename)
        if path.exists():
            studio.atomic(
                studio.inside(
                    directory, 'history', 'derived-blog-' + stage + '-' + uuid.uuid4().hex + '.md'
                ),
                path.read_bytes(),
            )
        studio.atomic(path, result['content'].encode())
    if stage in NOTED:
        noted = notes_path(directory, stage)
        if result.get('evidence') or result.get('gaps'):
            kept = {'evidence': result.get('evidence', []), 'gaps': result.get('gaps', [])}
            studio.atomic(noted, (json.dumps(kept, indent=2) + '\n').encode())
        elif not (unchanged and 'evidence' not in result and 'gaps' not in result):
            # A new version without notes keeps none; the same version brought back keeps its.
            noted.unlink(missing_ok=True)
    previous = run['stages'].get(stage, {})
    run['stages'][stage] = {
        'status': 'draft',
        'hash': studio.digest(result['content'].encode()),
        'basis': pin,
        'notes': result['notes'],
        'request': previous.get('request', ''),
        'model_purpose': previous.get('model_purpose', stage),
        **({'preservation': preservation} if preservation is not None else {}),
    }
    if stage != 'angles' and review_policy.automatic(
        run,
        'blog',
        stage,
        run['pipeline'][-1],
        first='outline' if 'outline' in run['pipeline'] else 'draft',
    ):
        _accept(directory, run, stage, 'review-policy')
        review_policy.receipt(run, stage, run['stages'][stage], studio.now())
    if stage == 'research':
        # Saved research, from the page, chat or a handover, replaces any kept draft.
        shutil.rmtree(directory / RESEARCH_DRAFT, ignore_errors=True)
    save(root, directory, record, run, 'Submitted ' + stage)
    return survey(root, ident)


# A draft's and a handoff's notes for the author, saved beside the stage: each claim's source
# and passage, and what the author must supply before publishing. Never in the writing.
NOTED = ('draft', 'package')


def notes_path(directory, stage):
    return studio.inside(directory, 'derived', 'blog-' + stage + '-notes.json')


def stage_notes(directory, stage):
    """The saved notes, or none when the file is missing or cannot be read as notes."""
    path = notes_path(directory, stage)
    try:
        found = studio.read_json(path) if path.is_file() else {}
    except (OSError, ValueError):
        found = {}
    if not isinstance(found, dict):
        found = {}
    evidence, gaps = found.get('evidence'), found.get('gaps')
    return {
        'evidence': [row for row in evidence if isinstance(row, dict)]
        if isinstance(evidence, list)
        else [],
        'gaps': [gap for gap in gaps if isinstance(gap, str) and gap.strip()]
        if isinstance(gaps, list)
        else [],
    }


def gaps(directory, stage):
    """What the author must supply before publishing: a handoff keeps the draft's too."""
    found = list(stage_notes(directory, stage)['gaps'])
    if stage == 'package':
        found += [gap for gap in stage_notes(directory, 'draft')['gaps'] if gap not in found]
    return found


def _accept(directory, run, stage, by):
    run['stages'][stage].update(status='approved', accepted_by=by)
    approved_hash = run['stages'][stage]['hash']
    studio.atomic(
        studio.inside(
            directory, 'history', 'derived-blog-approved-' + stage + '-' + approved_hash + '.md'
        ),
        studio.inside(directory, STAGES[stage][1]).read_bytes(),
    )
    run.setdefault('approved', {})[stage] = approved_hash


def decide(root, ident, expected, action, request='', page=False, target=None, refresh=False):
    found = guard(root, ident, expected, page)
    directory, record, run = load(root, ident)
    kept = None  # What Finish did with the library, said in the decision.
    stage = target if action == 'changes' and target else found['next']
    if refresh and (action != 'changes' or stage != 'research'):
        raise ValueError('Only the research is brought up to date.')
    if (
        action == 'changes'
        and target == 'draft'
        and run['existing']
        and 'draft' not in run['pipeline']
    ):
        run['pipeline'].insert(run['pipeline'].index('review'), 'draft')
    if stage is not None and stage not in run['pipeline']:
        raise ValueError('Choose a stage in this blog’s run.')
    if action == 'changes' and target and found['next']:
        if run['pipeline'].index(target) > run['pipeline'].index(found['next']):
            raise ValueError('Finish the current stage before changing a later stage.')
    if action == 'handoff':
        run['approval'] = 'conversation' if page else 'page'
    elif action == 'approve' and stage == 'angles':
        raise ValueError(
            'Choose one of the angles with run choose, or ask for three different ones.'
        )
    elif action == 'approve':
        if (
            not stage
            or next(row['status'] for row in found['stages'] if row['stage'] == stage) != 'draft'
        ):
            raise ValueError(
                'Only a current submitted draft can be approved. Read awaits in run status: '
                'steps the review level accepted automatically need no approval.'
            )
        _accept(directory, run, stage, 'page' if page else 'conversation')
        if stage == run['pipeline'][-1]:
            # Finish: the approved draft lands in the team library, once per blog.
            kept = keep_finished(root, directory, record, run)
    elif action == 'changes':
        if not stage:
            raise ValueError('This run is complete. Start a new revision in chat.')
        # Bringing the research up to date reads its sources again: it needs no words.
        request = text(
            request or ('Bring the evidence up to date.' if refresh else ''),
            'change request',
            8000,
            required=True,
        )
        run['stages'].setdefault(stage, {})['status'] = 'pending'
        run['stages'][stage]['request'] = request
        run['stages'][stage]['refresh'] = bool(refresh)
        run['stages'][stage]['model_purpose'] = (
            'repair' if stage == 'draft' and found['next'] == 'review' else stage
        )
        # Downstream decisions are kept in history, never silently renewed.
        for name in run['pipeline'][run['pipeline'].index(stage) + 1 :]:
            run['stages'].pop(name, None)
    else:
        raise ValueError('Unknown guided-blog decision.')
    event = action + (' ' + stage if stage else '')
    if action == 'approve' and kept is not None:
        event += ' · ' + kept
    save(root, directory, record, run, event)
    return survey(root, ident)


RESEARCH_STAGES = ('research-plan', 'research', 'claims-map')


def skip_research(root, directory, record, run, at):
    """Take research out of a run that stopped at it: its stages leave the pipeline, the
    decision is recorded, and the later stages are told there is no research bundle. The
    blog keeps its own research policy, so no other stage's input pin changes."""
    run['pipeline'] = [stage for stage in run['pipeline'] if stage not in RESEARCH_STAGES]
    for stage in RESEARCH_STAGES:
        run['stages'].pop(stage, None)
        run.get('approved', {}).pop(stage, None)
    run['research_skipped'] = {'from': at, 'at': studio.now()}
    save(root, directory, record, run, 'Continued without research')


def has_draft(directory, run):
    """Whether finishing this run keeps a draft in the team library."""
    draft = directory / 'DRAFT.md'
    if run.get('mode') in ('ideas', 'outline') or not draft.is_file():
        return False
    try:
        return bool(draft.read_text().strip())
    except (OSError, ValueError):
        return False


def keep_finished(root, directory, record, run):
    """Keep a finished blog's draft in the library; what happened, in a few words, or None
    when the run ends without a draft (ideas, an outline). run['library'] says it for the
    Done card: the item and its revision, or why the blog was not kept. The approval never
    waits on it: whatever stops the library save is reported, never raised."""
    draft = directory / 'DRAFT.md'
    if run.get('mode') in ('ideas', 'outline') or not draft.is_file():
        run.pop('library', None)
        return None
    try:
        text = draft.read_text()
        if not text.strip():
            run.pop('library', None)
            return None
        import blog_library
        import styles

        kind = (record.get('style') or {}).get('style_id')
        if kind and styles.name_of(root, kind) is None:
            kind = None  # Its style is gone; the blog is kept without a kind of post.
        source = blog_library.keep_written(root, record, text, kind)
        from management import share, receipt

        receipt(root, 'Finished blog', share(root, 'source', source), 'source')
    except Exception as exc:
        if not isinstance(exc, (ValueError, OSError)):
            from management import note_unexpected

            note_unexpected(exc)
        reason = (
            str(exc)[:200]
            if isinstance(exc, ValueError)
            else 'it could not be saved here. The approval is kept; finish it again to retry.'
        )
        run['library'] = {'reason': reason}
        return 'not kept in the team library: ' + reason
    run['library'] = {'id': source['id'], 'revision': source['revision']}
    return 'kept in the team library'


def tone_nudge(voice):
    tone = (voice.get('tone') or '').strip()
    return ' Tone nudge: ' + tone + ('' if tone.endswith(('.', '!', '?')) else '.') if tone else ''


def brief_line(root, record, payload):
    """Whose voice, which style and what tone, for the worker. In the guidance, not in
    inputs(), so the stage pins saved before this line hold."""
    voice = record.get('voice') or {}
    style = payload.get('style')
    if voice.get('mode') == 'profile':
        folder, _ = studio.item(root, 'profiles', voice['profile_id'])
        pinned = studio.read_json(
            studio.inside(folder, 'revisions', str(voice['revision']), 'record.json')
        )
        line = (
            'Write as '
            + pinned['name']
            + ' (voice guide revision '
            + str(voice['revision'])
            + ', '
            + pinned['status']
            + ')'
            + (', in the shape of ' + style['name'] if style else '')
            + '.'
        )
        return line + tone_nudge(voice)
    line = (
        'No author voice is pinned; keep the manuscript’s own voice.'
        if voice.get('mode') == 'preserve'
        else 'No author voice is pinned; follow voice.tone.'
        if voice.get('tone')
        else 'No author voice is pinned; write plainly in the house style.'
    )
    line += (' Write in the shape of ' + style['name'] + '.') if style else ''
    return line + (tone_nudge(voice) if voice.get('mode') == 'preserve' else '')


def carried(directory, run, payload, writing):
    """Passages of `writing` that came from an example and from nothing the run allows:
    its sources, brief, outline and research facts. Empty without examples."""
    if not payload.get('examples') or not writing.strip():
        return []
    from text_checks import carried_over

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    allowed = (
        [source['text'] for source in payload['sources']]
        + [str(value) for value in run['brief'].values()]
        + [payload.get('title', '')]
        + [str(item.get('body', '')) for item in payload.get('team_context', [])]
    )
    outline = directory / 'OUTLINE.md'
    if outline.is_file():
        allowed.append(outline.read_text())
    if run.get('research_contract') and run['stages'].get('research'):
        facts, _ = research_contract.read_bundle(directory / 'research')
        allowed += list(strings([facts['facts'], facts['findings'], facts.get('sections', [])]))
        allowed.append((directory / 'research/brief.md').read_text())
    return carried_over(writing, payload['examples'], allowed)['findings']


REFERENCES = Path(__file__).resolve().parents[1] / 'references'
# Sentences a run's writing steps and the desk's writing jobs share.
FROM_OUTLINE = (
    'Use the supplied outline as authoritative structure. Preserve headings and order unless '
    'explicitly asked to restructure.'
)
WRITING_NOTES = (
    'Return the writing in content and your notes apart from it: in evidence, each material '
    'claim with its source ID and exact passage; in gaps, each thing the author must supply '
    'before publishing, such as a release date or a link. Source IDs and editorial '
    'placeholders go there, never in content.'
)
GAPS_OPEN = 'The gaps already noted are in gaps: return those still open with any new ones.'


def house_guide():
    """The house style guide every writing job reads."""
    return (REFERENCES / 'style/house.md').read_text()


def style_rule(name, voice=True):
    """How a selected kind of post sits beside the voice and the house guide. A desk job has
    no voice, only its tone and the draft's own voice, and is told so."""
    if not voice:
        return (
            'SELECTED STYLE: '
            + name
            + '. Its guide is in style.guide. The style says the shape of this kind of '
            'writing: structure, moves, length, headings and register. Keep the draft’s own '
            'voice and the tone within that shape. The style invents no facts, experience or '
            'sources. Where the style’s register differs from the house guide’s tone defaults, '
            'the style wins; the house guide still decides mechanics.'
        )
    return (
        'SELECTED STYLE: '
        + name
        + '. Its guide is in style.guide. The style says the shape of this kind of writing: '
        'structure, moves, length, headings and register. The selected voice says how its '
        'author sounds. Where they conflict on wording, the voice wins; where they conflict '
        'on structure, the style wins. Neither invents facts, experience or sources. Where '
        'the style’s register differs from the house guide’s tone defaults, the style wins; '
        'the house guide still decides mechanics.'
    )


def shared_guidance(style=None, tone='', length=None):
    """What every desk job shares with a run's writing steps: the tone, the house guide, the
    kind of post and, where the job writes new text, the length. A desk blog writes with its
    tone only; no voice guide is read here."""
    tone = (tone or '').strip()
    parts = ['No author voice is pinned; keep the draft’s own voice.' + tone_nudge({'tone': tone})]
    parts.append(house_guide())
    if style:
        parts.append(style_rule(style['name'], voice=False))
    if LENGTHS.get(length):
        parts.append(LENGTHS[length])
    return '\n\n'.join(parts)


def job(root, ident):
    found = survey(root, ident)
    stage = found['next']
    if not stage:
        raise ValueError('This run is complete.')
    directory, record, run = load(root, ident)
    # A readable gate fallback must not turn a damaged published bundle into a new job.
    published = None
    if run.get('research_contract') and run['stages'].get('research'):
        published = research_contract.read_bundle(directory / 'research')
    payload = inputs(root, record, run)
    if stage == 'claims-map':
        payload['sources'] = claims_map.material(payload['sources'])
    payload.setdefault('style', None)
    if run.get('research_skipped'):
        payload['research_policy'] = 'none'  # The job payload is not hashed; pins hold.
        payload.pop('research_from', None)
    evidence = payload['sources']  # What the carried-over check may still allow below.
    # The package works from the saved writing, and only evidence checks review against
    # sources. inputs() above still refuses a changed source pin for every step.
    check = run.get('editor_check')
    if stage == 'package' or (stage == 'review' and check and check not in studio.SOURCE_CHECKS):
        payload['sources'] = []
    if stage == 'package':
        payload['examples'] = []
    if (
        run.get('research_contract')
        and stage not in ('research-plan', 'research')
        and run['stages'].get('research')
    ):
        directory, _ = studio.item(root, 'articles', record['id'])
        facts, manifest = published
        payload['research_bundle'] = {
            'digest': manifest['digest'],
            'brief': (directory / 'research/brief.md').read_text(),
            'findings': facts['findings'],
            'facts': facts['facts'],
            'sources': facts['sources'],
        }
    payload['documents'] = {}
    for name in run['pipeline']:
        path = studio.inside(directory, STAGES[name][1])
        if path.is_file():
            payload['documents'][name] = path.read_text()
        if name == stage:
            break
    if run['existing']:
        path = directory / ('DRAFT.md' if (directory / 'DRAFT.md').is_file() else 'ORIGINAL.md')
        payload['documents']['manuscript'] = path.read_text()
        if stage == 'review' and run.get('editor_check'):
            from manuscript_preview import text_only

            payload['documents']['manuscript'] = text_only(payload['documents']['manuscript'])
    if run.get('mode') == 'from-outline':
        payload['documents']['outline'] = (directory / 'OUTLINE.md').read_text()
    saved = run['stages'].get(stage, {})
    request = saved.get('request', '') or run.get('editor_request', '')
    # A note for this step is kept beside the run, outside its versioned state, so leaving
    # one never changes the version a worker is checked against.
    note = (engine(root).local(ident).get('notes') or {}).get(stage, '')
    payload['changes'] = '\n'.join(part for part in (request, note) if part)
    # The research, asked for again with its sources read again.
    payload['refresh'] = stage == 'research' and saved.get('refresh') is True
    if len(json.dumps(payload)) > 600_000:
        raise ValueError('This job needs smaller source excerpts. Continue it in chat.')
    # A request against a version the author has already seen, or their own manuscript,
    # edits it. Otherwise (a developed idea, a first attempt) it directs a new document.
    edit = stage != 'angles' and bool(
        request
        and payload['documents'].get(stage, '').strip()
        and not (stage == 'review' and run.get('editor_check'))
        and (
            saved.get('hash') or saved.get('apply_review') or (stage == 'draft' and run['existing'])
        )
    )
    # A focused edit or a single editor check other than shape keeps to its own scope, so
    # it gets no style. The job payload is not hashed; stage pins come from inputs().
    if edit or run.get('editor_check') not in (None, 'shape'):
        payload['style'] = None
    references = Path(__file__).resolve().parents[1] / 'references'
    if edit:
        guidance = (
            f'Edit the saved {STAGES[stage][0].lower()} in documents.{stage}. This is a minimal '
            'edit, not a rewrite: apply the author’s request at the end of this guidance and '
            'keep everything else verbatim.\n\n' + (references / 'minimal-edits.md').read_text()
        )
    elif stage == 'draft' and run['existing']:
        guidance = (
            'Revise the supplied manuscript in the scope of its brief. Preserve its stance, '
            'meaningful qualifiers and author voice; retain unsupported claims as questions '
            'rather than inventing support.\n\n' + (references / GUIDES[stage]).read_text()
        )
    else:
        guidance = STAGES[stage][2] + '\n\n' + (references / GUIDES[stage]).read_text()
    guidance = brief_line(root, record, payload) + '\n\n' + guidance
    if run.get('research_skipped'):
        guidance += (
            '\n\nThe author continued without research: there is no research_bundle and no '
            'research findings. Work from the brief and the supplied sources; mark a claim that '
            'needs evidence they lack as unresolved.'
        )
    guidance += '\n\n' + house_guide()
    if payload['style'] and stage in ('outline', 'draft', 'review', 'package'):
        guidance += '\n\n' + style_rule(payload['style']['name'])
    if LENGTHS.get(run.get('length')) and stage in ('outline', 'draft') and not edit:
        guidance += '\n\n' + LENGTHS[run['length']]
    if stage in ('draft', 'review'):
        requested = run.get('editor_check')
        guides = ['modules/blog-voice-check.md', 'style/software.md']
        if requested in ('polish', 'humanization', None):
            guides.append('modules/blog-humanize.md')
        if requested in ('factual-support', None):
            guides += ['modules/blog-fact-check.md', 'review/evidence.md']
        if requested == 'geo':
            guides += ['modules/blog-geo-review.md', 'review/evidence.md']
        if requested == 'shape':
            guides.append('modules/copywriting.md')
        for guide in guides:
            guidance += '\n\n' + (references / guide).read_text()
        guidance += '\nApply only the requested checks and editing scope. Preserve the original author voice, stance and qualifiers. Report exact passages, evidence and unresolved gaps. Linked helper instructions are guidance; do not claim tools ran.'
    if stage in ('draft', 'review'):
        from text_checks import lint

        rules = payload['voice'].get('rules', '{}')
        rules = json.loads(rules) if isinstance(rules, str) else rules
        writing = payload['documents'].get('manuscript', payload['documents'].get('draft', ''))
        payload['mechanical_checks'] = lint(writing, rules or {})
        copied = carried(directory, run, {**payload, 'sources': evidence}, writing)
        payload['mechanical_checks']['findings'] += copied
        from text_checks import reader_facing_notes

        payload['mechanical_checks']['findings'] += reader_facing_notes(writing)
        if copied and stage == 'review':
            guidance += (
                '\nmechanical_checks lists, under rule from-example, passages the draft carried '
                'over from an example of the kind of post. A claim traced to an example and to '
                'nothing else is unsupported.'
            )
    if run.get('editor_check') in ('polish', 'humanization'):
        guidance += (
            '\n\n' + (references / 'blogforge/voice/assets/ai-tells/patterns.md').read_text()
        )
    if stage == 'angles':
        if payload['sources']:
            guidance += '\nThe uploaded files are in sources, with their names; name them in each angle’s Leans on line.'
        if request and payload['documents'].get('angles', '').strip():
            guidance += (
                '\nThe author set aside the saved angles in documents.angles. Propose three '
                'different angles that honor the author’s request; do not repeat the earlier ones.'
            )
    if payload.get('examples') and stage in ('outline', 'draft'):
        guidance += '\nThe documents in examples show the kind of post wanted; take their shape, not their facts.'
    if run.get('mode') == 'ideas' and stage == 'outline':
        guidance += '\nReturn three distinct blog angles with audience, thesis, evidence needed and tradeoffs. Stop for the author to choose; do not draft the blog.'
    if run.get('mode') == 'from-outline':
        guidance += '\n' + FROM_OUTLINE
    if stage in NOTED:
        payload['response_kind'] = 'writing-with-notes'
        guidance += '\n' + WRITING_NOTES
    if stage in NOTED:
        payload['gaps'] = gaps(directory, stage)
        if stage == 'draft':
            guidance += '\n' + GAPS_OPEN
    if stage == 'package':
        guidance += (
            '\nList the gaps (in gaps) and any new ones under a '
            '`## Needs you before publishing` heading. The titles, excerpt and description are '
            'reader-facing: no source IDs or placeholders. With no sources here, evidence stays '
            'empty at the handoff.'
        )
    if stage == 'review' and payload['sources']:
        found_evidence = stage_notes(directory, 'draft')['evidence']
        if found_evidence:
            payload['evidence'] = found_evidence
            guidance += (
                "\nevidence lists the draft's claims with the source ID and passage behind each; "
                'check them against the sources.'
            )
    if stage == 'review' and run.get('editor_check'):
        payload['response_kind'] = 'editing-review'
        guidance += (
            '\nReturn the structured editing review required by the response schema: summary, findings and notes. '
            'Use at most 100 findings with distinct IDs containing only letters, digits, underscores or hyphens. '
            'Each before must be a verbatim contiguous quote from documents.manuscript, including its exact punctuation and whitespace. '
            'Choose a shorter quote within one plain-text run when a sentence crosses Markdown formatting or link boundaries. '
            'Do not quote a rendered or paraphrased version of the Markdown. '
            'Use kind edit/comment, after as the proposed replacement (empty for comments or deletion), '
            'context as exact surrounding manuscript text only when needed to disambiguate (otherwise empty), '
            'a concise reason, evidence as a source passage or an explanation of editorial judgment, '
            'and verdict supported/unsupported/contradicted/editorial. '
            'Do not invent a clean verdict. Return an empty findings list only with explicit coverage and limitations.'
        )
    if request:
        # The request is the author's instruction for this step, not untrusted document data.
        guidance += (
            '\n\nAUTHOR’S REQUEST FOR THIS STEP, from the author through Blog Studio. '
            + (
                'Apply it as a minimal edit of documents.' + stage + ' and change nothing '
                'it does not require.'
                if edit
                else 'Follow it within this step.'
            )
            + '\n"""\n'
            + request
            + '\n"""'
        )
    if run.get('model_profiles'):
        found['model_selection'] = model_profiles.route(
            run,
            'Blog Studio',
            stage,
            purpose=run['stages'].get(stage, {}).get('model_purpose', stage),
        )
    return found, payload, guidance


class Engine:
    """One worker at a time per workspace. Locks cover saves, never model latency."""

    def __init__(self, root, worker=blog_worker.generate):
        self.root, self.worker = root, worker
        self.closed = threading.Event()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.current = None
        self.thread = None
        self.sync_thread = None

    def local(self, ident):
        path = studio.inside(self.root, '.blog-runs', studio.identifier(ident) + '.json')
        return studio.read_json(path) if path.is_file() else {'enabled': False, 'status': 'paused'}

    def keep_local(self, ident, value):
        studio.write_json(studio.inside(self.root, '.blog-runs', ident + '.json'), value)

    def control(self, ident, action):
        found = survey(self.root, ident)
        if found['approval'] != 'page':
            raise ValueError('Choose Run this from here to move this blog from chat to the page.')
        state = self.local(ident)
        if action in ('resume', 'retry'):
            if found['complete']:
                raise ValueError('This run is already complete.')
            state.update(enabled=True, status='queued', error='', reason=None)
        elif action in ('pause', 'stop'):
            state.update(enabled=False, status='paused' if action == 'pause' else 'stopped')
            if action == 'stop' and self.current == ident:
                self.stop.set()
        else:
            raise ValueError('Unknown run control.')
        self.keep_local(ident, state)
        self.wake.set()
        return self.describe(ident)

    def note_stage(self, ident, found, local=None):
        """The stage a note left now would go with: the next job that starts. While a
        submitted stage waits for a decision, or a worker is on the next stage, that is the
        stage after it; None when there is no later stage."""
        if found['complete'] or not found['next']:
            return None
        local = self.local(ident) if local is None else local
        names = [row['stage'] for row in found['stages']]
        at = names.index(found['next'])
        busy = found['awaits'] == 'decision' or (
            local.get('status') == 'working' and self.current == ident
        )
        if not busy:
            return found['next']
        return names[at + 1] if at + 1 < len(names) else None

    def note_research(self, ident, event):
        """Note the research round that started, or a research job that ended, in this
        computer's run state. Best effort: a busy workspace skips a note, never the work."""
        try:
            with studio.locked(self.root):
                state = self.local(ident)
                research = state.setdefault('research', {})
                if 'job' in event:
                    research['jobs'] = (research.get('jobs') or [])[-59:] + [event['job']]
                elif 'outside' in event:
                    # How many found pages your sites kept out of this attempt, and which.
                    research['outside'] = event['outside']
                else:
                    research.update(round=event.get('round'), phase=event.get('phase'))
                self.keep_local(ident, state)
        except (ValueError, OSError):
            pass

    def note_job(self, ident, stage, began, metered):
        """Keep one stage job in this computer's run state: its seconds, and the tokens and
        dollars its CLI reported, each None unless every CLI job in it reported one. A job
        no CLI ran in is not kept. Best effort: a busy workspace skips a note, never the work."""
        if not metered:
            return
        tokens = [job['tokens'] for job in metered]
        dollars = [job['dollars'] for job in metered]
        entry = {
            'stage': stage,
            'seconds': round(time.monotonic() - began, 1),
            'tokens': sum(tokens) if None not in tokens else None,
            'dollars': round(sum(dollars), 4) if None not in dollars else None,
        }
        try:
            with studio.locked(self.root):
                state = self.local(ident)
                state['jobs'] = (state.get('jobs') or [])[-199:] + [entry]
                self.keep_local(ident, state)
        except (ValueError, OSError):
            pass

    def describe(self, ident, listing=False):
        found = survey(self.root, ident, listing)
        local = self.local(ident)
        # What this run has spent so far, as its stage jobs reported it on this computer.
        took = stops.took(local.get('jobs'))
        found['ahead'] = {
            **found['ahead'],
            **took,
            'spent': stops.cost(took['seconds'], took['dollars']) if took['jobs'] else None,
        }
        found['redo'] = redo(found, local.get('jobs'))
        status = local.get('status', 'paused')
        if found['complete']:
            status = 'complete'
        elif found['approval'] == 'conversation':
            status = 'in-chat'
        elif any(
            row['stage'] == found['next'] and row['status'] == 'draft' for row in found['stages']
        ):
            status = 'waiting-for-approval'
        elif status == 'working' and self.current != ident:
            status = 'queued' if local.get('enabled') else 'paused'
        elif status in ('waiting-for-approval', 'complete'):
            # The prior gate was just decided; the next job has not started yet.
            status = 'queued' if local.get('enabled') else 'paused'
        from team_workspace import driver, space

        owner = driver(self.root, ident) if space(self.root) else None
        decisions = found.get('decisions') or []
        research = None
        if found['next'] in RESEARCH_STAGES:
            saved = local.get('research') or {}
            here = Path(found['directory'])
            kept = research_draft(here, found.get('research_tie'))
            accepted = (
                here / research_contract.CASE / '.harness-research/synthesis.json'
            ).is_file()
            working = status == 'working'
            research = {
                # Through the shared contract: rounds of writing and an independent check.
                'contract': found.get('research_contract', False),
                # A draft a stopped research kept here, which Try again continues from.
                'kept': kept,
                # Where the next attempt starts: the kept draft, the accepted research, or anew.
                'from': 'kept' if kept else 'accepted' if accepted else None,
                'refusal': saved.get('refusal'),
                'rounds': research_contract.ROUNDS,
                # The round under way (0 while public sources are found), while it works.
                'round': saved.get('round') if working else None,
                'phase': saved.get('phase') if working else None,
                'last': research_cost(saved.get('jobs')),
                # Pages your sites kept out of the last attempt, named for the gate.
                'outside': outside_words(saved.get('outside')),
            }
        on_desk = (Path(found['directory']) / 'desk' / 'draft.json').is_file()
        from desk_migration import metadata as migrated_metadata

        migrated = migrated_metadata(Path(found['directory']))
        found['unfinished_migration'] = bool(migrated)
        if on_desk and migrated:
            # The old run's approval facts remain history; desk registration never
            # finishes its missing steps or turns automatic continuation into approval.
            found.update(complete=False, next=None, awaits=None)
            found['stages'] = [
                {
                    **row,
                    'status': migrated['historical_stages']
                    .get(row['stage'], {})
                    .get('status', 'pending'),
                    'auto_accepted': migrated['historical_stages']
                    .get(row['stage'], {})
                    .get('status')
                    == 'approved'
                    and row.get('accepted_by') == 'review-policy',
                }
                for row in found['stages']
            ]
            status = 'on-desk'
        elif on_desk:
            # Opened on the desk once finished: the run is read as it ended, with nothing to
            # resume, approve or redo; desk saves never make it look paused or stale.
            found.update(complete=True, next=None, awaits=None)
            found['stages'] = [{**row, 'status': 'approved'} for row in found['stages']]
            status = 'on-desk'
        return {
            **{key: value for key, value in found.items() if key != 'research_tie'},
            'team': bool(space(self.root) and space(self.root).address),
            'driver': owner,
            'status': status,
            'notes': local.get('notes') or {},
            'note_stage': self.note_stage(ident, found, local),
            # The job's start is timed only while it is the one working here.
            'started_at': local.get('started_at') if status == 'working' else None,
            'touched': decisions[-1]['at'] if decisions else None,
            'error': local.get('error', ''),
            # Why the last job stopped, when it is one the page can say more about.
            'reason': local.get('reason') if status == 'failed' else None,
            # The last lines the assistant's CLI wrote, kept on this computer only.
            'said': read_said(self.root, ident) if status == 'failed' else None,
            'research': research,
            # A finished blog may be opened on the writing desk; one already there says so.
            'desk_open': bool(
                (found['complete'] or found.get('finished'))
                and status not in ('queued', 'working')  # Its step would write DRAFT.md.
                and (Path(found['directory']) / 'DRAFT.md').is_file()
            ),
            'on_desk': on_desk,
            'enabled': local.get('enabled', False),
            'observation': 'Saved locally. Workers use your selected CLI sign-in. Public research links need review; no publishing is automatic.',
        }

    def once(self, ident):
        import brand_skill

        with brand_skill.using(quiet=True) as available:
            if available:
                return self._once(ident)

    def _once(self, ident):
        import desk_migration

        if desk_migration.blocked(self.root, ident):
            return
        if not self.local(ident).get('enabled'):
            return
        try:
            directory, _ = studio.item(self.root, 'articles', ident)
        except ValueError:
            return
        if (directory / 'desk' / 'draft.json').is_file():
            return  # On the desk: its run never starts another step.
        from team_workspace import before

        preview = survey(self.root, ident)
        if (
            not preview['complete']
            and preview['approval'] == 'page'
            and not any(
                row['stage'] == preview['next'] and row['status'] == 'draft'
                for row in preview['stages']
            )
        ):
            before(self.root, ident)
        with studio.locked(self.root):
            # A migration/conversation may have acquired the lock while this
            # runner was waiting. Recheck before cleanup or worker acquisition.
            if desk_migration.blocked(self.root, ident):
                return
            directory, record = studio.item(self.root, 'articles', ident)
            if (
                record.get('execution') == 'conversation'
                or (directory / 'desk/draft.json').is_file()
            ):
                return
            local = self.local(ident)
            if not local.get('enabled'):
                return
            found = survey(self.root, ident)
            if found['complete']:
                local.update(enabled=False, status='complete')
                self.keep_local(ident, local)
                return
            if found['approval'] != 'page' or any(
                row['stage'] == found['next'] and row['status'] == 'draft'
                for row in found['stages']
            ):
                return
            if any(
                row['stage'] == found['next'] and row['status'] == 'stale'
                for row in found['stages']
            ):
                local.update(
                    enabled=False,
                    status='needs-attention',
                    error='Saved writing or its inputs changed. Review the saved version or ask for changes before running it again.',
                )
                self.keep_local(ident, local)
                return
            from team_workspace import guard as team_guard

            team_guard(self.root, ident)
            found, payload, guidance = job(self.root, ident)
            choice = found.get('model_selection')
            if choice:
                directory, record, run = load(self.root, ident)
                attempt = sum(job['step'] == found['next'] for job in run.get('model_jobs', [])) + 1
                model_profiles.audit(
                    run, choice, attempt, 'research' if found['next'] == 'research' else 'write'
                )
                save(self.root, directory, record, run, 'Selected model for ' + found['next'])
                # Audit metadata changes the optimistic token, so use the freshly saved version.
                found['expected'] = survey(self.root, ident)['expected']
            local.update(status='working', error='', reason=None, started_at=studio.now())
            said_path(self.root, ident).unlink(missing_ok=True)  # The last failure's lines.
            if found['next'] == 'research':
                # A new attempt: its rounds and jobs replace the last one's.
                local.setdefault('research', {}).update(jobs=[], round=None, phase=None)
            self.keep_local(ident, local)
            self.current = ident
            self.stop.clear()
            # Includes session metadata as well as run/documents: a parallel edit wins.
            directory, _, run = load(self.root, ident)
            session = (directory / 'session.json').read_bytes()
            tie = found.get('research_tie')
            if found['next'] == 'research' and not research_draft(directory, tie):
                # A draft from other inputs or another research version is not continued.
                shutil.rmtree(directory / RESEARCH_DRAFT, ignore_errors=True)
            review_source = (
                (directory / 'DRAFT.md').read_text()
                if found['next'] == 'review' and run.get('editor_check')
                else None
            )
        pending = None
        review_attempts = []
        # Every CLI job this stage runs, metered: kept once it ends, whatever its outcome.
        meter, began = blog_worker.metered(), time.monotonic()
        metered = meter.__enter__()
        try:
            if found['next'] == 'research' and run.get('research_contract'):
                import synthesis_research

                pending = tempfile.TemporaryDirectory(prefix='blog-research-draft-')
                target = Path(pending.name)
                # Continue from the draft a stopped research kept, else the last reviewed case.
                origin = directory / RESEARCH_DRAFT
                if not origin.is_dir():
                    origin = directory / research_contract.CASE
                if origin.is_dir():
                    research_contract.copy_case(origin, target / research_contract.CASE)
                    for name in DRAFT_ONLY:
                        (target / research_contract.CASE / name).unlink(missing_ok=True)
                result = synthesis_research.generate(
                    target,
                    run,
                    payload,
                    self.worker,
                    seconds=found['seconds'],
                    stop=self.stop,
                    progress=lambda event: self.note_research(ident, event),
                )
            else:
                started = time.monotonic()
                result = self.worker(
                    found['engine'],
                    payload,
                    guidance,
                    seconds=found['seconds'],
                    web=found['next'] == 'research' and searches_web(payload),
                    stop=self.stop,
                    model_selection=found.get('model_selection'),
                )
            if found['next'] == 'claims-map':
                said = claims_map.problems(result['content'], payload['sources'])
                if said:
                    remaining = found['seconds'] - (time.monotonic() - started)
                    if self.stop.is_set() or self.closed.is_set() or remaining <= 0:
                        raise ValueError(
                            'The claims map quoted passages that are not in your material: '
                            + said[0]
                        )
                    result = self.worker(
                        found['engine'],
                        {
                            **payload,
                            'previous_output': result.get('content', ''),
                            'validation_error': said[0],
                        },
                        guidance
                        + '\nCorrect the previous output once. Quote each passage exactly from its named source; do not judge the claims.',
                        seconds=max(1, int(remaining)),
                        web=False,
                        stop=self.stop,
                        model_selection=found.get('model_selection'),
                    )
                    said = claims_map.problems(result['content'], payload['sources'])
                    if said:
                        raise ValueError(
                            'The claims map quoted passages that are not in your material: '
                            + said[0]
                        )
            if found['next'] == 'review' and run.get('editor_check'):
                from manuscript_editor import validate_review

                try:
                    validate_review(result, review_source)
                except ValueError as error:
                    review_attempts.append({'response': result, 'error': str(error)})
                    remaining = found['seconds'] - (time.monotonic() - started)
                    if self.stop.is_set() or self.closed.is_set() or remaining <= 0:
                        raise error
                    result = self.worker(
                        found['engine'],
                        {
                            **payload,
                            'previous_output': result.get('content', ''),
                            'validation_error': str(error),
                        },
                        guidance
                        + '\nCorrect the previous output once using the structured editing review schema. '
                        'Each before must be copied verbatim from the supplied manuscript, preserving punctuation and whitespace. '
                        'Use kind edit/comment, verdict editorial for writing advice, and a short evidence explanation. '
                        'Use IDs containing only letters, digits, underscores or hyphens. '
                        'Do not remove legitimate findings to evade validation.',
                        seconds=max(1, int(remaining)),
                        web=False,
                        stop=self.stop,
                        model_selection=found.get('model_selection'),
                    )
                    try:
                        validate_review(result, review_source)
                    except ValueError as error:
                        review_attempts.append({'response': result, 'error': str(error)})
                        raise
            with studio.locked(self.root):
                if self.stop.is_set() or self.closed.is_set():
                    if pending and not self.closed.is_set():
                        keep_research(directory, target / research_contract.CASE, tie)
                    return
                if (directory / 'session.json').read_bytes() != session:
                    raise ValueError(
                        'The blog changed while the worker ran. Your edit was kept. Retry from the latest version.'
                    )
                from team_workspace import before

                before(self.root, ident)
                if pending:
                    guard(self.root, ident, found['expected'], page=True)
                    research_contract.copy_case(
                        target / research_contract.CASE, directory / research_contract.CASE
                    )
                    research_contract.publish(
                        target / research_contract.CASE, directory / 'research'
                    )
                submit(self.root, ident, found['next'], result, found['expected'], page=True)
                state = self.local(ident)
                state.update(status='waiting-for-approval', error='')
                if pending:
                    # submit() let any kept draft go: the accepted research replaces it.
                    state.setdefault('research', {}).update(refusal=None, round=None, phase=None)
                if run.get('editor_check'):
                    state['enabled'] = False
                self.keep_local(ident, state)
        except Exception as exc:
            with studio.locked(self.root):
                state = self.local(ident)
                # Research that did not finish is kept for Try again, even when stopped.
                kept = (
                    keep_research(directory, target / research_contract.CASE, tie)
                    if pending and not self.closed.is_set()
                    else False
                )
                if not self.stop.is_set() and not self.closed.is_set():
                    message = (
                        str(exc)
                        if isinstance(exc, (ValueError, OSError))
                        else 'The worker failed. Retry this step; saved work is kept.'
                    )
                    if review_attempts:
                        try:
                            folder = studio.inside(self.root, '.blog-runs', 'diagnostics')
                            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                            folder.chmod(0o700)
                            diagnostic = folder / (ident + '.json')
                            studio.write_json(
                                diagnostic,
                                {
                                    'check': run.get('editor_check'),
                                    'at': studio.now(),
                                    'manuscript_sha256': studio.digest(review_source.encode()),
                                    'attempts': review_attempts,
                                },
                            )
                            diagnostic.chmod(0o600)
                        except OSError:
                            message += ' The private failure diagnostic could not be saved.'
                    reason = getattr(exc, 'reason', None)
                    if reason == 'time-limit':
                        # The limit this blog has, whatever a research job had left of it.
                        message = (
                            ('Research' if pending else 'This step')
                            + ' ran out of the time a step may take ('
                            + blog_worker.minutes(found['seconds'])
                            + ').'
                        )
                    said = getattr(exc, 'said', None) if reason == 'cli' else None
                    if said:
                        try:
                            keep_said(self.root, ident, found['next'], found['engine'], said)
                        except OSError:
                            message += ' What the assistant said could not be kept.'
                    if pending:
                        refused = isinstance(exc, research_contract.ReviewRefused)
                        reason = 'research-check' if refused else reason
                        research = state.setdefault('research', {})
                        research.update(round=None, phase=None)
                        research['refusal'] = (
                            research_refusal(exc, target / research_contract.CASE)
                            if refused
                            else None
                        )
                        if refused:
                            message = refusal_words(research['refusal'])
                        message = fitted(message, research_kept_words(kept, refused))
                    state.update(
                        enabled=False,
                        status='failed',
                        error=message[:500],
                        reason=reason if reason in FAILURES else None,
                    )
                    self.keep_local(ident, state)
        finally:
            meter.__exit__(None, None, None)
            self.note_job(ident, found['next'], began, metered)
            if pending:
                pending.cleanup()
            self.current = None

    def sync_team(self):
        from team_workspace import keep_desk_leftovers, refresh

        while not self.closed.is_set():
            try:
                keep_desk_leftovers(self.root)  # So the check is never refused for them.
                refresh(self.root)
            except (ValueError, OSError) as exc:
                # A failed background check remains visible until a successful one.
                from team_workspace import space, internal
                from studio_sync import support

                found = space(self.root)
                if found:
                    with support.locked(found.repo / '.git/blog-studio.lock'), internal():
                        prior = support.read_json(self.root / '.team-sync.json', {})
                        prior = prior if isinstance(prior, dict) else {}
                        studio.write_json(
                            self.root / '.team-sync.json',
                            {**prior, 'report': {'shared': False, 'notice': str(exc)[:500]}},
                        )
            if self.closed.wait(60):
                return

    def serve(self):
        import tool_jobs

        with studio.locked(self.root):
            tool_jobs.recover(self.root)
        while not self.closed.is_set():
            folder = studio.inside(self.root, '.blog-runs')
            for path in sorted(folder.glob('*.json')) if folder.exists() else []:
                if self.closed.is_set():
                    break
                try:
                    self.once(path.stem)
                except Exception as exc:
                    with studio.locked(self.root):
                        state = self.local(path.stem)
                        state.update(enabled=False, status='failed', error=str(exc)[:500])
                        self.keep_local(path.stem, state)
            if not self.closed.is_set():
                try:
                    tool_jobs.once(self)
                except Exception:
                    # A tool job that failed to be recorded never takes the loop down with it.
                    self.current = None
            self.wake.wait(1)
            self.wake.clear()

    def start(self):
        from team_workspace import space

        if space(self.root):
            self.sync_thread = threading.Thread(target=self.sync_team, daemon=True)
            self.sync_thread.start()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def close(self):
        self.closed.set()
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=5)
        if self.sync_thread:
            self.sync_thread.join(timeout=5)


def engine(root):
    return ENGINES.setdefault(str(root), Engine(root))


def catalog(root):
    import desk
    import desk_jobs

    rows = []
    working = desk_jobs.active(root)
    for path in sorted(studio.inside(root, 'articles').glob('*/session.json')):
        ident = path.parent.name
        try:
            # A blog on the writing desk, including a finished run opened there, lists as one.
            on_desk = studio.inside(path.parent, 'desk', 'draft.json')
            if on_desk.is_file() and not on_desk.is_symlink():
                draft = studio.read_json(on_desk)
                busy = working.get(ident, 0)
                # Marked as published: finished, out of In progress.
                published = (studio.read_json(path).get('editorial') or {}).get(
                    'stage'
                ) == 'published' and not busy
                # A start that stopped (a failed research, a Stop) needs the person.
                stopped = (
                    '' if busy else desk_jobs.stalled(root, ident, desk.read_start(root, ident))
                )
                rows.append(
                    {
                        'id': ident,
                        'title': draft['title'],
                        'status': 'working'
                        if busy
                        else 'failed'
                        if stopped
                        else 'complete'
                        if published
                        else 'desk',
                        'touched': draft['updated_at'],
                        'flow': 'desk',
                        'jobs': busy,
                        'complete': published,
                        'stages': [],
                        'next': None,
                        'error': stopped,
                        'mode': 'desk',
                    }
                )
                continue
            if studio.inside(path.parent, STATE).is_file():
                found = engine(root).describe(ident, listing=True)
                rows.append(
                    {
                        k: found[k]
                        for k in (
                            'id',
                            'title',
                            'status',
                            'next',
                            'approval',
                            'error',
                            'stages',
                            'complete',
                            'engine',
                            'mode',
                            'editor_check',
                            'team',
                            'driver',
                            'touched',
                            'desk_open',
                        )
                    }
                )
        except (ValueError, OSError, KeyError):
            rows.append(
                {
                    'id': ident,
                    'title': ident,
                    'status': 'needs-attention',
                    'error': 'Open this blog in chat to inspect its saved context.',
                }
            )
    rows.sort(key=lambda row: row.get('touched') or '', reverse=True)
    import blog_delete

    return {'items': rows, 'total': len(rows), 'deleted': blog_delete.deleted(root)}


def default_voice(root):
    """The voice a new blog gets when the page sends no profile: personal or team, or None.

    Reads only. A team default is named from its Team Hub revision without checking it
    out; creating the blog checks it out, as in chat."""
    import writing_defaults
    from hub_store import HubError
    from hub_workspace import active

    # Whatever stops the read (a Team Hub not joined here, a damaged record), the run options
    # still answer: they just offer no default voice.
    if not studio.voices_on(root):
        return None  # No default voice is applied while the older voice tools are off.
    try:
        adapter = active(root)
        found = writing_defaults.resolve(root, adapter=adapter)['values'].get('voice')
        if not found:
            return None
        if found['scope'] == 'team':
            shared = adapter.hub.graph()['revisions'][found['value']['revision']]
            saved = (shared.get('data') or {}).get('studio') or {}
            if saved.get('status') == 'retired':
                return None
            return {
                'scope': 'team',
                'profile': None,
                'name': saved.get('name') or shared.get('title'),
                'revision': found['value']['revision'],
                'status': saved.get('status'),
            }
        pin = found['value']
        directory, current = studio.item(root, 'profiles', pin['profile_id'])
        pinned = studio.read_json(
            studio.inside(directory, 'revisions', str(pin['revision']), 'record.json')
        )
    except (ValueError, OSError, KeyError, TypeError, HubError):
        return None
    if current.get('status') == 'retired':
        return None  # A new blog cannot take it; creating one says so.
    return {
        'scope': found['scope'],
        'profile': pin['profile_id'],
        'name': pinned['name'],
        'revision': pin['revision'],
        'status': pinned['status'],
    }


def options(root):
    def records(kind):
        result = []
        for path in sorted(studio.inside(root, kind).glob('*/record.json')):
            record = studio.read_json(path)
            if kind == 'sources' and 'material' in record.get('purposes', []):
                continue  # Uploaded for one run; chosen on its own screen, not from the library.
            if kind != 'profiles' or record.get('status') != 'retired':
                result.append(
                    {
                        'id': record['id'],
                        'name': record['name'],
                        'status': record['status'],
                        **({'purposes': record.get('purposes', [])} if kind == 'sources' else {}),
                    }
                )
        return result

    agents = {}
    for name in ('codex', 'claude'):
        try:
            blog_worker.source_curator.executable(name)
            agents[name] = True
        except ValueError:
            agents[name] = False

    import brand_skill
    import styles

    brand = brand_skill.status()
    brand['default'] = brand_skill.defaults(brand)
    return {
        'default_voice': default_voice(root),
        'profiles': records('profiles'),
        'styles': styles.catalog(root)['styles'],
        'sources': records('sources'),
        'agents': agents,
        'settings': settings(root),
        'brand': brand,
    }


def strip_preservation(notes):
    """Read the old structured suffix without showing raw JSON as an assistant note."""
    before, marker, encoded = notes.rpartition('Preservation check: ')
    if not marker or before and not before.endswith('\n'):
        return notes, None
    try:
        check = json.loads(encoded)
    except (ValueError, TypeError):
        return notes, None
    if not isinstance(check, dict) or not isinstance(check.get('changes'), dict):
        return notes, None
    return before.rstrip(), check


def gate_checks(stage, content, rules, copied, preservation, handoff=None):
    from text_checks import lint

    rows = []
    if stage in ('draft', 'review', 'package'):
        findings = lint(content, rules or {})['findings']
        groups = {}
        repeated = []
        for finding in findings:
            if finding['rule'] == 'duplicate-paragraph':
                repeated.append(finding)
            else:
                groups.setdefault(finding['rule'], []).append(finding)
        mechanical = any(rule != 'echoed-opener' for rule in groups)
        configured = any(
            (rules or {}).get(key)
            for key in (
                'no_em_dashes',
                'no_ascii_double_hyphen',
                'banished_words',
                'banished_phrases',
            )
        )
        if configured and not mechanical:
            rows.append({'label': 'No voice rule broken', 'passed': True})
        for rule, matches in groups.items():
            label = {
                'em-dash': 'em dashes',
                'double-hyphen': 'double hyphens',
                'echoed-opener': 'repeated section openings',
            }.get(rule, rule)
            if rule.startswith('banished:'):
                label = 'uses of “' + rule.partition(':')[2] + '”'
            detail = []
            for match in matches[:5]:
                line = match.get('line')
                if line is None and match.get('start') is not None:
                    line = content.count('\n', 0, match['start']) + 1
                detail.append(
                    (f'line {line}: ' if line is not None else '') + match['target'][:160]
                )
            rows.append({'label': f'{len(matches)} {label}', 'passed': False, 'detail': detail})
        from text_checks import reader_facing_notes

        noted = reader_facing_notes(content)
        rows.append(
            {
                'label': 'Source IDs or editorial notes in the writing'
                if noted
                else 'No source IDs or editorial notes in the writing',
                'passed': not noted,
                'detail': [f'line {item["line"]}: ' + item['target'][:160] for item in noted[:5]],
            }
        )
        rows.append(
            {
                'label': f'{len(repeated)} paragraphs repeat'
                if repeated
                else 'No paragraph repeats',
                'passed': not repeated,
                'detail': [item['target'][:160] for item in repeated[:5]],
            }
        )
        if copied is not None:
            rows.append(
                {
                    'label': 'Carried over from an example'
                    if copied
                    else 'No passage carried over from an example',
                    'passed': not copied,
                    'detail': [item['target'][:120] for item in copied],
                }
            )
        if handoff is not None:
            kept = re.sub(
                r'(?ims)^##[^\n]*(?:needs you before publishing|finding)[^\n]*\n.*?(?=^## |\Z)',
                lambda m: '\n' * m.group().count('\n'),
                handoff,
            )
            noted = reader_facing_notes(kept)
            rows.append(
                {
                    'label': 'Source IDs or editorial notes in the handoff'
                    if noted
                    else 'No source IDs or editorial notes in the handoff',
                    'passed': not noted,
                    'detail': [
                        f'line {item["line"]}: ' + item['target'][:160] for item in noted[:5]
                    ],
                }
            )
        if preservation is not None:
            changed = bool(preservation.get('needs_review'))
            rows.append(
                {
                    'label': 'Numbers, links or quotations changed'
                    if changed
                    else 'Numbers, links and quotations kept',
                    'passed': not changed,
                    'detail': list(preservation.get('changes') or {}),
                }
            )
    return rows or [{'label': f'No automatic checks apply to {STAGES[stage][0]}.', 'passed': True}]


def document(root, ident, stage):
    from manuscript_preview import fields

    def preview_file(path):
        body = path.read_text()
        return {'content': body, **fields(body)}

    directory, record, run = load(root, ident)
    if stage not in run['pipeline']:
        raise ValueError('Choose a stage in this blog’s run.')
    path = studio.inside(directory, STAGES[stage][1])
    content = path.read_text()
    copied = None
    context = inputs(root, record, run) if stage in ('draft', 'review', 'package') else None
    if stage in ('draft', 'review', 'package') and any(
        'inspiration' in selected['purposes'] for selected in record['sources']
    ):
        draft = directory / 'DRAFT.md'
        copied = carried(
            directory,
            run,
            context,
            draft.read_text() if draft.is_file() else '',
        )
    previous = None
    approved = run.get('approved', {}).get(stage, '')
    if re.fullmatch('[a-f0-9]{64}', approved):
        before = studio.inside(
            directory, 'history', 'derived-blog-approved-' + stage + '-' + approved + '.md'
        )
        if before.is_file() and studio.digest(before.read_bytes()) == approved:
            previous = before.read_text()
    found = survey(root, ident)
    row = next(row for row in found['stages'] if row['stage'] == stage)
    notes, legacy = strip_preservation(row['notes'])
    drafted = run['stages'].get('draft') or {}
    preservation = (
        drafted.get('preservation') or legacy or strip_preservation(drafted.get('notes', ''))[1]
    )
    rules = (context or {}).get('voice', {}).get('rules') or {}
    if isinstance(rules, str):
        rules = json.loads(rules)
    draft_path = studio.inside(directory, 'DRAFT.md')
    checked_text = (
        draft_path.read_text()
        if stage in ('review', 'package') and draft_path.is_file()
        else content
    )
    differences = (
        list(
            difflib.unified_diff(
                (previous or '').splitlines(),
                content.splitlines(),
                fromfile='Last approved',
                tofile='This version',
                n=3,
            )
        )
        if previous is not None
        else []
    )
    plan_path = directory / STAGES['research-plan'][1]
    questions = planning_questions(plan_path.read_text()) if plan_path.is_file() else []
    return {
        **(
            {
                'research': research_view.account(directory / 'research', questions)
                if run.get('research_contract')
                else None
            }
            if stage == 'research'
            else {}
        ),
        'name': path.name,
        'content': content,
        **fields(content),
        'previous': previous,
        'diff': differences[:4000],
        'diff_truncated': len(differences) > 4000,
        'stage': stage,
        'review_level': found['review_level'],
        # Grouped reviews read the approved stages together; the final stop always brings
        # the approved draft back beside the handoff notes, whatever the review level.
        'bundle': [
            {
                'stage': item['stage'],
                'label': item['label'],
                **preview_file(studio.inside(directory, item['path'])),
            }
            for item in found['stages']
            if stage == found['next']
            and item['stage'] != stage
            and item['status'] == 'approved'
            and (
                found['review_level'] != 'step_by_step'
                or item['stage'] == 'draft'
                and stage == run['pipeline'][-1]
            )
        ],
        'label': row['label'],
        'status': row['status'],
        'notes': notes,
        'expected': found['expected'],
        'checks': gate_checks(
            stage,
            checked_text,
            rules,
            copied,
            preservation,
            content if stage == 'package' else None,
        ),
        'gaps': gaps(directory, stage) if stage in NOTED else [],
        'id': ident,
        'title': found['title'],
    }


# What the page asks of a guided run. Anything else is answered as an unknown route: a new
# run starts in chat, with the CLI's `run create`.
PAGE_ACTIONS = (
    'adopt',
    'apply-review',
    'approve',
    'changes',
    'develop',
    'handoff',
    'note',
    'pause',
    'resume',
    'retry',
    'skip-research',
    'start',
    'stop',
)


def dispatch(root, action, data):
    """Called only by the authenticated page, under the ordinary desk mutation lock."""
    if action not in PAGE_ACTIONS:
        raise ValueError('Unknown management action.')
    runner = engine(root)
    ident = data.get('id')
    if isinstance(ident, str):
        import desk

        desk.refuse_on_desk(studio.item(root, 'articles', ident)[0])
    if (
        set(data)
        - {'id', 'expected', 'request', 'stage'}
        - ({'seconds'} if action == 'retry' else set())
    ):
        raise ValueError('Unknown run field.')
    # Every page control is bound to the version the person was shown.
    found = survey(root, ident)
    if not data.get('expected') or data['expected'] != found['expected']:
        raise ValueError('This blog changed. Reload before deciding.')
    if action == 'apply-review':
        guard(root, ident, data['expected'], page=True)
        directory, record, run = load(root, ident)
        review_file = studio.inside(directory, STAGES['review'][1])
        if not review_file.is_file():
            raise ValueError('There is no review to apply yet.')
        if (
            found['next'] not in ('review', 'package')
            or next(row['status'] for row in found['stages'] if row['stage'] == found['next'])
            != 'draft'
        ):
            raise ValueError('Apply findings while the review or handoff waits for you.')
        if runner.current == ident:
            raise ValueError('Wait for the current writing step to stop before applying findings.')
        review = review_file.read_text(encoding='utf-8')
        decide(root, ident, data['expected'], 'changes', APPLY_REQUEST, page=True, target='draft')
        directory, record, run = load(root, ident)
        run['stages']['draft'].update(request=APPLY_REQUEST + '\n\n' + review, apply_review=True)
        if 'package' not in run['pipeline']:
            run['pipeline'].append('package')
        record['stop_point'] = 'package'
        save(root, directory, record, run, 'Apply only the review’s findings')
        return runner.control(ident, 'resume')
    if action == 'develop':
        guard(root, ident, data['expected'], page=True)
        directory, record, run = load(root, ident)
        if run.get('mode') == 'from-files':
            choose_angle(root, directory, record, run, found, data.get('request', ''))
            return runner.control(ident, 'resume')
        if run.get('mode') not in ('ideas', 'outline') or not (directory / 'OUTLINE.md').is_file():
            raise ValueError('Choose a saved idea or outline before developing it.')
        request = text(data.get('request', ''), 'selected angle', 8000, required=True)
        run['mode'] = 'write'
        run['pipeline'] = ['outline', 'draft', 'review', 'package']
        run['stages'] = {
            'outline': {
                'status': 'pending',
                'request': 'Develop this selected angle or structure: ' + request,
            }
        }
        record['stop_point'] = 'package'
        save(root, directory, record, run, 'Selected angle for drafting')
        return runner.control(ident, 'resume')
    if action == 'start':
        if found['approval'] == 'conversation':
            decide(root, ident, data['expected'], 'handoff')
        return runner.control(ident, 'resume')
    if action == 'retry' and 'seconds' in data:
        # Try again with more time: the limit that just ran out is raised for every step.
        seconds = data['seconds']
        if type(seconds) is not int or not 30 <= seconds <= 3600:
            raise ValueError('Choose a step time limit between 30 and 3600 seconds.')
        if found['approval'] != 'page':
            raise ValueError('Choose Run this from here to move this blog from chat to the page.')
        directory, record, run = load(root, ident)
        run['seconds'] = seconds
        save(root, directory, record, run, f'Step time limit set to {seconds} seconds')
    if action in ('resume', 'retry', 'pause', 'stop'):
        return runner.control(ident, action)
    if action == 'note':
        # A note for the next job that starts. It is kept beside the run, in its local
        # state, never in the versioned record: leaving one stops nothing and changes no
        # version a running worker is checked against. job() folds it into that stage's
        # request when the stage starts.
        request = text(data.get('request', ''), 'note', 8000, required=True)
        stage = runner.note_stage(ident, found)
        if stage is None:
            raise ValueError(
                'There is no later step for a note to go with. Ask for changes to '
                + (STAGES[found['next']][0].lower() if found['next'] else 'a stage')
                + ' instead.'
            )
        state = runner.local(ident)
        notes = state.setdefault('notes', {})
        notes[stage] = (notes.get(stage, '') + '\n' + request).strip()
        runner.keep_local(ident, state)
        return {**runner.describe(ident), 'noted': stage}
    if action == 'skip-research':
        # Continue without research: from a run stopped at its research, on the page.
        guard(root, ident, data['expected'], page=True)
        if found['next'] not in RESEARCH_STAGES:
            raise ValueError('This blog is not waiting on research. Continue it as usual.')
        if found['awaits'] == 'decision':
            raise ValueError(
                'Decide on the '
                + STAGES[found['next']][0].lower()
                + ' first: approve them or ask for changes.'
            )
        if runner.current == ident:
            raise ValueError(
                'Research is stopping; try again in a moment.'
                if runner.stop.is_set()
                else 'Research is still working. Stop the research first, then continue without it.'
            )
        directory, record, run = load(root, ident)
        skip_research(root, directory, record, run, found['next'])
        shutil.rmtree(directory / RESEARCH_DRAFT, ignore_errors=True)
        state = runner.local(ident)
        state.pop('research', None)
        runner.keep_local(ident, state)
        return runner.control(ident, 'resume')
    if action == 'adopt':
        if not found['next'] or not found['content']:
            raise ValueError('There is no saved stage to review.')
        submit(
            root,
            ident,
            found['next'],
            {
                'content': found['content'],
                'notes': 'The saved version was brought back for your review. Earlier assistant notes remain in history.',
            },
            data['expected'],
            page=True,
        )
        return runner.describe(ident)
    if data.get('refresh', False) not in (True, False):
        raise ValueError('Say whether to bring the evidence up to date with true or false.')
    result = decide(
        root,
        ident,
        data['expected'],
        action,
        data.get('request', ''),
        page=True,
        target=data.get('stage'),
        refresh=data.get('refresh') is True,
    )
    if action == 'handoff':
        state = runner.local(ident)
        state.update(enabled=False, status='in-chat')
        runner.keep_local(ident, state)
        if runner.current == ident:
            runner.stop.set()
    elif action == 'changes' and runner.current == ident:
        runner.stop.set()
    runner.wake.set()
    return {**result, **runner.describe(ident)}


def angles(content):
    """The saved angles: each `## Title` heading with the line beneath it."""
    found = []
    lines = str(content or '').splitlines()
    for index, line in enumerate(lines):
        match = re.fullmatch(r'##\s+(.+?)\s*#*\s*', line)
        if not match:
            continue
        says = ''
        for later in lines[index + 1 :]:
            if later.startswith('#'):
                break
            if later.strip():
                says = re.sub(r'^[-*]\s+', '', later.strip())
                break
        title = re.sub(r'^\d+[.)]\s*', '', match.group(1)).replace('**', '').strip()
        found.append({'title': title, 'says': says})
    return found


def choose_angle(root, directory, record, run, found, request):
    """The chosen angle becomes the blog's title, point and reader; the normal run follows."""
    if run.get('angles') is False:
        raise ValueError('This blog has no angles to choose from.')
    saved = run['stages'].get('angles', {})
    if found['next'] != 'angles' or saved.get('status') != 'draft':
        raise ValueError('Wait for the three angles before choosing one.')
    request = text(request, 'selected angle', 8000, required=True)
    title, _, note = request.partition('\n')
    doc = (directory / STAGES['angles'][1]).read_text()
    angle = next(
        (item for item in angles(doc) if item['title'].casefold() == title.strip().casefold()),
        None,
    )
    if angle is None:
        raise ValueError('Choose one of the saved angles by its heading.')
    headings = [item['title'].casefold() for item in angles(doc)]
    if len(set(headings)) != len(headings):
        raise ValueError('Two angles share a heading. Ask for three different ones instead.')
    parts = [part.strip() for part in re.split(r'\s[·•|]\s', angle['says'])]
    audience = parts[0] if len(parts) >= 2 else ''
    point = parts[1] if len(parts) >= 2 else angle['says']
    record['title'] = angle['title']
    record.setdefault('writing_preferences', {})
    if audience:
        record['writing_preferences']['audience'] = audience
    run['brief'] = {
        'goal': point or run['brief']['goal'],
        'audience': audience or run['brief']['audience'],
    }
    after = run.get('after_angles') or {'research': 'none', 'stop': 'package'}
    pipeline = ['research-plan', 'research'] if after['research'] == 'web-allowed' else []
    pipeline += ['outline', 'draft', 'review', 'package']
    # The angles stay at the head of the run, decided by the pick.
    run['pipeline'] = ['angles'] + pipeline[: pipeline.index(after['stop']) + 1]
    run['chosen_angle'] = {'title': angle['title'], 'says': angle['says']}
    _accept(directory, run, 'angles', 'page' if run['approval'] == 'page' else 'conversation')
    run['stages'] = {
        'angles': run['stages']['angles'],
        'outline': {
            'status': 'pending',
            'request': (
                'Develop this selected angle: '
                + angle['title']
                + ('\n' + angle['says'] if angle['says'] else '')
                + ('\n' + note.strip() if note.strip() else '')
            ),
        },
    }
    record['stop_point'] = after['stop']
    # The brief and title just changed with the pick; the decided angles are pinned to them.
    run['stages']['angles']['basis'] = basis(root, directory, record, run, 'angles')
    save(root, directory, record, run, 'Chose the angle: ' + angle['title'])


def add_parser(groups):
    commands = groups.add_parser('run', help='Saved step-by-step Blog Studio work').add_subparsers(
        dest='action', required=True
    )
    create_cmd = commands.add_parser('create')
    for name in (
        'title',
        'author',
        'audience',
        'goal',
        'tone',
        'profile',
        'style',
        'id',
        'brand',
        'variant',
    ):
        create_cmd.add_argument('--' + name)
    create_cmd.add_argument(
        '--research',
        choices=OLD_RESEARCH,
        default=None,
        help='Older words: none, supplied-only (your documents) or web-allowed (your '
        'documents and the public web)',
    )
    create_cmd.add_argument(
        '--research-from',
        default=None,
        help='Where research may look: documents, sites and/or web, comma separated',
    )
    create_cmd.add_argument(
        '--site',
        action='append',
        default=[],
        help='A site for this blog only (repeatable); with sites, replaces the shared list',
    )
    create_cmd.add_argument(
        '--stop', choices=('outline', 'draft', 'review', 'package'), default='package'
    )
    create_cmd.add_argument('--length', choices=tuple(LENGTHS), default=None)
    create_cmd.add_argument('--engine', choices=('codex', 'claude'))
    create_cmd.add_argument('--seconds', type=int, default=600)
    create_cmd.add_argument('--source', action='append', default=[])
    create_cmd.add_argument(
        '--example',
        action='append',
        default=[],
        help='A library item read as an example of the kind of post for this blog only',
    )
    create_cmd.add_argument(
        '--messaging',
        action='append',
        default=[],
        help='A library item read as the product’s approved messaging for this blog only',
    )
    create_cmd.add_argument('--mode', choices=MODES, default='write')
    create_cmd.add_argument('--manuscript')
    create_cmd.add_argument('--outline-text')
    create_cmd.add_argument(
        '--point',
        action='store_true',
        help='With --mode from-files: start at the outline from the title, goal and audience',
    )
    commands.add_parser('list')
    for name in ('status', 'submit', 'approve', 'changes', 'handoff', 'choose'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--id', required=True)
        if name != 'status':
            cmd.add_argument('--expected', required=True)
        if name == 'choose':
            cmd.add_argument('--angle', required=True)
            cmd.add_argument('--note', default='')
        if name == 'submit':
            cmd.add_argument('--stage', choices=tuple(STAGES), required=True)
            cmd.add_argument('--file', required=True)
            cmd.add_argument('--notes', default='')
            cmd.add_argument(
                '--gap',
                action='append',
                default=[],
                help='With a draft or handoff: something the author must supply before publishing',
            )
        if name == 'changes':
            cmd.add_argument('--request', required=True)
            cmd.add_argument('--stage', choices=tuple(STAGES))


def research_from_words(words, sites):
    """--research-from documents,sites,web and --site: the shared shape. Sites are the
    shared list unless sites are given for this blog."""
    import studios_config

    named = [word.strip() for word in words.split(',') if word.strip()]
    if not named or set(named) - {'documents', 'sites', 'web'}:
        raise ValueError('Give --research-from as documents, sites or web, comma separated.')
    if sites and 'sites' not in named:
        named.append('sites')
    listed = []
    if 'sites' in named:
        listed = list(sites) or research_sites.defaults(studios_config.read()[0])
        if not listed:
            raise ValueError(research_sites.NO_SITES)
    return {'documents': 'documents' in named, 'sites': listed, 'web': 'web' in named}


def command(root, args):
    if args.action == 'create':
        raise ValueError(
            'New Blog Studio work starts on the desk. Use studio.py --root PATH desk create --input FILE (or --input - for JSON on stdin). Saved run status, submit and decisions remain available.'
        )
    if args.action == 'list':
        return catalog(root)
    if args.action == 'status':
        return engine(root).describe(args.id)
    with studio.locked(root):
        if args.action == 'create':
            data = {
                k: v
                for k, v in vars(args).items()
                if k
                not in (
                    'root',
                    'group',
                    'action',
                    'source',
                    'example',
                    'messaging',
                    'compact',
                    'research_from',
                    'site',
                )
                and v is not None
            }
            data['sources'] = args.source
            if args.research_from is not None or args.site:
                data['research_from'] = research_from_words(
                    args.research_from or 'sites', args.site
                )
            library = [{'id': ident, 'role': 'example'} for ident in args.example]
            library += [{'id': ident, 'role': 'messaging'} for ident in args.messaging]
            if library:
                data['library'] = library
            return create(root, data)
        if args.action == 'submit':
            if args.gap and args.stage not in NOTED:
                # Only a draft and a handoff keep gaps; elsewhere one would be dropped unsaid.
                raise ValueError(
                    'A gap goes with a draft or a handoff, where it is listed under Needs you '
                    'before publishing. Put it in --notes for this step. Nothing was submitted.'
                )
            return submit(
                root,
                args.id,
                args.stage,
                {
                    'content': Path(args.file).read_text(),
                    'notes': args.notes,
                    **({'gaps': args.gap} if args.gap else {}),
                },
                args.expected,
            )
        if args.action == 'choose':
            found = guard(root, args.id, args.expected)
            directory, record, run = load(root, args.id)
            if run.get('mode') != 'from-files':
                raise ValueError('Only a blog written from files chooses an angle.')
            choose_angle(root, directory, record, run, found, args.angle + '\n' + (args.note or ''))
            return survey(root, args.id)
        return decide(
            root,
            args.id,
            args.expected,
            args.action,
            getattr(args, 'request', ''),
            target=getattr(args, 'stage', None),
        )
