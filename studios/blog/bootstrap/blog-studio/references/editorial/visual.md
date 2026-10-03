# Visual companion

Choose the smallest visual that explains the actual argument: portable Mermaid
diagram, Markdown comparison table, or a screenshot capture plan. Ground labels,
architecture and metrics in selected manuscript/source passages. Identify
illustrative examples explicitly. Include placement, caption and alt text.

Save `editorial visual --id <id> --file <json>`:
`{"type":"diagram","content":"flowchart LR\nGateway --> Service","caption":"Request path","alt":"Gateway forwards to service","placement":"After the request-path explanation","illustrative":true,"manuscript_quotes":["exact supporting manuscript sentence"]}`.
Types also include table and screenshot-plan. Content is saved as portable `derived/visual-companion.md`, with its structured
record in `derived/visual-companion.json`, with manuscript/source provenance and staleness.
Read only the chosen portable companion when handing off its Markdown/Mermaid output.

Discover real render/image capabilities before promising finished media. Text
plans are not finished screenshots. For rendered output, visually inspect it and
record its saved location. A media service that receives private writing is a new
external destination; use local rendering or get explicit authorization first.
