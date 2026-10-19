from pathlib import Path
from studio_core.runtime import ensure_python

ensure_python(Path(__file__).resolve().parents[1], module='marketing_studio')

from .cli import main

raise SystemExit(main())
