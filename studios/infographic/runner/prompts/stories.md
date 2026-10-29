Propose one faithful explanation for directed work, or up to three meaningfully
different explanations for suggested/hybrid work. Fewer useful options are better
than duplicate layouts. Use only captured fact IDs. Keep exact locked phrases,
required IDs, exclusions and qualifications; hybrid proposals retain all must-show
ideas. Record omissions explicitly and ask for prioritization when content cannot
fit. Use one takeaway, one to five primary blocks and at most 250 visible words.
The omissions array contains only IDs from brief.must_show that this story leaves
out. It is [] when brief.must_show is empty. Optional details left out of the
source belong as readable notes in qualifications, never as invented omissions
or required_ids. Block required_ids likewise name only brief.must_show IDs.
Design an infographic, not a page of paragraphs. Prefer two or three concise blocks
and about 100–160 total visible words, including all node labels and captions. Leave room
for source notes, qualifications, labels and explanatory artwork. Do not request
an illustration for every block. Process step numbers are added by the compositor;
do not add extra numbering to titles or prose unless it is required source content.
Each proposal has id, headline, takeaway, rationale, qualifications, omissions and
blocks. Each block has id, kind (comparison/process/timeline/numbers/parts/concept),
title, text, fact_ids, required_ids, quantitative (boolean), illustration (boolean),
illustration_role and visual. A qualitative block MUST have visual={nodes,links}.
Each node has id, label (at most 8 words), caption (at most 16 words; empty is fine),
icon (layers/server/cloud/database/shield/lock/document/code/users/network/cycle/check/chart),
and fact_ids. Represent every block fact in a node or link. Every link has from, to,
label (at most 6 words; empty is fine), and fact_ids supporting that exact relationship.
Use 1–4 nodes and 0–6 links. No invented causal or chronological arrows. Use paired
nodes for comparisons, supplied ordered stages for processes, components for parts,
and relationships supported by the source for concepts. Block text is a short summary
(prefer at most 20 words), not a paragraph repeating the diagram. Numeric charts can
use visual=null. The native compositor draws editable pictograms, diagrams and exact
labels without an image provider. Request illustration=true only when a specific
pictorial illustration adds information beyond the native diagram, at most one
focal illustration per page; never merely
because a qualitative block needs graphics. Set quantitative=false for comparisons of ideas, capabilities,
descriptions or components; these do not require numeric measurements. Use parts
with quantitative=false to explain components rather than proportions. Use
quantitative=true for scaled charts, measured part-to-whole visuals and number
callouts. The numbers kind always requires actual numeric source values. Do not
invent numbers or turn descriptive values into chart data to satisfy a layout.
Describe the explanatory subject and relationships of an illustration when useful;
never add decorative artwork merely to fill a quota. Numeric comparisons require
compatible supplied units/periods/denominators/conditions; do not invent metrics,
chronology or causality. Required content cannot disappear to make a layout fit.
