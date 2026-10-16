# Select evidence without losing provenance

Begin with the article's selected reference IDs, roles, revisions and access
status, plus existing findings. Voice samples, inspiration and author background
are not factual references unless explicitly selected for that purpose. Locate
candidate passages with local search or host retrieval, then read enough adjacent
text to establish population, dates, method, conditions and qualifiers. Broaden
the read when context is ambiguous or sources disagree. Search snippets and
summaries help navigation; neither substitutes for the actual passage.

`article show` returns current content paths and the attached revision. If
`changed_since_attach` is true, that path is newer than the baseline. Read the
recorded revision from `sources/<id>/revisions/<revision>/content.md` when available;
use current content only when its revision matches the chosen evidence. Explicit
adoption uses source attachment; it is not implied by reopening. If the pinned
passage is missing or unreadable, report the gap. Never silently cite a new version
as the old one. Conflicting shared versions require an explicit selection.

For each evaluated claim retain the exact draft quote/location, verdict
(supported, unsupported or contradicted), explanation, and evidence: source ID,
revision, original URL/file, exact excerpt and page/heading/line locator. Record
which revision was actually read. Unsupported findings identify the inspected
sources/coverage and the gap; do not invent a supporting excerpt. Keep conflicting
passages with their separate provenance rather than choosing the favorable one.

Store these details in the review JSON alongside `findings` and a `coverage`
object describing checked passages, selected references, exclusions and access
limits. Supported claims also need traceable evidence, even if stored in a
separate `claims` list. The helper preserves these fields; it does not validate
claim truth or enforce their schema. A short author-facing summary points back
to this record. No readable factual references means unavailable, not clean.
