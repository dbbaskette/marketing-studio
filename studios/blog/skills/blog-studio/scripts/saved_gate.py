"""What may change a blog saved by the earlier step-by-step flow, in one place.

A saved-flow blog is a blog with a saved run that the manuscript editor's check did not make
and that is not on the writing desk. The earlier flow continues none of them, so every
changing request passes this gate first: the page's dispatch (management.dispatch and the
import jobs it starts), the command line's subcommands (studio.main and article_command),
the manuscript editor's entry point (manuscript_editor.dispatch) and the team workspace's
(team_workspace.action). A request that names a saved-flow blog anywhere in its body (or
names a tool job of one) is refused unless its action is allowed for that blog's state.
An action with no decision here is refused for a saved-flow blog.

What a decision allows:
- READS: allowed. It only reads the named blog, makes new work from it, or is not about a
  blog at all; it never writes the blog's folder.
- ANY: allowed for every saved-flow blog (the explicit migration, Delete and its Restore,
  a tool job's own control, which writes only the runner's records).
- FINISHED: allowed for a finished saved-flow blog only (what its Done card offered: mark
  as published, a Google Doc, the finished Open on the desk, recording or publishing it in
  the team repository, Polish or edit through the manuscript editor, repurposing).
- TAKE: Take or Take over, only where the blog would open on the desk once taken.
- RUNNING: Pause or Stop, only for a step this process is running now.
- WAITING: discarding a ready tool task's result, only for an unfinished saved-flow blog
  that waits on that ready task (its result can be neither saved to it nor cancelled).
- NEVER: refused for every saved-flow blog (Hand over among them).

The editor's own runs, a registered manuscript with no run, and desk blogs are not
saved-flow blogs: nothing here applies to them.
"""

import json
import os
import re

import studio

READS, ANY, FINISHED, TAKE, RUNNING, NEVER = 'reads', 'any', 'finished', 'take', 'running', 'never'
WAITING = 'waiting-task'

# What every page action may do to a saved-flow blog. Tool actions are keyed
# 'tool-action:<action>'.
PAGE = {
    # Not about a blog's own folder: sources, the library, settings, Google intake, reports.
    **dict.fromkeys(
        (
            'analyze',
            'brand-configure',
            'brand-install',
            'curate',
            'desk-create',
            'document-library',
            'document-library-document',
            'document-library-filters',
            'document-library-matching',
            'document-library-take',
            'files-intake',
            'geo-report-again',
            'geo-report-desk',
            'geo-report-google-plan',
            'geo-report-google-send',
            'geo-report-start',
            'google-copy',
            'google-preview',
            'google-start',
            'import-stop',
            'intake-draft',
            'library-add',
            'library-add-author',
            'library-add-preview',
            'library-add-samples',
            'library-author-different',
            'library-author-same',
            'library-import',
            'library-preview',
            'library-selection',
            'library-voices',
            'memory',
            'published-find-text',
            'published-find-text-stop',
            'published-preview',
            'refresh',
            'research-site',
            'research-sources',
            'resume',
            'retry-sync',
            'run-settings',
            'source-role',
            'team-join',
            'team-share-mode',
            'team-sync',
            'upload',
            'voice-links-import',
            'voice-links-preview',
            'tool-action:guide-discard',
            'tool-action:profile-retire',
            'tool-action:profile-save',
            'tool-action:source-purpose',
            'tool-action:style-retire',
            'tool-action:style-save',
        ),
        READS,
    ),
    # Any saved-flow blog: the explicit migration, Delete and Restore, a tool job's control.
    **dict.fromkeys(
        ('desk-migrate', 'blog-delete', 'blog-restore', 'tool-action:job-control'), ANY
    ),
    # Discarding a ready task's result that was never saved: an unfinished saved blog that
    # waits on it can neither apply nor cancel it, so this is its one way out. Only for that
    # blog (waits_on_ready_task); it writes only the task's own record.
    'tool-action:job-discard': WAITING,
    # A finished one: what its Done card offered.
    **dict.fromkeys(
        (
            'schedule',
            'google-open',
            'desk-open',
            'team-publish',
            'editor-apply-proposal',
            'editor-apply-selected',
            'editor-changes',
            'editor-check',
            'editor-google-plan',
            'editor-google-send',
            'editor-proposals',
            'editor-save',
            'tool-action:google-accept',
            'tool-action:google-compare',
            'tool-action:job-apply',
            'tool-action:job-create',
        ),
        FINISHED,
    ),
    'team-take': TAKE,
    'team-takeover': TAKE,
    'run-pause': RUNNING,
    'run-stop': RUNNING,
    # Never: continuing the earlier flow, Hand over, desk work and the other blog tools.
    **dict.fromkeys(
        (
            'team-handover',
            'run-approve',
            'run-changes',
            'run-resume',
            'run-retry',
            'desk-share',
            'desk-repurpose',
            *(
                'desk-' + name
                for name in (
                    'angles',
                    'apply',
                    'brief',
                    'draft',
                    'finish',
                    'first-pass',
                    'geo-option',
                    'google-check',
                    'google-compare',
                    'google-open',
                    'google-plan',
                    'google-send',
                    'google-take',
                    'library-update',
                    'meta',
                    'note',
                    'outline-save',
                    'restore',
                    'retry',
                    'review',
                    'revise',
                    'save',
                    'selection',
                    'skip',
                    'sources',
                    'stop',
                    'unremove',
                    'unskip',
                )
            ),
            'tool-action:interview-answer',
            'tool-action:interview-start',
            'tool-action:restore',
            'tool-action:variant-save',
            'tool-action:voice-apply',
        ),
        NEVER,
    ),
}

