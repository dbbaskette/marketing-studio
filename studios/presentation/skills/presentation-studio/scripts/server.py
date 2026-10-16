"""Presentation Studio facade over shared HTTP protections."""
import sys
from pathlib import Path
from studio_core.server import for_product
import computer
from workspace import WorkspaceError

sys.modules[__name__] = for_product(__name__, 'Presentation Studio',
    'X-Presentation-Studio-Token', Path(__file__).resolve().parent / 'desk',
    {'/': ('index.html', 'text/html; charset=utf-8'), '/index.html': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/markdown.js': ('markdown.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'), '/deck.css': ('deck.css', 'text/css; charset=utf-8')}, computer, WorkspaceError)
