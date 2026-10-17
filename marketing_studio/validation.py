"""Marketing Studio's error context for the shared settings contract."""
from studio_core import preferences
from .errors import WorkspaceError

EFFORTS = preferences.EFFORTS
FIELDS = preferences.FIELDS


def _call(action, *args):
    try:
        return action(*args)
    except ValueError as failure:
        raise WorkspaceError(str(failure)) from failure


def check(changes, current):
    return _call(preferences.check, changes, current)


def repository(value):
    return _call(preferences.repository, value)


def branch(value):
    return _call(preferences.branch, value)
