# Blog Studio cheat sheet

Talk to Blog Studio in your Codex or Claude Code chat. Short requests are enough.
It uses the current blog, saved voice, sources, Team Hub, and linked Google Doc.
It asks for missing details or a choice when there is more than one match.

## A typical session

1. **Start a blog about [topic].**
2. **Use these notes.**
3. **Make an outline.**
4. **Write the draft.**
5. **Proofread.**
6. **Push to Google Docs.**
7. Edit with your team in Google Docs.
8. **Pull from Google Docs.**
9. **Save and sync.**

Skip steps or combine them: **“Pull from Google Docs and proofread.”**
That brings the edits back and proofreads locally. Ask **“Push to Google Docs”**
when you want to send the revised wording back. For changes the team should
approve first, say **“Push as suggestions.”**

## Start or continue

| Say | To… |
| --- | --- |
| Use Blog Studio. | Start the writing flow |
| Check my setup. | Find setup or sign-in problems |
| Show my blogs. | Browse saved work |
| Continue [title]. | Resume a blog and show its status card |
| Show status. | Show the current blog’s status card and links |
| Give me some ideas. | Explore topics |
| Interview me. | Develop your idea one question at a time |
| Improve this draft. | Work on a draft you supply |

## Sources and voice

| Say | To… |
| --- | --- |
| Use these notes. | Add supplied source material |
| Start from this Google Doc: [link]. | Import the draft, preserve formatting, and link the same Doc for push/pull and suggestions |
| Use this as a source: [link]. | Add a web page or Google Doc |
| Help me set up my voice. | Provide background and writing samples |
| Save this voice. | Confirm the voice you have reviewed |
| Use my voice. | Apply your saved profile |
| Make it more conversational. | Adjust the tone |

## Write and review

| Say | To… |
| --- | --- |
| Make an outline. | Plan the blog before drafting |
| Write the draft. | Draft from the current brief and material |
| Proofread. | Correct spelling, grammar, and punctuation |
| Tighten it up. | Improve concision and remove repetition |
| Check the facts. | Check claims against available evidence |
| Check our style. | Review against selected team and house guidance |
| Suggest some titles. | Explore headline options |
| Apply those edits. | Make the changes just discussed |

## Google Docs and saving

| Say | To… |
| --- | --- |
| Push to Google Docs. | Send the current draft or its updates to the working Doc |
| Push as suggestions. | Refresh Google, then post native suggestions or clearly labeled review comments |
| Show review edits. | See the numbered comment-review findings |
| Apply edits 2 and 4. | Apply only those changes, recheck formatting, and resolve completed comments |
| Pull from Google Docs. | Bring back the team's text and formatting changes |
| Which copy is newest? | Check Google against the local copy |
| Show me the Google Doc link. | Find the working Doc |
| Save and sync. | Save and synchronize to the selected Team Hub |
| Is everything saved? | Check local and Hub save status |
| Show me this blog in GitHub. | Find its readable Hub page |
| Export to Word. | Get a Word copy |
| Export to PDF. | Get a PDF copy |

On the first Google handoff, Blog Studio asks for the destination if it is not
already established. Later requests reuse the linked Doc. Formatting preservation,
verification, and conflict checks belong to the skill—you do not need to repeat
them in every prompt. If access or an operation is unavailable, it explains what
is needed rather than claiming success.

“Push as suggestions” checks the latest Google copy automatically. It refreshes
affected findings and stops for competing edits; no separate pull prompt is needed.
After the team accepts or rejects proposals in Google, say **“Pull from Google Docs.”**
The returned Markdown contains accepted text; pending suggestions stay separate.
If native suggestions are unavailable, Blog Studio posts comments with current and
proposed wording. For ordinary comments, open **All Comments**. Use **“Apply edits
2 and 4”** to select changes; resolving a comment does not approve it.

Pulling retains a formatted DOCX snapshot and readable Markdown when supported.
Google edits are pulled on request. Normal Blog Studio saves sync to a selected
Hub; without one, they stay local. Queued or pending-review work is not yet shared
on the Hub's main branch.

## Team and finishing touches

| Say | To… |
| --- | --- |
| Join our Hub: [repo link]. | Connect to your team's existing private Hub |
| Share this blog with our Hub. | Share an existing local article |
| Remember for this blog: [rule]. | Save an article preference |
| Remember for our team: [rule]. | Save a shared preference |
| Show my defaults. | Inspect your saved writing defaults |
| Show the sources for this section. | Retrieve relevant source passages with their saved revisions |
| Clear local caches. | Remove disposable derived data; keep your writing and history |
| What changed? | Compare with the previous checkpoint |
| Undo that edit. | Restore earlier text as a new revision |
| Set the author to [name]. | Organize the blog under its author |
| Rename this blog to [title]. | Update its title |
| Make a LinkedIn post from this. | Prepare a social draft |

## Editorial desk and earlier posts

| Say | To… |
| --- | --- |
| Open editorial desk. | Browse blogs, upload references, and curate team memory |
| Show our pipeline. | See stages, owners, due dates and Doc links |
| What needs my attention? | See reviews, waiting decisions and stale work |
| Assign this blog to [name], due [date]. | Record its owner and due date |
| Mark this ready for review. | Make an explicit editorial decision |
| Import our old blogs from [folder/site/feed/export]. | Preview a reference collection |
| Find our previous blogs about [topic]. | Search retained earlier posts |
| Use these posts as references. | Pin selected sources to your blog |
| Refresh our blog library. | Preview changes and import a bounded batch |
| Learn from our old blogs. | Propose source-linked writing lessons |
| Show evidence. | Inspect selected factual claims and cited passages |
| This needs a diagram. | Prepare a grounded visual and caption |
| Package this for launch. | Prepare selected channel drafts and links |

Blog Studio asks only for missing details. Imports and rule promotion are explicit;
preparing a package does not send or publish it. [Desk guide](editorial-desk.md).

[Project README](https://github.com/dbbaskette/blog-studio#readme) ·
[Status card](status-card.md) · [First-session guide](new-user-guide.md) · [Setup](installation.md) ·
[Google Docs](google-docs.md) · [Team Hub](team-hub.md)