# What every command-line subcommand may do: 'group action', or 'group' for one without
# actions.
COMMANDS = {
    **dict.fromkeys(
        (
            'run list',
            'run status',
            'desk create',
            'desk show',
            'desk migration-preview',
            'saved-work',
            'init',
            'list',
            'manage',
            'home',
            'context',
            'readiness',
            'resume',
            'passages',
            'check',
            'cache',
            'select',
            'status',
            'route',
            'changes',
            'prepublish',
            'plan',
            'research status',
            'editorial board',
            'editorial inbox',
            'editorial assets',
            'team join',
            'team status',
            'team sync',
            'article create',
            'article show',
            'google start',
            'google capabilities',
            'google source',
            'google status',
            'google compare',
            *(
                'library ' + name
                for name in (
                    'read',
                    'locate',
                    'setup',
                    'collections',
                    'preview',
                    'import',
                    'voice-links',
                    'find',
                    'curator',
                    'analyze',
                    'curate',
                    'lesson',
                    'promote',
                )
            ),
            *('defaults ' + name for name in ('show', 'set', 'reset')),
            *('profile ' + name for name in ('create', 'save', 'show', 'retire')),
            *('style ' + name for name in ('create', 'save', 'show', 'retire')),
            *('source ' + name for name in ('add', 'show', 'update')),
        ),
        READS,
    ),
    'desk migrate': ANY,
    # A finished one keeps what it had: the editorial decision, a Google Doc, recording it
    # in the team repository, and the article commands the manuscript editor uses.
    **dict.fromkeys(
        (
            'editorial schedule',
            'team publish',
            'google prepare',
            'google confirm',
            'google pull',
            'google accept',
            'google receipt',
            *(
                'article ' + name
                for name in (
                    'rename',
                    'research-policy',
                    'author',
                    'remember',
                    'forget',
                    'detach-context',
                    'attach',
                    'save',
                    'restore',
                    'progress',
                    'context',
                    'guidance',
                    'note',
                    'voice',
                    'review',
                    'derive',
                )
            ),
        ),
        FINISHED,
    ),
    'team take': TAKE,
    'team takeover': TAKE,
    **dict.fromkeys(
        (
            'run create',
            'team handover',
            'team migrate',
            'research import',
            'research plan',
            'research record',
            'editorial evidence',
            'editorial package',
            'editorial visual',
            *(
                'desk ' + name
                for name in ('save', 'context', 'submit', 'handoff', 'scope', 'outline-save')
            ),
        ),
        NEVER,
    ),
}

# The sentences a refusal says: each names the two ways on from a saved blog.
SAVED_FLOW = (
    'The earlier step-by-step flow no longer continues this blog: open it on the desk, or '
    'start new work from it.'
)
NOT_RUNNING = 'No step of this blog is running here to pause or stop. ' + SAVED_FLOW
NOTHING_TO_TAKE = (
    'There is nothing to take this blog for: it cannot open on the desk. Start new work '
    'from it instead.'
)

_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,79}')
_JOB = re.compile(r'[0-9a-f]{32}')
_MOST = 256  # Names one request is read for: far more than any action sends.


class Refused(ValueError):
    """A changing request refused for a saved-flow blog; nothing was changed."""


