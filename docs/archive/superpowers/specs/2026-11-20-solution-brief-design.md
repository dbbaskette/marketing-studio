# Solution brief route for Blog Studio: design draft

Date: 2026-11-20. Status: built on the branch that adds this file.

## As built

The first version differs from the design below in these ways:

- **The layout lives in the draft, not in a separate file.** A sidebar is a blockquote in the
  opening or under a `## ` heading, and the icon row is a list of `- [icon: words] **Label**:
  detail` lines in the opening. The person reads and edits them on the desk like any text.
  `brief.py` takes them out when the brief is made and builds the layout Harness Brand needs.
- **Icons are named as concepts and looked up.** The writing guide tells the assistant to use
  only the brand's icon library and to name each icon in plain words. `brief.py` asks Harness
  Brand's library for each one and refuses the brief, naming the words, when there is no match.
- **The brief rules run when the brief is made**, not in Finishing's proofread. "Make the brief"
  returns each rule as passed or to look at, with the page count from the render.
- **Two sidebars on one page are separated automatically** where that is safe: on page 1 the
  later one moves to the next section when that has none, otherwise its section starts a new
  page. A clash on the final page is reported for the person to settle.
- **No pictures yet.** A picture in the draft is not carried and is reported.
- **The open questions' defaults were taken**: briefs show in the existing lists, a LibreOffice
  render is the check, and a template marked not official is allowed with its warning.

## Goal

A person uploads files or links (approved messaging, product docs, an example brief) and gets a
branded solution brief as a Word file and a PDF, laid out like the reference brief built
on 2026-11-20: cover, one icon row, a sidebar on each page, one figure, a full final page.

## Decisions already made

| Decision | Choice |
| --- | --- |
| Document types | Solution brief only. White papers come later as a template choice. |
| Sources | Supplied sources by default. Outside research is opt-in per brief. |
| Where it is built | Blog Studio writes a structured brief. Harness Brand lays it out. |

## Not in this version

- White papers, or a separate fifth studio.
- A native Google Doc with the same layout. The Word file and PDF are the faithful outputs.
- A general layout engine. Only the slots the solution-brief template already has.
- Drawing the figure automatically (see open questions).

## How a person uses it

This section was revised on 2026-11-20 after reading Blog Studio's current source (4.10.1). The
first draft assumed the New blog wizard and `run create`, both of which have been removed: new
work starts on the writing desk, which has "ways" (`topic`, `outline`, `draft`, `shape`) and
three steps (research, outline, draft), with review and export in Finishing and Share.

**On the page.** "What would you like to do?" (`sStartTasks` in `assets/management/runner.js`)
gains one card:

> **Solution brief**: Turn messaging, product documents or links into a branded solution brief.

It opens the desk start with a new way, `brief`. The start asks for a working title, the files
and links and what each is for, and where research may look. It does not ask for a kind of post
or a length: a brief has a fixed shape. It needs a brand, and says so if none is set in Settings.

**In conversation.** The same start through `studio.py desk create --input FILE` with
`"way": "brief"`.

Source roles are the ones the desk already has, used as they are today:

| Role | Used for |
| --- | --- |
| Messaging | The product's approved claims, stated as the product's own. |
| Facts | Facts and figures the brief may quote. |
| Example | Shape only, such as an existing brief. No fact, figure or quote is taken from it. |

## Steps on the desk

The `brief` way uses the desk's existing steps. Only what each produces changes.

1. **Research** (only when the person opted in). Findings are marked as research, never as
   messaging.
2. **Outline.** A slot plan instead of an argument: title, subtitle, intro points, the four
   icon-row items, sections, one sidebar per page, the figure, summary and call to action. It
   lists every claim with the source it traces to, and the gaps. The person reviews it.
3. **Draft.** The brief's words as Markdown, and the layout (below) saved beside it.
4. **Finishing.** The desk's proofread gains the brief rules as findings (rules below).
5. **Share.** A new action, "Make the brief", hands the Markdown and the layout to Harness
   Brand and shows the pages, the Word file and the PDF. Sending it to Google Drive stays a
   separate, requested action.

Blog Studio is standard-library Python and writes no Word files, so it hands over Markdown.
Harness Brand's document mode reads Markdown as well as `.docx`.

## The handoff between the two tools

Blog Studio hands Harness Brand two files: the brief as Markdown (title, subtitle, headings,
paragraphs, lists, the figure) and `brief-layout.json`, which names what goes in each template
slot.

