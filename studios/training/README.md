![Training Studio: audience and sources, review the plan, build materials and mark ready](docs/assets/training-studio-header.svg)

# Training Studio

Turn a subject into training people can use. Describe your learners and their goal,
review what will be taught, then build a learner guide, reference brief, slide deck
and practice at the levels you need. Read and refine the materials on one desk.

Training Studio works independently or from [Marketing Studio](../../README.md).
Your signed-in Codex or Claude Code does the assistant work, Harness Research
handles evidence, and Harness Slides builds requested decks in your brand.

[Install](#install) · [Your first training](#your-first-training) · [The desk](docs/the-desk.md)

## Choose your materials

| Material | What it gives you |
| --- | --- |
| Research and teaching plan | Sources, learning objectives, coverage and sequence |
| Learner guide | The material learners read |
| Product or competitive brief | A concise reference for one subject or a comparison |
| Slide deck | Slides and speaker notes for teaching |
| Practice scenarios | Role-play, pitch, tutor or questionnaire practice |
| Optional Yoodli layout | Fields and reference material to build a roleplay in Yoodli yourself |

Choose levels **101** (introduction), **201** (practical use), **301** (architecture
and troubleshooting) and **401** (internals and advanced design). Research is shared;
each selected level gets its own materials. You can add levels later.

## Install

Choose an available Training Studio or suite bundle from
[Releases](https://github.com/dbbaskette/marketing-studio/releases), unpack it,
and run `bash install.sh` from that folder. You do not need a `.command` launcher.

Or install from source:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh --studios training
```

Select integration with `--target codex` or `--target claude`. Bring Git and your
installed, signed-in assistant. Prepared bundles include selected private runtimes
and dependencies; source installers may fetch prerequisites.

Research requires Harness Research. Decks also require Harness Slides, your brand
skill and fonts, and the selected preview tools. Google and Word copies need their
optional tools. Missing capabilities are explained rather than silently substituted.

[Requirements and platforms](../../docs/installation.md) ·
[Package independently](../../docs/packaging.md)

## Your first training

1. **Open Training Studio.** Use `marketing-studio open training`, or its independent
   launcher:

   ```sh
   sh ~/.local/share/training-studio/studio
   ```

   Keep the terminal open. Complete shared setup with your assistant, work folder
   or team repository, name and optional brand/delivery choices.
2. **Choose New training.** Explain what learners should be able to do, their
   starting knowledge, the levels, time and materials. Add reference documents and
   choose where research may look: documents, approved sites and/or the public web.
3. **Check the topics.** **Here’s what this training will cover** shows coverage,
   depth and timing. **Ask for changes** revises the plan; **Build the training**
   makes the selected materials. There is no sample lesson to approve.
4. **Review requested slide text.** If you selected a deck, **Review slide text**
   shows its words and notes. Ask for changes or choose **Approve text & design deck**
   for that version before design starts.
5. **Read, edit and mark ready.** Material tabs show the formatted guide, brief,
   slides and practice; level tabs keep the depth separate. Review results as they
   arrive. **Mark ready** is your approval of the material shown, not merely evidence
   that the assistant finished writing it.

## Refine the training on the desk

Edit a part, add a note or select a passage for a focused change. History retains
previous versions. A result cannot silently replace text you changed while it ran.
The slide card supports words, speaker notes and section-scoped redraw requests.
Drawing-bound word edits retain Harness Slides’ explicit design-answer requirement.

When an input changes, dependent material may be **held**. Choose **Update** to
remake it from the current input, or **Keep as it is**. The proposed update says
what it reaches and its available price history. New sources wait for the explicit
research update; adding a document alone starts no research.

**Finishing** applies to the selected material and proposes checks or changes.
Choose Apply, Edit or Skip. Local checks and assistant-backed checks are identified;
serious blocking findings still prevent readiness. **Mark this level ready** previews
its materials before confirmation. Undo or Return to draft retains History and
previous library copies; editing a Ready material returns it to Draft.

[The complete desk guide](docs/the-desk.md)

## Download, reuse and share

Download one material or a ZIP of a level/all levels as currently saved. A download
does not mark anything ready. Ready guides and briefs can be kept as Markdown in
the shared local Document Library; a failure offers a local retry. Training deck
PDFs are not currently kept there. **Add from library** captures a selected revision
as this training’s own source.

Google Docs for a guide or brief are optional. Sending and pulling changes use the
supported explicit actions and conflict handling. The index and publishing are
separate from individual material readiness. A Yoodli layout is copied into Yoodli
by you; Training Studio does not upload it.

[Document Library](../../docs/shared-setup.md#the-document-library) ·
[Google Docs](docs/google-docs.md) · [Scenarios and Yoodli](docs/scenarios-and-yoodli.md)

## Work in a conversation

Complete setup first, then ask your assistant to use Training Studio in the configured
workspace. Describe the finite scope: a teaching plan, guide, practice, or the full
selected training. Checked desk commands create, inspect and submit the material
without starting a nested assistant. A page visit or restart does not transfer that
work to the runner; handoff is an explicit request.

Only you approve and mark materials ready. The conversation-owned page offers its
supported reading, readiness and download actions; it does not expose every runner
editing tool. Follow the [conversation guide](skills/training-studio/references/conversation.md).

## Teams, saved work and help

One computer drives a shared training at a time. Takeover is explicit; unshared
work and missing private inputs are handled before changes continue. Shared defaults
are common to all four studios, while each workspace stays where it was configured.
Older conversation work can share finished trainings, and reuse your team's
scenarios, audiences and research, through the [team hub](docs/team-hub.md).

Older saved trainings keep their compatible flow. Eligible unfinished work offers
**Open on the desk**, a read-only preview, then Apply/Cancel. It preserves original
records and starts no work or approval. Unsupported or missing-input work retains
its saved path. [Saved-work compatibility](../../docs/saved-work-compatibility.md)

Use **Status → Check this computer** for missing tools or assistant sign-in. Follow
the [installation guide](../../docs/installation.md) for updates and rollback; close
idle studios before an update. Never discard a workspace to fix a tool problem.

[Runner and team workflow](docs/runner.md) · [Development](docs/development.md) ·
[Acceptance and limits](docs/acceptance.md) · [MIT licence](LICENSE)
