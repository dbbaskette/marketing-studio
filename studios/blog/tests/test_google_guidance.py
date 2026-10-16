"""The Google guidance must match the helpers it tells an agent to run. No Google access."""

import contextlib
import io
from pathlib import Path
import re
import shlex
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/blog-studio/scripts'))
import google_drive as gd
import google_roundtrip as rt
import google_suggestions as gs
import studio

REFERENCES = ROOT / 'skills/blog-studio/references'
GUIDANCE = (
    sorted((REFERENCES / 'google').glob('*.md'))
    + sorted((REFERENCES / 'modules').glob('blog-google-*.md'))
    + [REFERENCES / 'short-commands.md']
)
HELPER = re.compile(
    r'(google_drive\.py|google_roundtrip\.py|google_suggestions\.py|studio\.py)\s+(.*)$'
)


class GoogleGuidanceTests(unittest.TestCase):
    def test_every_helper_command_in_the_guidance_parses(self):
        parsers = {
            'google_drive.py': gd.build_parser(),
            'google_roundtrip.py': rt.build_parser(),
            'google_suggestions.py': gs.build_parser(),
            'studio.py': studio.parser(),
        }
        checked = 0
        for path in GUIDANCE:
            for line in path.read_text().split('\n'):
                command = HELPER.search(line.strip())
                if not command or '`' in line or not line.strip().startswith(('python3', '...')):
                    continue
                words = shlex.split(re.sub(r'<[^>]+>', 'PLACEHOLDER', command[2]))
                if command[1] == 'studio.py' and 'route' in words:
                    continue  # The router takes free text and belongs to another module.
                checked += 1
                with (
                    self.subTest(file=path.name, command=line.strip()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    try:
                        parsers[command[1]].parse_args(words)
                    except SystemExit:
                        self.fail('The helper does not accept this documented command.')
        self.assertGreaterEqual(checked, 20)

    def test_guidance_has_no_always_true_runtime_gates(self):
        # Guidance is only delivered to runtimes at or above the manifest minimum, so such gates say nothing.
        gate = re.compile(r'runtime\s+\**1\.\d|1\.\d+\+', re.IGNORECASE)
        for path in GUIDANCE:
            with self.subTest(file=path.name):
                self.assertIsNone(gate.search(path.read_text()))

    def test_guidance_agrees_that_raw_docs_json_stays_local(self):
        gcloud = (REFERENCES / 'google/gcloud.md').read_text()
        roundtrip = (REFERENCES / 'google/roundtrip.md').read_text()
        self.assertIn('never go to the Team', gcloud)
        self.assertIn('never sent to the Hub', roundtrip)
        self.assertNotIn('four snapshot files become article history', roundtrip)

    def test_proofread_rule_is_the_same_in_both_places(self):
        short = (REFERENCES / 'short-commands.md').read_text()
        suggestions = (REFERENCES / 'google/suggestions.md').read_text()
        self.assertIn('Leave `DRAFT.md` as it is', short)
        self.assertIn('leaves\n`DRAFT.md` unchanged', suggestions)
        self.assertNotIn(
            'Read the current draft and save with `article save ... --label\n  proofread`', short
        )


if __name__ == '__main__':
    unittest.main()
