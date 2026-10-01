![Blog Studio — Your ideas. Your voice.](docs/assets/blog-studio-banner.svg)

# Blog Studio

**A writing partner inside your own Codex or Claude harness.**

Bring a rough idea, a stack of notes, or a blog you've already written. Blog Studio helps you find the next useful step, uses your voice, and loads the writing guidance that step needs.

**6 starting paths · 14 capability modules · Reusable voices · Resumable work**

[Get started](#get-started) · [Progressive disclosure](#how-progressive-disclosure-works) · [Roadmap and token estimates](docs/progressive-disclosure-roadmap.md) · [Download the skill](dist/blog-studio.zip)

## Start where you are

| What you have in mind | What Blog Studio helps you do |
|---|---|
| **Help with my draft** | Get feedback or a focused revision while preserving your original |
| **Write the first draft** | Turn a topic, audience, and angle into a coherent article |
| **Build an outline** | Develop the argument and section progression, then stop at the outline |
| **Write from my outline** | Expand your structure into a complete draft |
| **Interview me** | Draw out your experience through one focused question at a time |
| **Help me find an idea** | Explore your audience, interests, and the point worth making |

You can attach source content, paste notes, share links, reuse saved material, or start without it. Voice setup is available on its own: share authored writing, LinkedIn background, or a description of how you want to sound.

## How progressive disclosure works

The **parent skill** holds the brief, selected sources, voice, and requested outcome. It opens a capability when the current task needs it, then follows the relevant references within that capability.

```mermaid
flowchart TD
    P[Blog Studio parent skill]
    P -->|Material supplied| S[Source intake]
    P -->|Voice setup needed| V[Voice profile]
    P -->|Current writing task| W[Discover · interview · outline · draft · edit]
    P -->|Review requested| R[Selected editorial checks]
    P -->|Next format requested| F[Repurpose · export]
```

| Stage | What appears in chat | Guidance loaded when needed |
|---|---|---|
| **Start** | The right starting choices, or immediate work on a clear request | Parent and entry flow |
| **Material** | Attachments, notes, links, or selected saved sources | Intake and source organization |
| **Voice** | Saved profile, learn my voice, requested tone, or preserve this draft | Voice setup and selected profile |
| **Write** | The next question, outline, draft, or revision | The current writing capability |
| **Review** | Specific findings and proposed changes | Requested voice, factual-support, structure, humanization, or GEO checks |
| **Finish** | The requested artifact and optional next step | Export or repurposing guidance |

These stages adapt to your request. A clear draft request can continue through an internal outline; outline-only stops at the outline. A quick edit gets a focused review. Existing context is reused instead of asking you to repeat setup.

**The workflow stays in chat.** The optional [newcomer prompt generator](preview/blog-studio.html) helps you choose a starting request to paste into your harness. It doesn't generate the article or store your writing.

## Token footprint

Progressive disclosure keeps the full reference library available while selecting guidance for the current operation. The library contains approximately **162.8k estimated tokens**; a normal route reads a subset.

| Route | Current guidance estimate | Target after roadmap |
|---|---:|---:|
| Outline with sources | 4.9k | 2–3k |
| First draft with sources | 11.4k | 3–5k |
| Quick edit | 8.6k | 2.5–4k |
| Voice setup | 5.5k | 2–3.5k |
| Comprehensive review | 10.8k | 4–6k |

Estimates use characters ÷ 4 and count each selected instruction file once. They include workspace guidance and exclude author material, generated prose, conversation history, and host/tool context. They are planning estimates rather than total billed usage. Targets are **planned refinements**, and already loaded text can remain in the conversation.

See the [full roadmap](docs/progressive-disclosure-roadmap.md) for file-level estimates, assumptions, source/output allowances, and acceptance criteria.

## Work that carries forward

- **Your voice:** reusable profiles, auditions, explicit preferences, and a pinned revision for each article.
- **Your sources:** original files, readable text, provenance, and separate roles for evidence, inspiration, background, and authored samples.
- **Your manuscript:** an untouched original, saved outlines and drafts, version history, and a checkpoint for resuming.
- **Your reviews:** findings tied to the draft, voice, and evidence they checked, with clear current, stale, failed, unavailable, or not-run status.

The default local `.blog-studio/` data workspace is excluded from Git. Saved work can be reopened by path in another chat; the local files provide continuity.

## Get started

**From this repository:** open it in your harness and ask:

> Use `skills/blog-studio/SKILL.md` to help me start a blog. Show me the relevant starting choices and source and voice options.

Or start with a concrete outcome:

> Use `skills/blog-studio/SKILL.md` to build an outline from my attached notes. Keep it conversational and stop at the outline.

**For skill discovery:** expand [blog-studio.zip](dist/blog-studio.zip) and copy the complete `blog-studio` folder into your harness's skill directory. Keep its references and helpers together. See [setup and package details](PACKAGE.md) for locations and local usage.

**For the newcomer prompt generator:** open [preview/blog-studio.html](preview/blog-studio.html) locally, or serve it with:

```sh
python3 -m http.server 8896 --bind 127.0.0.1 --directory preview
```

Then visit `http://127.0.0.1:8896/blog-studio.html`.

## What's implemented and what's next

The six routes, fourteen capability modules, local continuity helpers, and portable packages are implemented. **15 deterministic tests passed**, along with package validation and portability checks. Conversational quality and route selection still need a representative harness pilot.

| Next milestone | Estimated development tokens |
|---|---:|
| Smaller entry skill and explicit loading map | 8–15k |
| Focused workspace and continuity reads | 12–20k |
| Concise writing, editing, strategy, and title guides | 20–35k |
| Scoped reviews and selected evidence reads | 10–18k |
| All-route harness pilot and newcomer handoff | 12–22k |
| **Total remaining estimate** | **62–110k** |

Development estimates cover implementation and verification work. They are separate from the runtime guidance estimates above. Details and dependencies live in the [roadmap](docs/progressive-disclosure-roadmap.md).

## Verify and package

```sh
python3 -m unittest discover -s tests -v
python3 skills/blog-studio/scripts/validate_package.py
python3 scripts/package_blog_studio.py
```

Portable ZIPs and checksums are in [dist](dist/). The original five-skill collection remains available as [blog-writing-toolkit](skills/blog-writing-toolkit/SKILL.md).

Upstream sources retain their licenses and pinned provenance. See [package notes](skills/blog-studio/references/package-notes.md), [source lock](skills/blog-studio/sources.lock.json), and [BlogForge asset lock](skills/blog-studio/blogforge.lock.json).
