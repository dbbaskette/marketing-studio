# Blog lifecycle reference module

Use when a parent skill needs lifecycle design, platform selection, research or
review criteria, or the broader upstream command taxonomy.

**Input:** requested workflow or assessment, current stage, content/artifacts,
platform, available tools, and authorized completion boundary.
**Output:** a scoped workflow, selected next module, or editorial assessment
with actionable gaps and clearly identified verification limits.

Read the [original blog orchestrator](../upstream/claude-blog/skills/blog/SOURCE.md)
for lifecycle coverage. Route executable writing work through the four other
packaged modules; do not dispatch the upstream slash commands.

Useful conditional references:

- [Quality scoring](../upstream/claude-blog/skills/blog/references/quality-scoring.md) for an explicitly requested editorial scorecard; scores are heuristics, not ranking predictions.
- [Editorial heuristics](../upstream/claude-blog/skills/blog/references/editorial-heuristics.md) for detailed editorial assessment.
- [Platform guides](../upstream/claude-blog/skills/blog/references/platform-guides.md) for the user's actual format.
- [E-E-A-T signals](../upstream/claude-blog/skills/blog/references/eeat-signals.md) for supported author expertise and provenance.
- [Schema](../upstream/claude-blog/skills/blog/references/schema-stack.md) or [crawler guide](../upstream/claude-blog/skills/blog/references/ai-crawler-guide.md) only for requested schema or crawl work.

Only five shortlisted source skills are collected. The rest of claude-blog's
suite, named agents, helper scripts, and provider integrations are absent.
The upstream workflow's community footer, media minimums, rendering requirements,
and automatic delegation do not become this package's defaults. Do not present
an unsupported upstream command as implemented. Read [package notes](../package-notes.md)
when resolving dependencies or proposing full upstream runtime use. Recheck
search-engine claims against current primary documentation if they affect the
user's work; the bundled update ledger is a dated snapshot.
