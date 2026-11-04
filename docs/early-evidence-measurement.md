# Early accepted evidence measurement

Issue #361 makes accepted investigator packets readable before the investigator
barrier. The preview uses existing helper-accepted facts and captures; it adds no
author or provider call. Each preview is bounded to 12 statements, six citations
per statement, 24 source descriptions and 12 limitations, with 1,200-character
text fields. Complete packets remain in the research case. Previews are not final
artifacts and cannot bypass the independent check.

## Scripted measurement

Run `scripts/ci/benchmark-evidence.py` with `STUDIO_TEST_RESEARCH_RUNTIME` set to a
disposable copy of the pinned Harness Research helper. The fixture has four
research areas, at most three concurrent investigators, one fast investigator,
three delayed by 0.6 seconds, four section authors, one final author and one
independent reviewer. Sources, statements and workers are synthetic.

On macOS with Python 3.14 and Harness Research 1.1.1, one measured run produced:

| Milestone | Seconds since start |
| --- | ---: |
| First accepted finding readable | 1.041 |
| First saved report section readable | 2.638 |
| Checked final report | 3.179 |

The call count remains 10: four investigators, four section authors, one final
author and one reviewer. The earlier implementation could not display findings
before the section stage. This is a scripted responsiveness measurement, not a
live-model speedup claim; provider latency and source volume will vary.

A separate real-helper test holds a slow investigator until another packet is
visible, fails it, then retries only that investigator. Successful peers remain
readable, and the retried packet has a new attempt number. Hash, request, generation
and attempt mismatches suppress restored previews. Retrying a stream removes its
old preview; stopping, pausing or source invalidation removes current evidence
from progress. The UI labels incomplete findings and superseded checked-report
history explicitly. It performs no source fetches or additional model work.
