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

A voice belongs to one author, who may be the person you are writing for rather than
the person in the chat: a ghostwriter learns Sam Rivera's voice from Sam's posts and
starts a blog with that voice and Sam Rivera as its author. Name every profile for its
author and record the author on each sample (`--author`); ask whose writing it is
before reading it, and keep the permission to analyze it the person's to give. A voice
is not a style.
When the author wants a kind of writing learned, such as how product announcements are
shaped, learn a [style](workspace/styles.md) from examples by anyone and keep it apart
from the voice; a blog takes one of each, and the page offers them as **Write as** and
**Kind of post**. Links to public posts arrive through `library voice-links` (add
`--purpose style-sample` for a style, which skips the byline check) or the page's
**Tools → Voices and styles → Add links to posts**. A LinkedIn export arrives through
the page's **Import a LinkedIn export** (the `upload` route), as `author-background` and
`voice-sample` sources by the person it names. A post kept from another byline keeps
its published byline in the library.

For a list of an author's published posts (a `.txt` file or pasted links, one per
line; `#` comments and blanks ignored), confirm whose posts they are, then run
`library voice-links --file <list.txt> --author <name>`. It saves nothing and
reports the link count, the site scope (common host and folder), duplicates,
unusable lines and posts already in the library. A list mixing sites stops; ask
which one, then add `--site <host>`. With `--import`, the library's `urls` import
fetches the new pages (25 per call; repeat the same command to continue) and
classifies each as a voice sample for that author. A post whose page names
another author stays out; add `--keep <url>` only if the author wrote it, and
`--retry` to fetch failed links again. Then learn from up to twenty samples.

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

[Profile storage](workspace/profiles.md) stores each profile revision with its guide, background,
explicit rules, sample IDs, and provisional/confirmed state. Articles select a
specific revision. A later profile change affects new articles, not an existing
article's pinned voice; switching an existing article's voice is deliberate.
Only read relevant exemplars for a writing task. Export the guide when requested.
