# Package notes and source mapping

This package collects the five source skills listed in
`blog-writing-skill-shortlist.md` on October 1, 2026. Both upstream repositories
use MIT licenses, retained next to their snapshots:

- [claude-blog license](upstream/claude-blog/LICENSE)
- [marketingskills license](upstream/marketingskills/LICENSE)

The original skill documents are copied byte-for-byte as `SOURCE.md`; only their
filename changes. Their supporting reference, template, and evaluation files
are retained in the original directory layout. Renaming avoids presenting
archival source documents as additional installed skill entry points. The thin
module wrappers are the intended interfaces. Originals remain available for
comparison or later synthesis; their runtime instructions are not automatically
adopted by this package.

## Path resolution

For a path in a claude-blog source beginning `skills/` or `data/`, prefix it with
`references/upstream/claude-blog/` from the package root. For marketingskills,
prefix repository-root paths with `references/upstream/marketingskills/`.
Replace terminal `SKILL.md` with `SOURCE.md` for the five collected source skills.
A source-relative link such as `references/checklist.md` resolves relative to
that source document's directory. Never resolve upstream paths from the user's
working directory or assume a `~/.claude` installation exists.

## Runtime boundaries

The two claude-blog skill folders, their 22 shared blog references, 12 templates,
writer delivery reference, and `data/google-updates.json` are collected. The
three marketingskills folders include their seven references and upstream
evaluation fixtures. No upstream scripts, installers, agent definitions,
credentials, or additional skills are installed or executed.

The lock manifest lists omitted explicit path dependencies per source. This
includes the upstream delivery/rendering helpers, reviewer/researcher agents,
FLOW source references, and additional blog skills. Named related marketing
skills (SEO audits, CRO, social, email, offers, launch, and others) are also
outside this shortlist. Ordinary planning, drafting, and editing use the module
wrappers and available host tools. A request for the complete upstream runtime
requires separately collecting its actual dependencies and checking host
compatibility; do not silently install it or claim its gates passed.

The FLOW alignment reference attributes FLOW to AgriciDaniel under CC BY 4.0.
The underlying FLOW framework and prompts are omitted. Preserve that attribution
if reusing the alignment; obtain the original source and applicable attribution
before quoting the framework. The update ledger and dated optimization claims
are source snapshots, not live evidence.

## Parent handoff example

A higher-level skill can state:

> Resolve `<toolkit-root>` to the installed `blog-writing-toolkit` folder. For
> an existing draft that needs polishing, read
> `<toolkit-root>/references/modules/copy-editing.md`, supply the draft and voice
> instructions, and use its guidance. Load only its relevant supporting files.
> Return the revision and material change notes to this workflow.

An end-to-end blog workflow loads `content-strategy` if planning is needed,
`blog-write` for article creation, and `copy-editing` for revision as each stage
begins. The parent retains the user's context and controls further actions.

## Verification and updating

Run `python3 scripts/validate_package.py` from this folder, or invoke that script
by absolute path. It checks the five module routes, source checksums, licenses,
a single active skill entry point, and local links in the authored wrappers.
Use the Codex skill-creator validator for entry-point frontmatter as well.
These checks establish package integrity, not the truth of upstream editorial
claims or the operability of the omitted upstream runtime.

To refresh, fetch a deliberate upstream commit, replace the selected source
folders, review module compatibility, regenerate source hashes and dependency
records, validate, and rebuild the archive. Do not mix files from unrecorded
commits. The lock file is maintained provenance metadata, not a tamper-proof
signature.
