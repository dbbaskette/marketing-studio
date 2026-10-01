# Blog Studio

A portable skill for writing blogs inside Codex or Claude. Start with a manuscript, topic, outline, source material, or author interview, then load the relevant writing and review capabilities as needed.

- Six starting paths and fourteen capability modules
- Source attachments, pasted notes, and URLs through the host harness
- Reusable author voice profiles with pinned revisions
- Local article workspaces, version history, and review freshness
- Optional newcomer prompt generator

Read [setup and package details](PACKAGE.md), the [main skill](skills/blog-studio/SKILL.md), and the [progressive disclosure roadmap with token estimates](docs/progressive-disclosure-roadmap.md).

The packaged skills and local helpers are implemented. Fifteen deterministic tests passed, along with package validation and portability checks. The roadmap describes remaining guidance refinements and conversational pilot validation.

Author data belongs outside the installed skill. The default local `.blog-studio/` workspace is excluded from Git.

## Verify

```sh
python3 -m unittest discover -s tests -v
python3 skills/blog-studio/scripts/validate_package.py
```

## Package

```sh
python3 scripts/package_blog_studio.py
```

Portable ZIPs and checksums are in [dist](dist/). Upstream sources retain their licenses and provenance; see the skill's package notes and lock files.
