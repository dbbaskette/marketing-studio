# Google Docs, when requested

Load only for a supplied Google Doc or a requested Google operation. Ordinary
writing stays on its current route and needs no Google account or CLI.

| Intent | Load |
| --- | --- |
| Start/edit a blog from an existing Doc | [start from Google](start.md) |
| Use a Doc as material | [source](../modules/blog-google-source.md) |
| Continue drafting in Docs | [handoff](../modules/blog-google-handoff.md) |
| Bring edits back | [return](../modules/blog-google-return.md) |
| Send proofreading as suggested edits | [suggestions](suggestions.md) |
| Leave/reply/resolve comments | [review](../modules/blog-google-review.md) |
| Use a native template | [template](../modules/blog-google-template.md) |
| Download or share | [export and sharing](../modules/blog-google-export.md) |

Read [adapter contract](adapter.md) once when selecting a connection; recheck
changed capabilities. For the local CLI connection or sign-in, load
[gcloud access](gcloud.md). Read [checkpoint contract](checkpoints.md) only for a
local transfer/receipt command. Reuse fresh provider observations. A failed or
unavailable operation retains local work; offer a supported local outcome.

Keep credentials with the connected provider. Read [privacy](../privacy.md)
before external operations. Only selected content crosses into Google;
background, private sources, voices, rules, and interview notes stay private
unless individually selected. A shared folder can already grant access: inspect
its audience before placing a private draft there. Posting is not publishing.
