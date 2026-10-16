# Reuse a native Google Docs template

**Input:** user-selected template/reference, current blog and adaptation scope.
**Output:** native copied Doc with verified structure/content, or an explicit
capability gap. Follow [adapter](../google/adapter.md), [privacy](../privacy.md)
and the installed Google Docs template-preservation route.

Clarify whether the linked Doc is a template/reference or merely a content source
when this changes the result. Before construction, enumerate the complete nested
tab tree and relevant heading/table styles, lists, links, chips, images, controls,
headers/footers and semantic field roles. A tab deep link does not authorize
collapsing the template. Inventory both form to preserve and example facts to
replace; prior-project claims, dates, owners and approvals are not blog facts.

Make a native copy in the requested folder. Check inherited audience and copy
permissions; don't assume an editing copy is private or shares the source's exact
access. Verify the copy preserves the full tab tree before filling it. Native
copy unavailable with meaningful native structure: report that limitation and
offer an explicitly approved different format; never flatten into a fresh Doc
or reconstruct through Word while claiming faithful template reuse.

Use trusted read on the copied destination before its first write. Adapt only
requested content/fields inside retained native structures. Respect user-directed
extensions and removals. Retain untouched tabs, styles, controls and instructions;
replace stale example facts in every retained tab where the new task requires
adaptation. If facts are missing, use labeled placeholders rather than inventions.
Use supported native elements per the active Docs skill; preserve unsupported
controls without claiming to edit them. Guard writes with the observed revision
and reread after index changes. An unsafe exact mutation stays unavailable.

Read back the whole affected structure, selected content, heading/table styles,
links, native elements, tab order/nesting and folder/access. Inspect a rendered
export too when layout matters and the tools support it. Explain any unverified
fidelity. Retain local text and pending checkpoint on failure. If this is a
writing handoff, finish [handoff](blog-google-handoff.md) confirmation only after
both text and structural readback succeed.

Optional [receipt](../google/checkpoints.md): operation `template`, copied document
ID, status; requested/observed objects contain `template_id`, `tab_signature`
(SHA-256 of the ordered title/parent/order topology, not copied IDs), and
`structure_verified` boolean. Expected topology incorporates only user-authorized
changes. Matching topology does not prove styles/controls survived: verify those
through native readback before setting structure_verified. Do not store the raw
provider response or any credentials in shared memory.
