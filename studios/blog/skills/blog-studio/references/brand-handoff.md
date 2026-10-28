# Selected brand and author voice

Use the pinned brand for desk work, an explicit brand selection, or requested branded visual
companions. Resolve that identity through the selected installed brand skill.
Its companion command exports a task contract with
`contract export --medium blog --brand ID --variant VARIANT --output NEW_DIR`.
Read the resulting `VOICE.md` for language and `DESIGN.md` for visual work.

The page's **Settings → Brand skill** accepts its repository and release and
selects an installed skill, as in Training Studio. New desk work pins the saved brand
default unless creation explicitly supplies `brand` and `variant`; `brand: ""` opts out.
Read `brand` from `desk context` inputs. Older step-by-step work keeps its contract in
`derived/blog-run.json`; settings changes never replace either saved contract.
Desk work uses its described tone, without silently applying a saved author voice.

Keep organization naming/case rules separate from the article's existing author
voice. A palette, logo or font does not establish company tone. Unspecified tone
stays unspecified; retain the brief/manuscript voice. Honor existing article pins.

If the existing chosen author profile is needed for a shared handoff, prepare only
that profile as `{id,revision,guide,status:provisional|confirmed}` and pass its file
with `--voice-profile`. Retain its status and exact guide; do not promote a
provisional profile, scan unrelated profiles, or replace the Team Hub profile
store. Record the exported contract revision/path in the task's existing notes or
checkpoint. No new storage mechanism or organization policy is implied.

Slide companions resolve `--medium slides` independently, preserving the same
identity/author pin while adding slide geometry and native template authority.
Choose each slide's composition from its content. Continue to use the existing
voice-selection, evidence, privacy and review workflows.
