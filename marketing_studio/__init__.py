"""Shared setup and a local launch pad for the independent studios."""

import sys
from pathlib import Path
_CORE = Path(__file__).resolve().parents[1] / 'core'
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
