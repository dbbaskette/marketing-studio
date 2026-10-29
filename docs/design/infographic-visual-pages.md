# Infographic Studio: visual explanations

The output is an infographic, with a visible explanation that carries the story:
process stages, component maps, descriptive comparisons, timelines or measured
charts and number callouts. Paragraph blocks alone do not satisfy this goal.

New planning responses describe short, evidence-linked visual nodes. The compositor
draws the diagrams and pictograms as editable SVG, retains required wording and
qualifications, and checks real fonts, geometry and reading size. Arrows represent
only supplied process/chronology or explicitly supported relationships. Qualitative
information never becomes a scaled chart. Pictograms are illustrative, not logos
or product screenshots. Existing saved scenes stay intact until an explicit rebuild.

Generated imagery supplements the diagram when the selected story requests it.
The image worker is instructed to make exactly one generation request per intent;
further revisions are explicit. A single focal illustration is generated for its
own frame, rather than a mostly blank page. Exact wording and numeric marks remain
compositor-owned.

Codex output collection accepts either the owned job output directory or the
native generated-images directory for the exact UUID from the worker's recorded
thread.started event. It never adopts paths from assistant prose or scans other
threads. Completed saved output can be recovered locally with a revision/basis
check, without resubmission. Cancelled requests remain cancelled; incomplete,
stale, linked or invalid output cannot replace current work.

Older prose plans with long labels expose Make this story visual. One explicit
assistant revision reuses the captured facts and proposes short visual nodes;
the user reviews and chooses it. Short older plans can rebuild diagrams locally.

Verification uses synthetic sources, injected providers and the installed renderer.
Review actual rendered process, comparison, component, concept and numeric pages,
including dense/mixed content, three presets, image recovery and phone workflow.
