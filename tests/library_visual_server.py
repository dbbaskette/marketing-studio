"""A disposable Marketing Studio home for tests/library_visual.cjs: synthetic settings, a
synthetic Document Library and one synthetic Blog Studio workspace, all in a temporary
folder. Prints the page's private address and serves until it is stopped.

No studio is started, no assistant or provider is reached and nothing on this computer is
read or changed: HOME, the studios config, the library and every studio's data folder are
named for this process only, and BROWSER is false so nothing opens a browser.
"""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]


def main():
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp).resolve()
        os.environ.update({
            'HOME': str(base / 'home'), 'STUDIOS_CONFIG': str(base / 'studios-config.json'),
            'STUDIOS_LIBRARY': str(base / 'library'), 'MARKETING_STUDIO_DATA': str(base / 'data'),
            'BLOG_STUDIO_DATA': str(base / 'blog-data'),
            'PRESENTATION_STUDIO_DATA': str(base / 'none'), 'TRAINING_STUDIO_DATA': str(base / 'none'),
            'INFOGRAPHIC_STUDIO_DATA': str(base / 'none'), 'BROWSER': 'false'})
        (base / 'home').mkdir()
        from test_library_adopt import Workspace
        import marketing_studio  # noqa: F401  puts the core on the import path
        from marketing_studio import server as home_server
        from marketing_studio.launcher import Launcher
        from marketing_studio.page import Home
        from studio_core import document_library, preferences, studios_config

        studios_config.update({'local': {'root': str(base / 'work')}})
        preferences.finish(studios_config, lambda _: None)
        library = document_library.opened(create=True)
        # Rows written in one second sort by title, newest first: this one leads the page.
        long = ('Zephyr, a synthetic field guide with a deliberately long title that has to '
                'wrap on a phone without pushing the page sideways')
        # The newest first on the page: the long title, a deck and a file that needs text.
        for number in range(1, 29):
            library.add_upload(f'note-{number}.txt', f'Synthetic note {number}.\n'.encode(),
                               title=f'Synthetic note {number}')
        library.retain('presentation:launch-0a0a0a0a0a0a', 'presentation', 'presentation',
                       'Launch deck', '# Launch\n\n## Slide 1\n\nOne.\n',
                       pdf={'state': 'needs-export', 'reason': 'Synthetic: no PDF exporter here.'})
        library.add_upload('scan.pdf', b'%PDF-1.4 synthetic, no text')
        library.add_upload('field-guide.md', b'# Field guide\n\nSynthetic words.\n', title=long)
        blogs = Workspace(base / 'writing')
        blogs.source('gateway-guide-1a2b3c4e', 'Gateway guide', '# Gateway guide\n\nRoutes.\n',
                     purposes=('reference', 'inspiration'), author='Avery',
                     library={'origin_kind': 'written-here', 'article': 'gateway-guide-1a2b3c4d'})
        blogs.source('pricing-notes-5e6f7a8b', 'Pricing notes, kept as an upload with a long name',
                     'Plans start at two seats.\n', original=b'Plans start at two seats.\n',
                     filename='pricing.md', library={'origin_kind': 'upload'})
        blogs.source('scan-7e8f9a0b', 'A scanned page', status='pending',
                     original=b'%PDF-1.4 synthetic', filename='scan.pdf',
                     library={'origin_kind': 'upload'})
        (base / 'blog-data').mkdir()
        (base / 'blog-data' / 'page.json').write_text(json.dumps({'workspace': str(blogs.root)}))
        launcher = Launcher()
        desk = home_server.Desk(page=lambda port: Home(port, launcher))
        desk.start()
        print(desk.url, flush=True)    # private test process only
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        try:
            stop.wait()
        finally:
            desk.stop()
            launcher.close()


if __name__ == '__main__':
    main()
