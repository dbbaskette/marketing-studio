![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio works inside **Codex or Claude Code**. Tell it what you want to do:
plan an article, write a draft, improve something you already wrote, or talk through
an idea one question at a time. You stay in the same chat.

[**Get started**](#get-started) · [Simple commands](docs/prompt-cheat-sheet.md) · [First blog walkthrough](docs/new-user-guide.md)

## Get started

1. **Download `blog-studio-installer.zip`** from the
   [latest release](https://github.com/dbbaskette/blog-studio/releases/latest).
   No account or sign-in is needed to download or install it.
2. **Expand the ZIP** and open **Install Blog Studio.command** in its `installer`
   folder. Choose Codex, Claude Code, or both, and follow the setup instructions.
3. **Open a new chat** in your chosen tool and say:
   **“Use Blog Studio. Help me start a blog.”**

Already installed? Download the latest installer and run it again, then open a
new chat. An update brings new writing guidance and helpers together; your
drafts, voices, and Hubs stay where they are. If a new blog says the guidance
needs a newer Blog Studio runtime, this update is what it is asking for.
[What changed](CHANGELOG.md)

[Setup help, company laptop instructions, and updates →](docs/installation.md)

## Two ways to work

| | On the page | In a conversation |
| --- | --- | --- |
| Start | Open the page and choose **New blog** | Ask your assistant to use **Blog Studio** |
| Writing | The runner starts Codex or Claude for each stage | Your assistant writes with you |
| Decisions | Approve or request changes on the page | Approve or request changes in chat |
| Resume | Open **Home** or **Blogs** | Ask to continue your saved blog |

The page uses Training Studio’s navigation, three-step setup, progress stages
and paper review pages. Choose **Write a blog**, **Outline only**, **Revise a
draft**, or **Review a draft**. Both entry points keep the same sources, voice
and saved writing. A guided blog stops for approval at research questions, findings, outline, draft, review and export
package; you can omit research or choose an earlier stop. You can switch between
the page and your conversation without making another blog.

To open the page, say **“Use Blog Studio. Open the page.”** It needs a signed-in
Codex or Claude CLI to run the writing. Closing the browser leaves it working;
keep its terminal open. [Writing on the page and in chat →](docs/runner.md)

## Start with what you have

| You have… | Say… |
| --- | --- |
| A Google Doc | **Start from this Google Doc: [link].** |
| A draft on your computer | Attach it and say **Improve this draft.** |
| Notes or source material | **Use these notes to help me write a blog.** |
| An idea | **Make an outline about [topic].** |
| Experience you want to share | **Interview me.** |

Blog Studio asks for any missing details. You can ask for an outline, a first
draft, or feedback only. **“Help me set up my voice”** lets it learn from your
writing and preferences.

## Research before writing or checking facts

Say **“Research this topic”** to gather useful background before outlining or
drafting. Blog Studio also offers research when you choose your sources.

Uploaded source documents are included in research. Blog Studio reads them
first, retains their originals, and cites their relevant passages in the report.

Choose **Uploaded sources only** or **Uploaded sources plus external research**.
Blog Studio asks once and remembers the choice for this blog. You can also say
**“Research uploaded sources only”** or **“Research uploaded sources plus external
research”** to start directly. The first option stays within your supplied
material; the second adds public evidence where it helps.

Say **“Fact-check”** to check the current blog: it uses your saved references,
researches gaps, and shows supporting sources, contradictions and unanswered
questions. **“Show research”** opens the saved research brief. Findings and
references stay with your blog and can help later articles.

A readable research report is written automatically; no separate report command
is needed.

The workflow adapts [Deep Research skills](https://github.com/Weizhena/Deep-Research-skills).
It uses the tools already available in
Codex or Claude Code. Public searches use generic questions; private drafts stay
in your workspace and selected private Hub. You can say **“Use only my sources.”**
Proofreading stays focused on wording.

## Work with your team in Google Docs

If you start from a Google Doc, Blog Studio saves the original and a formatted
copy, then keeps **that same Doc** linked to your blog. Importing it does not
change the Google document or create a duplicate.

A typical review looks like this:

1. **“Start from this Google Doc: [link].”**
2. **“Proofread.”**
3. **“Push as suggestions.”**

Suggestions go back to the linked Doc so your team can review them. Blog Studio
checks the latest Google copy first. Prefer comments? Say **“Push feedback as
comments”** to leave feedback without changing the document text. If suggested
edits are unavailable, it uses
readable review comments and tells you where to find them. Say **“Show review
edits”**, then **“Apply edits 2 and 4”** to choose which comment proposals to apply.

After someone edits in Google, say **“Pull from Google Docs”** or **“Pull and
proofread.”** Blog Studio brings back the latest writing and saves a formatted
Word copy. It checks for competing edits before replacing local work.

Starting a blog in chat instead? **“Push to Google Docs”** sends it to Google.
Later pushes update the linked Doc. Use **“Push as suggestions”** when you want
review proposals instead of direct edits.

Google access needs a separate connection. You can say **“Use this folder for
team reviews: [link]”** and **“Use this as our blog template: [link].”** Blog Studio
remembers selected team preferences in your Hub and checks access before use.
These preferences do not change who can see a document.

Some document layouts need extra handling; Blog Studio will tell you when an
import or update cannot be completed.
[Google Docs setup and help →](docs/google-docs.md)

## Pick up where you left off

| Say… | To… |
| --- | --- |
| **My blogs.** | Find saved work |
| **Continue [title].** | Resume a blog |
| **Show status.** | See its working Doc link, save status, and next step |
| **Save and sync.** | Save your work and share it with your selected Team Hub |

A **Team Hub** is your team's private writing library on GitHub. It keeps blogs,
sources, notes, voices, and writing rules together, organized by author and title.
Earlier versions remain available.

Say **“Join our Hub: [repository link].”** Normal saves then share the selected
workspace with that Hub. Without one, your work stays on your computer. Blog
Studio tells you when a save is still waiting to be shared.

Your Hub lives at `~/blogs/<hub-name>/`, with readable shared files and Git history
together. Local drafts and sync state stay in the hidden `.blog-studio/` folder.
Existing Hubs can be moved by saying **“Move our Hub to the standard folder.”**

[Create or join a Team Hub →](docs/team-hub.md) · [More simple commands →](docs/prompt-cheat-sheet.md)

## See the team's work

Say **“Open editorial desk.”** A private page opens on your computer with:

- **Blogs in progress:** owners, due dates, stages, and working Google Doc links.
- **Needs attention:** review findings, waiting decisions, and stale companions.
- **Reference library:** browse and curate earlier posts. Choose **Import old blogs** to add a folder, website, feed or export. Preview the list and check only the posts you want to save.
- **Team memory:** shared notes, context, and writing rules.

Everyone with write access to your Hub uses the same controls. GitHub manages
membership. The desk runs locally; your private Hub also has readable editorial
and collection pages. Google links reflect saved information—ask in chat to
refresh Google content or feedback.

| Say… | To… |
| --- | --- |
| **Show our pipeline.** | See your team's writing stages and next actions |
| **What needs my attention?** | Find work needing a decision or review |
| **Import our old blogs from [folder or site].** | Preview a historical reference collection |
| **Find our previous blogs about [topic].** | Find relevant earlier writing |
| **Show evidence.** | Inspect support for important claims |
| **This needs a diagram.** | Prepare a visual companion |
| **Package this for launch.** | Prepare copy for your chosen channels |

Reference documents and links you add are saved for reuse in later blogs, locally
and in your selected private Hub. New-blog planning searches relevant saved
references and earlier posts; it loads only useful passages. Source dates and
revisions stay attached so old product claims can be checked. You can say
**“Use our saved references about [topic].”**

Readable imports can be summarized and tagged for later reuse (topics, products,
and cautions). That analysis sends the document text through your signed-in
Codex or Claude CLI to its provider; the upload and import dialogs show the
choice, and you can turn it off per upload. **Review details** lets you correct
the results; **Analyze reference** retries unfinished analysis. Originals are
retained. PDFs without extracted text remain marked **Needs extraction**.

Imports are previewed before a bulk save. Earlier posts remain references until
you explicitly choose to start an editable blog. Packages and visuals stay tied
to their draft; changes flag them for review. Preparing them does not publish.

The desk tells you whether work was **saved on your computer**, **shared with
your Hub**, or **waiting to sync**. Pending saves offer **Retry sync**. While a
view, search, or page loads, a message appears and page buttons pause.

If a reference changes while you edit its tags or notes, your proposed changes
stay in the form. Choose **Reload and compare**, then choose the latest saved
values or keep your proposal before saving again. Reloading alone does not save
changes.

Open a blog title or choose **Inspect finding** to see the saved writing and its
review status. **Copy request** gives you a short handoff to continue that specific
blog in chat. Editorial fields, reviews, and history open when you need them.

The desk shows your Hub access before editing. Read-only members can browse and
refresh; decisions and specialized memories explain how to continue in chat.

[Using the editorial desk →](docs/editorial-desk.md)

## The right help at the right time

**Idea → sources and voice → outline or draft → review → shared editing**

You can start at any step. Blog Studio loads only the instructions your request
needs, so short requests stay quick. You do not need to manage the individual
skills yourself.

Writing guidance and helpers update together when you run a newer installer.
Each blog records the version it was started with.

[How it works and token estimates →](docs/progressive-disclosure-roadmap.md)

## Your content stays under your control

Work stays in your chosen AI tool, on your computer, and in your selected private
Team Hub. Google transfers use the content and document you select. Blog Studio
adds no telemetry uploads. Your AI provider, GitHub, and Google process content
under your account settings.

[Privacy details](docs/privacy-review.md) · [House style](docs/house-style-guide.md) · [Troubleshooting](docs/troubleshooting.md)

---

**For developers and team administrators:** [Developer guide](docs/development.md) ·
[Roadmap](https://github.com/dbbaskette/blog-studio/issues/3) ·
[Performance evidence](docs/performance.md) · [Hub acceptance walkthrough](docs/hub-acceptance.md) · [Package details](PACKAGE.md)
