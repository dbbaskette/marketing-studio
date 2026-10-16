# Blog Studio research on harness-research

**Superseded** by the shared research component spec:
`docs/research-component-spec.md` in Marketing Studio
(https://github.com/dbbaskette/marketing-studio). Blog Studio is the first studio built to it,
and `skills/blog-studio/scripts/studio_research/` is the component's source copy.

## Blog Studio's part (its adapter)

- `scripts/deep_research.py` keeps Blog's rules around the component: the article's research
  policy decides whether public research is allowed; evidence comes only from references
  attached at their exact revision and planned with; fact-check claims match DRAFT.md
  exactly; a planned reference with a newer revision makes research stale; research saved by
  the earlier engine (`derived/research.json`) is reported stale and planned again.
- `scripts/blog_runner.py`: the `research-plan` stage takes a worker's JSON plan through the
  component and shows `research/plan.md`; the `research` stage runs `studio_research.steps`,
  each worker started by `blog_worker.generate(..., tools=...)` with the research tools, and
  shows `research/report.md`. Handing the stage in from chat needs a current finding for every
  question.
- Team sharing: the Hub carries `.harness-research/research.json`, its report,
  `research/plan.*`, `research/report.md` and `research/web/`; `research/sources/` is ignored
  and rebuilt from the shared references.
- Install: `installer/companions.json` and `installer/companions.py`, ported from Training
  Studio's installer.
