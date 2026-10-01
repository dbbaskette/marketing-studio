# Article writing module

Use to produce a complete blog article from a topic, brief, or outline.

**Input:** topic/brief, audience, voice samples or instructions, source material,
search intent if relevant, target format/length, and authorized output location.
**Output:** the requested article with supported factual claims, useful structure,
and a short account of unresolved source or asset needs when any remain.

Read the [original blog-write skill](../upstream/claude-blog/skills/blog-write/SOURCE.md)
for its article workflow. Its shared `skills/blog/...` references live under
`references/upstream/claude-blog/` relative to the package root. Select only
what the article needs:

- [Template selection](../upstream/claude-blog/skills/blog/references/content-templates.md) and its linked template when article structure needs guidance.
- [Research quality](../upstream/claude-blog/skills/blog/references/research-quality.md) or [synthesis](../upstream/claude-blog/skills/blog/references/synthesis-contract.md) for substantial research synthesis.
- [Content rules](../upstream/claude-blog/skills/blog/references/content-rules.md) for structure and readability.
- [Platform formats](../upstream/claude-blog/skills/blog/references/platform-guides.md) for a specified publishing format.
- [Internal linking](../upstream/claude-blog/skills/blog/references/internal-linking.md) when actual site content is available.
- [Visual media](../upstream/claude-blog/skills/blog/references/visual-media.md) when visuals are requested or serve the explanation.

Draft with the host's available tools. Preserve the user's voice and scope;
research depth, word count, images, videos, charts, and FAQs depend on the
material. Do not fill statistics or media quotas, copy example claims, invent
experience, or force a sales CTA into an educational article. Use verified real
links; keep unresolved linking suggestions outside finished prose. Reuse an
approved outline rather than requiring another approval.

The upstream delivery reference depends on omitted rendering scripts, image
providers, and reviewer agents. See [package notes](../package-notes.md) only
when that full runtime is requested. Deliver the requested format with relevant
verification; do not claim upstream preflight or scoring scripts ran.
For polishing the resulting draft, load [copy-editing](copy-editing.md) when needed.