def state(root, ident):
    """'finished' or 'unfinished' for a saved-flow blog ('unfinished' too when its run record
    cannot be read: which flow made it is then unknown, so nothing continues it), or None for
    anything else (no such blog, a desk blog, a registered manuscript with no run, or the
    manuscript editor's own run). Only reads small records."""
    import blog_runner
    import desk_migration

    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        return None
    try:
        directory = studio.inside(root, 'articles', ident)
        if directory.is_symlink() or not directory.is_dir():
            return None
        if not (directory / 'session.json').exists() and not os.path.lexists(
            directory / blog_runner.STATE
        ):
            return None
        if os.path.lexists(directory / 'desk' / 'draft.json'):
            return None  # On the desk: desk work.
        if not os.path.lexists(directory / blog_runner.STATE):
            return None  # A registered manuscript, or desk work with no run.
    except (OSError, ValueError):
        return None
    run = desk_migration.saved_run(directory)
    if not isinstance(run, dict):
        return 'unfinished'
    if blog_runner.continues(run):
        return None  # The manuscript editor's own run.
    stages = run.get('stages') if isinstance(run.get('stages'), dict) else {}
    pipeline = run.get('pipeline') if isinstance(run.get('pipeline'), list) else []
    finished = bool(pipeline) and all(
        isinstance(stages.get(name), dict) and stages[name].get('status') == 'approved'
        for name in pipeline
    )
    return 'finished' if finished else 'unfinished'


def _job_article(root, job):
    """The blog a tool job works on, from its record under .blog-runs/tools; None if unknown."""
    try:
        path = studio.inside(root, '.blog-runs', 'tools', job + '.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            return None
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None
    article = (record.get('metadata') or {}).get('article') if isinstance(record, dict) else None
    return article if isinstance(article, str) else None


def named(root, data):
    """Every blog a request body may name: each string shaped like an ID, anywhere in it,
    and the blog of each tool job it names."""
    found, jobs = set(), set()

    def walk(value, depth):
        if len(found) + len(jobs) > _MOST or depth > 8:
            return
        if isinstance(value, str):
            if len(value) <= 80 and _ID.fullmatch(value):
                found.add(value)
                if _JOB.fullmatch(value):
                    jobs.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item, depth + 1)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, depth + 1)

    walk(data, 0)
    for job in jobs:
        article = _job_article(root, job)
        if article:
            found.add(article)
    return found


def _would_open(root, ident):
    """Whether this blog opens on the desk once taken: its outcome opens on the desk, it
    finished, or it waits only for Take."""
    import desk_migration

    said = desk_migration.classify(root, ident)
    if said['outcome'] in ('migrates', 'finished'):
        return True
    if said['outcome'] == 'wait':
        return desk_migration._clears(root, ident, said['reason'])[0] == 'take'
    return False


def refusal(root, decision, ident, found):
    """The sentence that refuses this decision for this saved-flow blog, or None."""
    if decision in (READS, ANY):
        return None
    if decision == FINISHED:
        return None if found == 'finished' else SAVED_FLOW
    if decision == TAKE:
        return None if _would_open(root, ident) else NOTHING_TO_TAKE
    if decision == RUNNING:
        import blog_runner

        return None if blog_runner.engine(root).current == ident else NOT_RUNNING
    if decision == WAITING:
        return None if found == 'unfinished' and waits_on_ready_task(root, ident) else SAVED_FLOW
    return SAVED_FLOW


def waits_on_ready_task(root, ident, job=None):
    """Whether this saved blog waits on a ready tool task (`job`, when named): its saved
    record's outcome is waiting, and what clears it is that task, ready for the person."""
    import desk_migration

    try:
        said = desk_migration.classify(root, ident)
        if said['outcome'] != 'wait':
            return False
        clear, task = desk_migration._clears(root, ident, said['reason'])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return (
        clear == 'job'
        and isinstance(task, dict)
        and task.get('status') == 'ready'
        and (job is None or task.get('id') == job)
    )


def check(root, decision, data):
    """Refuse (Refused, a ValueError) when `data` names a saved-flow blog `decision` does not
    allow. Reads only; nothing is written either way."""
    for ident in sorted(named(root, data)):
        found = state(root, ident)
        if found is None:
            continue
        said = refusal(root, decision, ident, found)
        if said:
            raise Refused(said)


def page_key(route, data):
    if route == 'tool-action' and isinstance(data, dict):
        return 'tool-action:' + str(data.get('action'))
    return route


def page(root, route, data):
    """The gate for one page action (management.dispatch, import jobs)."""
    check(root, PAGE.get(page_key(route, data), NEVER), data)


def command_key(args):
    action = getattr(args, 'action', None)
    # The article commands are also called inside Blog Studio with only their own arguments.
    group = getattr(args, 'group', 'article')
    return group + (' ' + action if isinstance(action, str) else '')


def command(root, args):
    """The gate for one command-line subcommand."""
    check(root, COMMANDS.get(command_key(args), NEVER), vars(args))
