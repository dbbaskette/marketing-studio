# Blog Studio packages

The recommended [guided installer ZIP](dist/blog-studio-installer.zip) installs a small stable [bootstrap](bootstrap/blog-studio/SKILL.md) plus versioned Python helpers. The [installation guide](docs/installation.md) covers Mac setup, private GitHub access, target locations, update, repair, rollback, and removal.

The bootstrap quietly fetches approved `main` when a new writing task starts. It materializes `skills/blog-studio/SKILL.md`, its references, and provenance records from that exact revision into the author's task cache. Runtime scripts from the repository are excluded from the readable guidance snapshot and are never executed. The assistant reads relevant files progressively; downloads stay outside model context.

`skills/blog-studio/` remains the single maintained operational guidance source, including fourteen capability modules and pinned upstream references. The compatibility manifest is [guidance/manifest.json](guidance/manifest.json). Bootstrap/runtime changes require a new managed bundle; guidance-only changes need no reinstall. The installer builder copies the continuity helpers and the three Team Hub modules from the full package and records file hashes in the bootstrap manifest.

Codex uses `~/.agents/skills/blog-studio`; Claude Code uses `~/.claude/skills/blog-studio` (or its configured root). Both link to one managed local runtime. User writing lives separately, by default in `.blog-studio` under the active writing project. Articles record guidance pins and runtime paths, originals, draft history, voice revisions, and review freshness. Adopting a new guidance revision makes affected reviews stale.

Runtime **1.1.0** includes `hub.py`, `hub_store.py`, and `hub_workspace.py`. Shared working content belongs in a separate private Team Hub repo; local projection maps, queues, and caches never enter either skill distribution. The new guidance manifest requires 1.1.0; old runtime versions remain available for installer rollback with compatible historical guidance. See [Team Hub](docs/team-hub.md).

The separate [full offline ZIP](dist/blog-studio.zip) expands to a complete self-contained `blog-studio` skill. Copy that whole folder into a supported skill root for manual/offline use. It does not refresh automatically. Avoid installing the managed and manual parents with the same name at once.

The optional [prompt generator](preview/blog-studio.html) forms starting requests for newcomers; direct chat uses the same writing workflow. It does not upload content, fetch URLs, or generate articles.

```sh
python3 -m unittest discover -s tests -v
python3 skills/blog-studio/scripts/validate_package.py
python3 scripts/package_blog_studio.py
python3 scripts/package_installer.py
```

Builds include ZIP checksums. Local hashes detect package changes; authenticity still depends on obtaining the bundle from the trusted private repository. Automated tests use disposable homes and local repositories, not production skill folders or Google documents. No global installation or dependency installation was performed by this implementation.

See [progressive disclosure and token estimates](docs/progressive-disclosure-roadmap.md), [setup help](docs/troubleshooting.md), and [Google Docs next steps](docs/google-docs-roadmap.md).

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
