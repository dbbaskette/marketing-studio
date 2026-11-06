"""Saved scheduling policy for readable output before optional deck work.

This only orders existing steps. Their input checks, approvals, spending limits,
and the single material worker remain owned by the existing pipeline and engine.
"""
from runner import drafts, outline_first

PIN = {'schema': 1, 'order': 'readable-first'}


def enabled(record):
    value = record.get('material_flow')
    return (isinstance(value, dict) and type(value.get('schema')) is int
            and value == PIN and drafts.on_desk(record) and outline_first.enabled(record))


def order(listed, session, record):
    """Prioritize each level's readable output, preserving order within each group.

    Earlier plans still precede later plans, and selected briefs precede practice.
    Explicit updates retain the existing scoped update chain and hold behavior.
    Records without this pin retain their original order.
    """
    if not enabled(record) or drafts.updates(record):
        return listed
    levels = session['levels'] or [None]

    def priority(step):
        import workspace
        if step.stage in ('intake', 'research-plan', 'research'):
            return (0, 0)
        if step.stage == 'package':
            return (4, 0)
        level = workspace.split(step.artifact)[1] if step.artifact else None
        at = levels.index(level) if level in levels else len(levels)
        group = (1 if step.stage in ('blueprint', 'document', 'brief')
                 else 2 if step.stage in ('scenario', 'yoodli') else 3)
        return (group, at)

    return tuple(sorted(listed, key=priority))
