# Synthesis research

For fresh research, follow the installed Harness Research synthesis workflow in
`.studio-research/`. Send the presentation audience and actual goal as free-text
`purpose`; preserve scope and source permissions separately. Ask for evidence and
messages worth explaining visually, with objections and qualifications. Obtain
independent evidence and semantic review of the exact report and authored brief.
Verify the complete bundle; a readable draft is not checked research.

Use `python "<studio-runtime>/scripts/studio_core/research_contract.py" --case
.studio-research --project <deck>` with the actual case path `.studio-research`
to copy the owned case, evidence and bundle. Read `research/report.md` and
`research/brief.md`, retaining conditions, counterfacts and gaps in the outline.
Record run schema 3 and the returned `contract` as `research_contract`, then
completed research steps in `run.json` and the person's actual decisions
as the workspace reference describes. Existing legacy research keeps its old
helper commands and saved format. A page-driven deck is handled by its runner.
