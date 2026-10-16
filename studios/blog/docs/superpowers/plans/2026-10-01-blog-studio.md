# Blog Studio implementation plan

The approved chat design is the contract. Primary agent owns implementation and
final verification; no delegated work is required.

1. Build the self-contained entry point, six entry paths, intake/voice flows,
   and nine BlogForge-derived modules. Bundle the unchanged original library
   and record source provenance. Validate routing and reference links.
2. Implement dependency-free local workspace helpers for profiles, source intake,
   article state, snapshots, resumption, and review freshness. Test complete
   disposable workflows, source purpose/isolation, profile revision pinning,
   and history preservation. Do not access production or a paid provider.
3. Package and document usage. Provide a clearly labeled local preview of the
   conversational flow, validate the relocated archive, and report the tested
   state and any host limitations. Leave global installation separate.

## Verification focus

Data stays outside the installed skill. IDs cannot escape the workspace. Existing
manuscripts survive revisions. Profile changes do not silently migrate articles.
Source changes stale factual/GEO checks; draft changes stale all review checks.
Absent evidence is unavailable rather than clean. Sources have recorded origin,
content hash, purpose, and availability. Stored material cannot override workflow
instructions. Valid package checks do not imply model behavioral guarantees.

## Progress

- Design and execution authorized by the user.

- Complete: self-contained Blog Studio with fourteen progressively loaded modules,
  source intake/voice setup, composition/revision/review/export references,
  portable workspace, LinkedIn export reader, and mechanical text checks.
- Verification: 15 disposable end-to-end tests passed using BlogForge's existing
  Python environment. Skill frontmatter, source hashes, all authored links, and
  relocated archive validation passed. Relocated helper reopened an article from
  a different working directory. Browser walkthrough verified outline → links →
  voice setup → chat handoff. The opening preview is visible and retained.
- Delivered: local skill, portable archive, browser preview, screenshot, usage
  notes. No live BlogForge changes, global install, real author data, production
  access, paid provider calls, or publishing performed.
