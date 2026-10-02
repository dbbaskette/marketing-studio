# Blog Studio prompt cheat sheet

Copy these prompts into your Codex or Claude Code chat with Blog Studio installed.
These are chat requests, not terminal commands. Replace bracketed text with your
own details. Once you have selected a blog, “this blog” means that article.

**Typical flow:** start → add sources and voice → outline → draft → review →
Google Docs → bring edits back → save to Hub → resume later.
Skip steps you do not need.

## 1. Get ready

> Use Blog Studio. Check my setup and show me my starting choices.

To work with your team, join its existing private Hub once for this workspace:

> Join our Team Hub at [GitHub repository URL] and use it for this writing project.

You need existing repository access. Joining does not upload earlier local work.
To share an existing blog, ask: “Share my saved blog ‘[title]’ with this Hub.”

## 2. Pick a starting point

Choose one:

| I want to… | Say this |
| --- | --- |
| Explore ideas | Give me three blog ideas about [topic] for [audience], with a takeaway for each. |
| Be interviewed | Interview me about [topic], one question at a time. Help me reach an outline. |
| Make an outline | Build an outline about [topic] for [audience]. Stop before drafting. |
| Get a first draft | Write a first draft about [topic] for [audience], around [word count] words. Ask for missing source material first. |
| Use my outline | Turn my attached outline into a draft. Preserve its argument and section order. |
| Improve my draft | Review my attached blog. Preserve the original and give feedback before rewriting. |

Optional:

> Help me choose the blog type: announcement, tutorial, architecture explanation,
> performance deep dive, comparison, or customer/engineering story.

## 3. Add sources and your voice

> Ask me what source material I want to provide before we write.

> Use [file path or link] as factual source material for this blog. Tell me if you cannot read it.

> Use this Google Doc as a source: [Doc link].

For a reusable voice, set it up once:

> Help me create a voice profile called “[name].” Ask for my LinkedIn background
> and blogs I have written. Show me a voice summary and a short sample before saving it.

After reviewing the sample:

> Confirm and save this voice profile. Use it for this blog.

For later blogs:

> Use my saved “[name]” voice profile.

LinkedIn supplies background; your authored samples supply writing style. Paste
text or provide a file when a link is inaccessible. A saved voice is optional:
“Use a clear, conversational tone” works too.

## 4. Outline, draft, and revise

> Create and save an outline from our sources. Stop at the outline.

> Turn the saved outline into a first draft of about [word count] words. Save it.

> Tighten the introduction and remove repetition. Keep the facts and my voice.
> Save a new revision.

> Give me five title options and a clear next step for the reader.

## 5. Review the writing

> Check this blog against our house style and chosen blog type. Give feedback first.

> Check technical claims against our sources, including versions, availability,
> code examples, and performance claims. Flag unsupported statements.

> Apply the agreed edits and save a new revision. Tell me what changed.

## 6. Send it to Google Docs for shared editing

For the first handoff:

> Put this draft in Google Docs in [review folder link]. Verify the result,
> save the checkpoint, and give me the working Doc link.

For a blog that already has a linked Doc:

> Check whether Google or our local copy has newer changes. Show any conflicts
> before sending anything.

Then, when ready to send local wording edits:

> Send these wording changes to the linked Google Doc. Preserve the team's
> heading sizes, spacing, and formatting. Verify the result and save the checkpoint.

Google access must be connected. If a requested edit cannot preserve formatting,
Blog Studio should explain the limitation before changing the document.

## 7. Bring the team's Google edits back

After editing in Google Docs, including spacing or heading changes:

> Bring back the latest edits from the linked Google Doc, including formatting.
> Save the formatted DOCX snapshot and readable Markdown to our Team Hub.
> Show conflicts before resolving them. Do not send anything back to Google.

The Doc stays the live shared editing copy. DOCX stores its exported formatting;
Markdown provides readable text and Git diffs. Pending suggestions or multiple
tabs may require a scoped return instead of the automatic snapshot workflow.

## 8. Save, find the links, and come back later

> Save this blog and sync it to our Team Hub. Tell me whether it is shared,
> queued, pending review, or conflicted.

> Show me this blog's GitHub page and working Google Doc link.

> Show my blogs.

> Find our team's blog about [topic] and help me continue it.

> Continue “[blog title].” Check whether Google or our local copy has newer changes.
> Show the last check, last confirmed save to the Hub, and next step.

Normal Blog Studio saves sync the changed item and its selected dependencies when
a Hub is selected. Without a Hub, saves stay local. Google edits come back when
you request them; there is no background watcher. Queued or pending-review work
is not yet on shared main. Google freshness is only known at the time of a successful
live check.

## Handy extras

| I want to… | Say this |
| --- | --- |
| Inspect context | What sources, voice, rules, and review results are selected for this article? |
| Set an article preference | Remember for this article: [preference]. |
| Set a shared rule | Remember for our team: [rule]. |
| Stop using a preference | Forget this article's [preference]. |
| Organize the GitHub library | Set this blog's author to [name], rename it “[title],” and sync it to the Hub. |
| Export | Export the latest linked Google Doc as a Word file or PDF and tell me where it is saved. |
| Repurpose | Create a LinkedIn post from this blog using the same facts and voice. Save it for review. |

Forgetting a preference stops its active use; it does not erase Git history.
Google version milestone names are currently manual: in the Doc, use
**File → Version history → Name current version**. A milestone name does not
confirm freshness or save anything to the Hub.

[Project README](https://github.com/dbbaskette/blog-studio#readme) · [Installation](installation.md) ·
[Full first-session guide](new-user-guide.md) · [Google Docs details](google-docs.md) ·
[Team Hub details](team-hub.md)
