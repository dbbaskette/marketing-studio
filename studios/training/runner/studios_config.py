"""Training Studio settings facade over the shared storage implementation."""
import sys
import hub
from workspace import WorkspaceError
from studio_core.studios_config import for_product


def _address(value):
    if hub.ADDRESS_WITH_SECRET.match(value.strip()):
        raise WorkspaceError('That address carries a password or token. Give the address without it; git signs in with your own credentials.')


sys.modules[__name__] = for_product(__name__, 'Training Studio', WorkspaceError, _address)
