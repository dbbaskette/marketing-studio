"""Infographic Studio's independently runnable pipeline."""
from pathlib import Path
import sys

# The suite-owned link is materialized to ordinary files when packaged. Importing
# this studio does not require Marketing Studio or another native studio.
_shared = str(Path(__file__).resolve().parent)
if _shared not in sys.path:
    sys.path.insert(0, _shared)
