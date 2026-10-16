"""Marketing Studio facade over shared HTTP protections."""
import sys
from pathlib import Path
from studio_core.server import for_product
from . import computer
from .errors import WorkspaceError

sys.modules[__name__] = for_product(__name__, 'Marketing Studio',
    'X-Marketing-Studio-Token', Path(__file__).resolve().parent / 'web',
    {'/': ('index.html', 'text/html; charset=utf-8'), '/index.html': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'), '/home.css': ('home.css', 'text/css; charset=utf-8')}, computer, WorkspaceError)
