"""Marketing Studio settings facade over the shared storage implementation."""
import sys
from studio_core.studios_config import for_product
from .errors import WorkspaceError
from .validation import repository

sys.modules[__name__] = for_product(__name__, 'Marketing Studio', WorkspaceError,
                                    repository, strict_groups=True)
