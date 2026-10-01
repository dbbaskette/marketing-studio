# Voice setup and reuse

Start from a chosen saved profile, confirmed authored samples, an imported
manuscript's voice, or directly stated tone. A voice-only request does not
create an article. Read [voice profile](modules/blog-voice-profile.md) to learn it.

For a new profile offer:

> Share your LinkedIn profile or About text, links to writing you've authored,
> uploaded samples, or pasted passages. You can also describe your tone and
> preferences. Which writing best represents how you want to sound?

LinkedIn bio information informs identity and subject expertise. Authored posts
and articles inform prose style. A URL is accepted as an input, not a promise
that its full contents are accessible. If inaccessible, request pasted material
or an export through normal chat attachments. BlogForge's export path reads
`Profile.csv` and HTML articles in an `Articles/` folder; exports without those
items still need actual writing samples. Use local ZIP/CSV readers; no LinkedIn
login, scraping service, or new credentials are required by this skill.
Use the packaged `scripts/linkedin_import.py --file <export.zip>` for a supplied
export. It reads only profile background and article HTML, emits JSON, and does
not extract arbitrary archive paths or import unrelated contacts/messages.
Normalize selected articles through source intake before adding them to a profile.

A few representative samples help; even one can support a provisional guide.
Ask for favorites when prioritization matters. Extract observed style separately
from explicit author preferences and factual biography. Do not store unrelated
personal information from an export. Use supplied biographical facts; do not
infer career experiences from stylistic examples.

Show a concise voice summary and a short audition preserving all supplied
facts. Invite corrections to that concrete result. If the author explicitly
requests saving it, save; otherwise a setup task may save a provisional profile
and label it clearly until the audition is confirmed. Do not invent a confirmed
voice or train it on generated samples automatically.

[Workspace](workspace.md) stores each profile revision with its guide, background,
explicit rules, sample IDs, and provisional/confirmed state. Articles select a
specific revision. A later profile change affects new articles, not an existing
article's pinned voice; switching an existing article's voice is deliberate.
Only read relevant exemplars for a writing task. Export the guide when requested.
