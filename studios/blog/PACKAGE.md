# Blog Studio

[Blog Studio](skills/blog-studio/SKILL.md) is the main conversational workflow.
It offers six starting paths, optional source intake, reusable voice profiles,
progressive capability loading, and portable article workspaces.

- [Open the interactive preview](http://127.0.0.1:8896/blog-studio.html)
- [Preview file](preview/blog-studio.html) (works directly in a browser)
- [Portable Blog Studio archive](dist/blog-studio.zip)
- [State and helper reference](skills/blog-studio/references/workspace.md)
- [Progressive disclosure roadmap and token estimates](docs/progressive-disclosure-roadmap.md)

The preview lets you choose a path, source input, and voice, then copy a request
into chat. It does not itself read URLs, upload files, or call a model. The actual
skill runs in the host conversation and accepts its attachments/tools.
The prompt generator is an optional starting aid for newcomers; direct chat
uses the same workflow. The project directory is
`/Users/dbbaskette/Projects/blog-studio`.

To try it now, ask your assistant to use the skill at the absolute path to
`skills/blog-studio/SKILL.md`. For automatic discovery, copy the complete
`blog-studio` folder into your selected skill root (project `.agents/skills/`
or `~/.codex/skills/`). Global installation has not been performed. The archive
contains one self-contained skill folder with fourteen capability modules,
source references, provenance, and dependency-free Python helpers.

Saved author and article data lives outside the installed package. The default
is `.blog-studio` in the active content project, unless another workspace is
selected. Profiles are versioned; articles pin a voice revision. Originals and
prior drafts are preserved, and review freshness is recomputed from actual inputs.
No real author profile or article has been fabricated for this implementation.

Validate with `python3 -m unittest discover -s tests -v` and
`python3 skills/blog-studio/scripts/validate_package.py`. Rebuild the archive
with `python3 scripts/package_blog_studio.py`. To serve the preview again, run
`python3 -m http.server 8896 --bind 127.0.0.1 --directory preview` from this
project. No third-party packages or external service accounts are required.

---

# Blog writing skill package

The five entries in [the shortlist](blog-writing-skill-shortlist.md) are collected
in [blog-writing-toolkit](skills/blog-writing-toolkit/SKILL.md). The portable
archive is [dist/blog-writing-toolkit.zip](dist/blog-writing-toolkit.zip).

The toolkit has one skill entry point, five focused module wrappers, and
unchanged upstream source snapshots with supporting references, templates,
evaluation fixtures, licenses, and commit/hash records. Read the entry point,
then the relevant module, then only the supporting files needed for that task.

A higher-level skill can call a module by reading
`<toolkit-root>/references/modules/<module>.md` with the user's brief, voice,
sources, and output requirements. The module IDs are `content-strategy`,
`blog-write`, `copywriting`, `copy-editing`, and `blog` (lifecycle reference).

For example, use `blog-write` for a researched article and `copy-editing` for a
polish request. Planning and persuasive copy are separate optional stages.
See [package notes](skills/blog-writing-toolkit/references/package-notes.md)
for source path mappings, parent handoffs, and omitted runtime dependencies.

## Use or install

The package is stored locally in this project; it has not been installed
into the global skills directory. A parent can read the local entry point or
module paths immediately. For normal discovery, copy the complete
`blog-writing-toolkit` folder into your chosen skill root, such as a project's
`.agents/skills/` or `~/.codex/skills/`. The zip expands to that single folder.
Install the whole folder so references and provenance remain together.

## Validate and package

Run `python3 skills/blog-writing-toolkit/scripts/validate_package.py` from this
project. Source snapshots are pinned to the commits in
[sources.lock.json](skills/blog-writing-toolkit/sources.lock.json); updating
requires an intentional source refresh and archive rebuild.

The archive contains only the toolkit, without the rest of either upstream
repository. Their external runtimes were not installed or executed. The
bundled upstream claims and examples need ordinary fact checking before use.
