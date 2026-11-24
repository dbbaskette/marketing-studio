"""Protected Marketing Studio Brands page with synthetic sources and no provider access.

Its brands folder holds two made-up brand packs: Sample Co, with a document template and a
rebranding profile, and Plain Co, with neither, so the templates, a rebrand refused, a
rebrand running (the stand-in waits STAND_IN_REBRAND_PAUSE seconds between its steps, 3 by
default) and a finished one can all be seen. Shared settings' Brand card is on the same page.
The stand-in Harness Brand reaches no Google service and no assistant."""
import json
import os
import signal
import sys
import threading
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_brands import BrandsCase, BRIEF, brand_pack, proposal, export_zip
from marketing_studio import brand_job, server, shared
from studio_core import preferences, server as protocol


def main():
    case = BrandsCase()
    case.setUp()
    desk = None
    try:
        preferences.finish(shared, lambda _: None)
        def assistant(agent, guidance, task, folder, model, effort, line, stop, seconds=0):
            # Deliberately long enough for real polling and editing; no command is run.
            for number in range(20):
                if stop.wait(.25):
                    raise brand_job.brand_skill.Stopped()
                line(f'Reviewing synthetic sources {number + 1}')
            return json.dumps(proposal())
        os.environ.setdefault('STAND_IN_REBRAND_PAUSE', '3')
        brand_pack(case.brands, 'sample', [BRIEF])
        brand_pack(case.brands, 'plain')
        (case.brands / 'sample' / 'rebrand').mkdir()
        (case.brands / 'sample' / 'rebrand' / 'manifest.json').write_text('{"schema": 1, "brand": "sample", "files": {}}')
        (case.root / 'export.zip').write_bytes(export_zip())
        (case.root / 'example-light.pptx').write_bytes(b'PK stand-in template')
        with mock.patch.object(brand_job, 'run_assistant', assistant):
            desk = server.Desk(page=lambda port: type(case.page)(port, case.launcher))
            desk.start()
            print(json.dumps({'url': desk.url, 'source': str(case.root / 'export.zip'), 'template': str(case.root / 'example-light.pptx')}), flush=True)
            signal.signal(signal.SIGTERM, protocol.interrupt)
            signal.signal(signal.SIGINT, protocol.interrupt)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    finally:
        if desk:
            desk.stop()
        case.tearDown()
        case.doCleanups()


if __name__ == '__main__':
    main()
