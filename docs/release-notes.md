# Release notes

The newest release is first. The version being worked on is in [`VERSION`](../VERSION), and the companion skills' floors are in [`pins/companions.json`](../pins/companions.json). Each studio's own changelog has the detail.

# Marketing Studio 4.19.0

Every studio is at 4.19.0. These are the changes since 4.18.1.

- **The parts of a project down the left.** Every studio's project page lists the project's parts on the left (a blog's outline and sections, a deck's slides, a training's materials, an infographic's parts), each with its state, from one shared list. A Presentation Studio deck that is not yet on the desk has no list.
- **Upgrade a Selected changes deck in place.** A Presentation Studio deck made with Selected changes can become Redesign, keep content without starting again. Nothing is spent until you press Start on the new step, which says what the redesign does and how long it takes; the changes you made are kept, and revisions already delivered stay delivered.
- **Old saved work opens more often.** A Presentation Studio deck paused in the old step-by-step flow now opens on the desk, and one whose record cannot be read opens as a read-only record with its files. Every saved state of the old flows in Blog Studio, Presentation Studio and Training Studio is now pinned by a test. Known limit: one Presentation Studio record the shared running-step check refuses, such as a desk deck started with research, stops sharing, migration previews and conversation edits for its whole workspace ([#541](https://github.com/dbbaskette/marketing-studio/issues/541)).
- **One look and fewer waits.** Since 4.18.1: one look for Marketing Studio and all four studios, a command palette that finds your work, questions asked in place, one main action per view, pages that stop polling while hidden, a home page that answers while a studio starts, companion checks that ask once, Brand setup in one pass (PDF brand books read, document templates, Rebrand a Google file), research and finished work kept in the Document Library with **Continue in another studio**, and Infographic Studio's long actions in the background with **Stop**.
- **Safer and smaller underneath.** Blog Studio, Presentation Studio and Training Studio send Google requests through one shared transport; Presentation Studio and Training Studio refuse redirects and any destination they do not use, and Blog Studio refuses a Word file whose inner XML declares a DOCTYPE or entity. Every PDF, Word and HTML reader is shared. Blog Studio's unused reference toolkit is gone, so a release has two Blog Studio archives, not three.

# Marketing Studio 4.18.1

Every studio is at 4.18.1. These are the changes since 4.18.0.

- **Learner tasks carried through delivery.** A training's assessed learner tasks, shared cases and job aids reach every material built from its teaching plan.
- **A one-page job aid for Infographic Studio.** An approved teaching plan's **One-page job aid** can be chosen in Infographic Studio's **Import selected studio material**.
- Research triage keeps a qualification that changes a decision, and Presentation Studio's repair and review steps keep attribution guidance.

# Marketing Studio 4.18.0

Every studio is at 4.18.0. These are the changes since 4.17.1.

- **Technical training that rehearses.** Training Studio plans technical workshops and CLI labs around what learners do: local configuration, a check or a conditional decision taught as such, and instructor preflight for what cannot be assumed.
- A paired teaching benchmark, for comparing technical trainings, is described in [Training Studio's teaching benchmark](../studios/training/docs/teaching-benchmark.md).

# Marketing Studio 4.17.1

Every studio is at 4.17.1. These are the changes since 4.17.0.

- Marketing Studio previews brands in batches, and research searches passages in batches, so both read less.
- A provider timeout offers a retry, and the Team Hub guide is back in Training Studio's navigation.

# Marketing Studio 4.17.0

Every studio is at 4.17.0, aligned for the first time. Versions 4.13 to 4.16 of the suite were never released; their work is in this release. These are the changes since 4.12.0.

- **Nothing pinned to one installed version.** Studios, Harness Research, Harness Slides and the brand skill are reached through a stable `current` link and installed and updated from their repositories' `main`, with oldest-accepted versions in [`pins/companions.json`](../pins/companions.json). The brand skill's release setting is gone. Training Studio and Presentation Studio update themselves from `main`.
- **No spending limits.** Nothing stops, pauses or warns for cost; reported cost stays as information. Assistant steps get more time, and Blog Studio's step time limit is gone.
- **Desks rebuilt as workbenches** with a shared shell: one Brief, Plan, Make, Ship arc, one card for what waits for you, and a command palette.
- **More ways in.** **Copy as new** for a training or deck, a whole folder of sources, every link in an uploaded file, up to 1,000 links per research run with Harness Research 1.2.0, the Document Library keeping files of any type, and **Document graphics** in Shared settings. Training Studio follows your outline and documents, plans as an instructor would teach and draws its own charts; Blog Studio writes solution briefs; Training Studio can rebrand a finished deck with **Change brand**.
- Studio READMEs were rebuilt around a first project, with illustrated guides.

# Marketing Studio 4.12.0

Marketing Studio 4.12.0 ships Presentation Studio 4.15.0 and Training Studio 4.14.0 (Blog Studio 4.10.1 and Infographic Studio 0.5.0 unchanged). These are the changes since 4.11.1.

- Finished research sections can be read before the final check, and concerns you queue are kept privately until you apply them.
- The time to the first readable section is reported apart from the time to the checked result.

# Marketing Studio 4.11.1

Marketing Studio 4.11.1 ships Presentation Studio 4.14.1 and Training Studio 4.13.1. These are the changes since 4.11.0.

- An idle desk checks a small change signal before reading its content again; focus and reconnecting catch up at once.
- Quick scan choices say more plainly what they do.

# Marketing Studio 4.11.0

Marketing Studio 4.11.0 ships Presentation Studio 4.14.0, Training Studio 4.13.0 and Infographic Studio 0.5.0. These are the changes since 4.10.0.

- An unfinished start form is kept across reloads, in Infographic Studio too.
- Slide-text review shows one slide at a time, and corrections are kept across reloads without starting work.

# Marketing Studio 4.10.0

Marketing Studio 4.10.0 ships Infographic Studio 0.4.0. These are the changes since 4.9.0.

- Marketing Studio's home refreshes pending work, and a preview that fails says why and how to recover.
- Infographic Studio keeps its renderer guidance when an approved file is recovered.

# Marketing Studio 4.9.0

These are the changes since 4.8.0.

- Brands are written and finished in the brands repository set in Shared settings.

# Marketing Studio 4.8.0

Marketing Studio 4.8.0 ships Presentation Studio 4.13.0 and Training Studio 4.12.0. These are the changes since 4.7.1.

- New decks and trainings warned and carried on at a project spending amount instead of stopping. (Spending limits were removed altogether in 4.17.0.)

# Marketing Studio 4.7.1

These are the changes since 4.7.0.

- `marketing-studio` commands reuse a studio link that is already running instead of starting another.

# Marketing Studio 4.7.0

Marketing Studio 4.7.0 ships Blog Studio 4.10.1, Presentation Studio 4.12.1, Training Studio 4.11.1 and Infographic Studio 0.3.1. These are the changes since 4.6.0.

- **See what the assistant is doing.** Every studio shows the assistant's work as it happens and keeps an Activity log for each project.
- **Approve the plan before detailed research.** Training Studio starts with a Quick scan outline you approve, and Presentation Studio with a slide story you approve. A new deck or training can be left half filled in and resumed.
- **Research that keeps its parts.** Section contributions are kept across retries, and a change to the sources previews which sections it affects before anything is redone. Local build steps recover, and saved work resumes where it was.
- **Settings.** A model and reasoning level for each kind of work, and a brands repository fetched only when you ask. Google Slides sources are read through Google Drive, and each studio README shows its workflow as a diagram.

# Marketing Studio 4.6.0

Marketing Studio 4.6.0 ships Blog Studio 4.10.0, Presentation Studio 4.9.0, Training Studio 4.8.0 and, for the first time, Infographic Studio 0.3.0, which is not yet signed off. Installs pin Harness Research 1.1.0 and Harness Slides 0.16.0, and Tanzu Brand 0.14.1 was tested. These are the changes since 4.5.0.

- **An editing desk in every studio.** New blogs, decks and trainings are made on an editing desk: a note rewrites only the part it names, History keeps earlier versions to compare and restore, and Finishing's tools propose changes you apply or skip. Presentation Studio's Slides tab reviews one slide at a time, and Training Studio's desk holds each level's materials. You can also ask your assistant to work on a desk in chat; a focused request stays focused and starts no other assistant.
- **Saved work keeps its path.** Work started step by step continues as before. Eligible unfinished work moves to the desk only after a preview you confirm, keeping its records, decisions and History. The shared **Where new work stops** setting is gone; existing runs keep their review level.
- **Blog Studio: a GEO review and reader aids.** Tick **Include a GEO review** on a new blog, or choose **Run GEO review** under Before publishing, for located proposals that make passages easier to reuse in AI search, such as a claim missing its date, version or unit, or a procedure that wants numbered steps. Finishing's **Reader aids and AI search** adds an FAQ, key takeaways, a comparison table, quotes checked against their sources, alt text and a definition-style opening, each previewed first. A detail only the author knows is asked for, never invented, and nothing is promised to earn citations or rankings.
- **Blog Studio: a GEO report for a published post.** **Get a GEO report for a published post** reads a live post's link and makes a report: what already works, ranked changes marked inline with their reasons, and **Page access** checks such as noindex, robots.txt for search crawlers, structured data, byline and dates. Download it as HTML or Markdown, make a Google Doc with each change as a suggestion, or **Edit this post on the desk**. **Link to a published post** also brings a live post to the desk for a GEO review.
- **Blog Studio: posts built by scripts.** When a page fetches its article with scripts, **Ask Codex to find the post's text** (or Claude Code) asks your assistant, with no tools or web access, where the text comes from on the same site. Blog Studio reads that address itself under the usual limits, and takes one second look within the same 3 minutes when the first answer finds no text. A recipe that works is kept for that site on this computer.
- **Blog Studio: also new.** **Check spelling and grammar** reviewed in your text, with optional more human-sounding wording; Copy edit in Finishing; the Google Doc round trip finished on the page with **Bring accepted changes**; other people's pending Doc suggestions shown on the desk; an SEO meta description from Repurpose; and a plain message when the assistant cannot reach its service from your network.
- **The Document Library.** Marketing Studio's new **Library** screen keeps text, Markdown, HTML, Word and PDF uploads and finished work on this computer: finished blogs, delivered decks with their matching PDF, ready learner guides and briefs, and approved infographics. **Add from library** copies a chosen revision into one project, and a newer revision is taken only with **Use revision N**. Uploads offer **Keep in library** or **Only this project**; in Blog Studio, **Keep a copy in the Document Library** or **Only this blog**. **Add existing work** previews older finished work before adding it, and **Remove from library** hides a document without deleting it. The library is kept in `library/` under your work folder, normally `~/Studios/library`. Choosing documents starts no research and shares nothing with your team.
- **Training Studio material review.** A material opens to read as learners receive it, with **Edit** for its parts and **Copy text** for a section. **Mark this level ready** lists each material as opened or not and changes nothing until you confirm, and **Undo** and **Return to draft** reverse it. Home, Trainings, Status and the desk show one standing for each training. A training kept locally can make a Google Doc of a guide or brief when you ask.
- **Presentation Studio.** New deck asks what the deck starts from and its goal, then lists what happens after Start. **Approve text & design deck** never drops a change you typed, and slide text can be corrected in place. The Delivered card keeps a receipt for every revision.
- **Shorter setup and clear ownership.** Shared settings lead with four everyday choices; models, the brand skill release, research sites and installations are under **Advanced**. The save state stays in view, and Shared, Override and Project tags say where each value is set. When another tab or studio saved first, the notice names the setting and offers **Load newer settings**; nothing is written from an outdated form. Studio cards say **Can open**, **Needs setup**, **Not checked** or **Not installed**, with one recovery action, and checking starts no assistant, sign-in or paid work.
- **Phone access.** With phone access on, the computer's home shows a QR code for the private link, drawn on the computer with nothing fetched. A studio opened on the computer stays at `127.0.0.1`; only one opened from the phone goes through the network bridge, which now accepts each studio's own upload sizes. Training Studio's materials and Infographic Studio work better on a phone.
- **Infographic Studio 0.3.0, not signed off.** The fourth studio turns supplied documents, notes, links or selected CSV into one branded page with source-backed story choices, editable labels and charts, a visual editor with readable history, exact-revision approval, and PNG, PDF, editable SVG and accessible-text exports, with optional Codex or Gemini artwork. Its editor, exports and provider adapters are implemented. Live Codex/Gemini image acceptance, artwork review and first-release sign-off ([#152](https://github.com/dbbaskette/marketing-studio/issues/152), [#223](https://github.com/dbbaskette/marketing-studio/issues/223), [#224](https://github.com/dbbaskette/marketing-studio/issues/224)) are still pending, and a fake-provider test is not proof of live provider access. Its initial acceptance target is macOS on Apple Silicon. See [first-release readiness](infographic-first-release-readiness.md).
- **Companions.** Installs use Harness Research 1.1.0 (up from 1.0.1) and Harness Slides 0.16.0, each at an exact commit and source checksum. Decks need a brand skill at 0.14.0 or newer, and this release was tested with Tanzu Brand 0.14.1. Marketing Studio never installs the brand skill.

Download `marketing-studio-installer.zip` for the whole suite, now with Infographic Studio, or one studio's installer ZIP. Each has a `.sha256` file for checking the download. Unzip it, then run `bash install.sh` in the unpacked folder, or open `installer/Install Marketing Studio.command` on macOS. Close running studios before you update. Your existing workspaces and settings are kept.

Signing in to an assistant, your organisation's brands and fonts, and optional Google setup are still your choices. Installing or opening a studio starts no provider job.

# Marketing Studio 4.5.0

Marketing Studio 4.5.0 ships Blog Studio 4.7.0, Presentation Studio 4.5.0 and Training Studio 4.5.0, with Harness Research 1.0.1 pinned and Tanzu Brand 0.14.1 tested. These are the changes since 4.0.0.

- **Your team's repository, connected.** Home says where each studio's work lives: connected to a repository and branch, local Git on this computer, or not connected, with a **Connect** action. A shared repository set in Marketing Studio now reaches studios that already have a workspace.
- **One team library.** Blog Studio keeps finished blogs, added files, lists of links and Google Docs in one library, each with a role, an author and a kind of post. A list of links by many authors is sorted by each post's own byline.
- **Voices and styles.** Learn a voice for any author, so ghostwriting has one voice for each person, and start from eight ready-made styles for technical writing. A voice can be learned from a file of links to an author's posts, from up to twenty samples. Voices and styles opens from Blog Studio's Home and sidebar.
- **Say what each file is for.** Each upload is marked as facts, an example of the kind of post, or approved messaging. Examples shape a post but never supply its facts. **I know the point** starts from the point you already have, and you choose the voice as you go. Write from a brief takes every file at once, and a Google Doc is read tab by tab.
- **The authoring workflow review, Phases 1 to 5.** Research can finish, and a failure says what to do next. Each thing has one name, and **Where this run stops** sets how often a run stops for you, saved once for every studio. Research stops show the brief, the independent check, the gaps and the findings for each question, along with what a change would cost. A training, deck or blog can be finished on its page: download it, bring back your edits, apply review findings and approve the version shown. Harness Slides, Harness Research and the brand skill are now fully used.
- **Research checks read the originals.** The independent check reads a supplied Google Doc, PDF or Word file as it is, so supplied material no longer fails the check again and again.
- **Research from your documents, your sites and/or the public web**, in every studio. Your sites are listed in Shared settings. Each page research saves is checked against them, redirects included, and a site can be added for a single piece of work.
- **Announcements that read like announcements.** Blog Studio writes approved messaging in the product's own voice and keeps source notes and open questions out of the text.
- **Delete from the lists.** Decks, trainings and blogs can be deleted from the lists and Home cards that show them, with each studio's usual confirmation.
- **Also since 4.0.0:** one shared Golden Gate look on every studio page; `marketing-studio start`, `stop` and `restart`; installer diagnostics and repository sync; slide text you can change after a deck is built; blogs finished, published, deleted and restored from the page; a blog written from your uploaded files, with three angles to pick from; and pages that work better on a phone.
- **Companions.** Installs use Harness Research 1.0.1 and Harness Slides 0.16.0, each at an exact commit and source checksum. Decks need a brand skill at 0.14.0 or newer, and this release was tested with Tanzu Brand 0.14.1. Marketing Studio never installs the brand skill.

Download `marketing-studio-installer.zip` for the whole suite, or one studio's installer ZIP. Each has a `.sha256` file for checking the download. Unzip it, then run `bash install.sh` in the unpacked folder, or open `installer/Install Marketing Studio.command` on macOS. Close running studios before you update. Your existing workspaces and settings are kept.

Signing in to an assistant, your organisation's brands and fonts, and optional Google setup are still your choices. Installing starts no provider job.