```json
{
  "template": "solution-brief",
  "icon_row": {
    "before": "The risks",
    "items": [
      {"icon": "functional-icons.database", "label": "AI-ready data",
       "detail": "Governed data products with context and lineage"}
    ]
  },
  "sidebars": [
    {"page_of": "The platform",
     "blocks": [
       {"type": "heading", "text": "Use cases"},
       {"type": "bullet", "text": "**Contain agents** in a locked-down runtime"}
     ]}
  ],
  "figure": {"caption": "Figure 1: Three layers of control"},
  "page_break_before": ["The platform"],
  "closing_from": "Why us"
}
```

Slots are anchored to heading text. A heading that matches no section, or more than one, is
refused: nothing is written.

Sidebar block types are `heading`, `body`, `bullet`, and `stat` (a pulled figure with its
attribution line). A `quote` type exists only for a quotation that a source attributes to a named
person.

## Harness Brand changes

Document mode gains `--layout FILE`. It ports the one-off script that built the reference
brief into a new module beside `document_template.py`:

- **Sidebars.** Copy the template's own first-page and later-page sidebar boxes and set the
  blocks in the template's sidebar styles.
- **Icon row.** Up to four icons in the template's invisible table, each with a label and a line
  of detail. Icons come only from the brand's library, in the brand's treatment, with alt text.
- **Figure.** Kept on one page with its caption, with space above it.
- **Page rules.** `page_break_before`, and `closing_from` to choose which section starts the
  final page. Today the last level-1 heading is forced there, which left "Summary" alone on a
  page.
- **Verification.** The existing all-or-nothing check extends to sidebar and icon text.
- **Render report.** After rendering, report the page count and which page each section,
  sidebar and figure landed on, so Blog Studio can check the rules without reading pixels.
- **Template capabilities.** Detected from the template itself (a sidebar text box, the
  invisible table style), so a brand whose template has no sidebar is refused with no brand
  data to maintain.
- **Markdown source.** Document mode accepts a `.md` file as well as a `.docx`.

## Rules the review stage enforces

These are the corrections made while building the reference brief, as defaults.

| Rule | Checked by |
| --- | --- |
| Four or five pages. The final page holds the closing section, not a stranded heading. | Render report |
| One sidebar per page. No two on the same page. | Render report |
| Exactly one icon row, on page 1. | Layout file and render report |
| The subtitle fits one line. | Render report |
| No table that restates the figure. | Judgment |
| No audience or targeting list, authors, sales plays or other internal-only content. | Judgment |
| No sources list. A third-party figure carries its attribution where it appears, or is listed as a gap. | Mechanical |
| No invented quotes. | Mechanical: a quote must trace to a source |
| A "claim boundaries" section in the messaging is a hard rule. | Judgment, listed in review |
| Every claim and figure traces to a supplied source or a research finding. | Existing claims check |

A brief that runs long is reported with what to cut. Type is never shrunk to make it fit.

## When things go wrong

| Situation | What happens |
| --- | --- |
| No brand set, or its template lacks these slots | The desk start says so before any work begins. |
| Harness Brand is missing or predates `--layout` | "Make the brief" says what to install; the Markdown download still works. |
| LibreOffice is absent | The Word file is produced and reported as not visually checked. |
| Harness Brand refuses the layout | The reason is shown and the run returns to the draft. |

## Testing

- **Harness Brand:** a fixture layout produces a document with the expected boxes, icons and
  page rules; the reference brief is regenerated and compared slot by slot.
- **Blog Studio:** the new way's steps, the brief rules in proofread, the desk start hiding kind
  of post and length, and the Share action with Harness Brand present and absent.
- **End to end:** from the messaging PDF alone, the run reproduces a five-page brief that
  passes every rule above.

## Build order

1. Harness Brand `--layout`, Markdown input and the render report, released on its own
   (`docs/superpowers/plans/2026-11-20-document-layout.md` in the Harness Brand repository).
2. Blog Studio's `brief` way, its outline and draft instructions and the brief rules.
3. The start card and the "Make the brief" action in Share.

## Open questions

1. **Who draws the figure?** The reference brief's diagram was hand-written SVG. Proposed for
   this version: the figure is optional and supplied by the person or made in Infographic
   Studio. The plan stage describes the figure it wants.
2. **Naming on the page.** Briefs would appear under "Blogs" and "My blogs". Is that acceptable,
   or should the list say "Blogs and briefs"?
3. **Checking in Word.** Rendering uses LibreOffice. Does a brief need a check in Word itself
   before it counts as done?
4. **Template status.** A brand pack can mark a document template as not official
   (`official: false`). Should this route refuse such a template, or only carry the warning?
