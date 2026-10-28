"""Pure validation of Blog Studio's one supported unfinished-migration format.

No Studio operations, readers, repairs, settings, locks or workers belong here.
The domain reader and repository replay guard use the same immutable facts.
"""

import hashlib
import json
import re

WRITES = frozenset(
    {'desk/migration.json', 'desk/draft.json', 'desk/images.json', 'desk/start.json'}
)
STAGES = frozenset(
    {'angles', 'research-plan', 'research', 'claims-map', 'outline', 'draft', 'review', 'package'}
)
MODES = frozenset(
    {
        'existing',
        'first-draft',
        'outline-only',
        'from-outline',
        'interview',
        'discover',
        'from-files',
    }
)


def session_supported(record, ident=None):
    """Implicit schema 1 is the original saved format; future schemas refuse."""
    if (
        not isinstance(record, dict)
        or type(record.get('schema', 1)) is not int
        or record.get('schema', 1) != 1
    ):
        return False
    strings = (
        'id',
        'title',
        'mode',
        'stage',
        'stop_point',
        'research_policy',
        'next_step',
        'created_at',
    )
    if any(not isinstance(record.get(key), str) or not record[key].strip() for key in strings):
        return False
    if ident is not None and record['id'] != ident or record['mode'] not in MODES:
        return False
    if any(
        not isinstance(record.get(key), dict) for key in ('reviews', 'artifact_hashes', 'voice')
    ) or not isinstance(record.get('sources'), list):
        return False
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in record['artifact_hashes'].items()
    ):
        return False
    voice = record['voice']
    if voice.get('mode') not in ('tone', 'preserve', 'profile') or not isinstance(
        voice.get('tone', ''), str
    ):
        return False
    if voice['mode'] == 'profile' and (
        not isinstance(voice.get('profile_id'), str)
        or not voice['profile_id']
        or type(voice.get('revision')) is not int
        or voice['revision'] < 1
    ):
        return False
    for source in record['sources']:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get('source_id'), str)
            or not source['source_id']
            or type(source.get('revision')) is not int
            or source['revision'] < 1
            or not isinstance(source.get('purposes'), list)
            or any(not isinstance(purpose, str) or not purpose for purpose in source['purposes'])
        ):
            return False
    return True


def run_supported(run):
    """The saved run shapes understood by this fixed migration format."""
    if (
        not isinstance(run, dict)
        or type(run.get('schema')) is not int
        or run['schema'] not in (1, 2, 3)
        or run.get('approval') not in ('page', 'conversation')
    ):
        return False
    pipeline, stages = run.get('pipeline'), run.get('stages')
    if (
        not isinstance(pipeline, list)
        or not pipeline
        or len(pipeline) > len(STAGES)
        or any(not isinstance(stage, str) or stage not in STAGES for stage in pipeline)
        or len(set(pipeline)) != len(pipeline)
        or not isinstance(stages, dict)
        or set(stages) - STAGES
        or any(
            not isinstance(state, dict)
            or state.get('status') not in ('pending', 'draft', 'approved')
            for state in stages.values()
        )
    ):
        return False
    if run['schema'] == 2:
        policy = run.get('review_policy')
        if (
            not isinstance(policy, dict)
            or policy.get('schema') != 1
            or policy.get('level') not in ('balanced', 'automatic', 'step_by_step')
        ):
            return False
    if run['schema'] == 3 and (
        not isinstance(run.get('research_contract'), dict)
        or run['research_contract'].get('schema') != 2
    ):
        return False
    return True


def migration_supported(value, session_bytes, run_bytes, draft, ident):
    """Validate bounded records and historical equality without filesystem access."""
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1:
        return False
    session = value.get('session')
    if (
        value.get('product') != 'Blog Studio'
        or value.get('id') != ident
        or not session_supported(session, ident)
        or session.get('flow') != 'desk'
        or session.get('execution') not in ('conversation', 'runner')
        or session.get('conversation_scope') not in ('draft', 'outline', 'research', 'part')
        or value.get('material') not in ('draft', 'outline', 'original')
        or not isinstance(value.get('expected'), str)
        or re.fullmatch(r'bm1\.[A-Za-z0-9_-]{43}', value['expected']) is None
    ):
        return False
    files = value.get('files')
    if (
        not isinstance(files, list)
        or len(files) > len(WRITES)
        or any(not isinstance(name, str) or name not in WRITES for name in files)
        or len(set(files)) != len(files)
        or not {'desk/migration.json', 'desk/draft.json'} <= set(files)
    ):
        return False
    if (
        not isinstance(session_bytes, bytes)
        or not isinstance(run_bytes, bytes)
        or max(len(session_bytes), len(run_bytes)) > 1_000_000
    ):
        return False
    if hashlib.sha256(session_bytes).hexdigest() != value.get('session_basis') or hashlib.sha256(
        run_bytes
    ).hexdigest() != value.get('run_basis'):
        return False
    try:
        original = json.loads(session_bytes)
        run = json.loads(run_bytes)
    except (ValueError, UnicodeError):
        return False
    if not session_supported(original, ident) or not run_supported(run):
        return False
    if (
        value.get('historical_pipeline') != run['pipeline']
        or value.get('historical_stages') != run['stages']
    ):
        return False
    return (
        isinstance(draft, dict)
        and type(draft.get('schema')) is int
        and draft['schema'] == 1
        and draft.get('id') == ident
        and draft.get('unfinished_migration') is True
    )


def dependencies(value, draft):
    """Fixed output dependencies, called only after migration_supported succeeds."""
    return set(value['files']) | ({'desk/images.json'} if draft.get('images') else set())
