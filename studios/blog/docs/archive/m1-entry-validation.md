# M1 entry refinement — October 1, 2026

M1 is implemented locally for [issue #4](https://github.com/dbbaskette/blog-studio/issues/4). The parent is now a loading map: the current operation selects a required module, while intake, voice setup, continuity, hub, composition, review, and export references have explicit conditions. Startup choices and stop rules live in one short entry flow. The bootstrap keeps guidance freshness, exact resume pins, installed-runtime selection, and explicit cached fallback separate from writing intake.

## Measured instruction footprint

Estimates use each file's Unicode characters divided by four, rounded up. They include frontmatter and are not tokenizer counts, provider billing, or a measurement of conversation history.

| Guidance | Before | After |
| --- | ---: | ---: |
| Repository parent | 1,501 | 787 |
| Entry flow | 828 | 408 |
| Parent + entry | 2,329 | 1,195 |
| Installed bootstrap, separate | 1,018 | 857 |
| Complete offline instruction library | 168,311 | 167,177 |

Parent + entry meets M1's approximately 800–1,200-token target and is 49% smaller. The corpus still has 85 instruction files. Runtime helpers, upstream bytes/locks/licenses, and craft/workspace guides are unchanged. M2–M4 reductions remain separate work. Run `python3 scripts/measure_guidance.py` to refresh the inventory and `--check` to detect stale measurements; CI also checks it.

## Outline-only smoke in the current Codex session

This was a controlled in-session smoke using the working-tree offline entry, not a clean installation or an independently discovered skill. The session read the entry, entry flow, selected source intake, argument-outline module, and workspace guidance. It used disposable local files and synthetic notes; no research, account access, private team material, or remote hub was involved.

Request:

> Build an outline for team leads from these notes. Use a direct conversational tone, supplied material only, and stop at the outline.

The notes proposed recording an owner, current decision, next action, and supporting note in team handoffs, then sampling notes weekly for omissions. They supplied no measured improvement or real customer example.

The session inferred outline-only, reused supplied notes and tone without another starting menu, authored a three-part plan (missing context → proposed fields → check omissions), and marked the absent quantified evidence. It saved the original source, brief, and outline through `studio.py`, updated the checkpoint, then reopened the saved article. Readback confirmed the selected source, `stop_point: outline`, no pending question, the exact saved outline, and no `DRAFT.md`. No durable voice profile was created for a tone-only choice.

Disposable artifacts were retained under `/tmp/blog-studio-m1-smoke-4q8tmbv7/`; they are not bundled or committed. This smoke supports the direct outline path and local stop/readback behavior. It does not establish independent conversational quality, installed discovery, or Claude Code parity; those remain M5/I4 pilots.

## Newcomer request compatibility

The unchanged prompt generator's actual inline script was executed with a minimal DOM stub in Node. All six route requests retained their intended stop points and supplied tone. An outline attachment request retained “Please wait for it”; a voice-learning request retained selected LinkedIn background and authored samples. The current outline smoke and generated outline request specify the same route and stop. This checks generated text, not browser clicks, upload behavior, or a full six-route conversational pilot.

## Package and helper verification

Final rebuilt packages passed **all 87 tests** in 56.226 seconds. Both maintained entries passed the skill frontmatter validator; package/source validators, installer launcher syntax, and reproducible token-inventory checks passed. Existing route/stop, source roles, voice/guidance pins, review freshness, private-content boundaries, installer/update/rollback, Team Hub, and extracted-bundle checks cover the unchanged helpers. Immutable source hashes, maintained reference links, entry frontmatter, archive checksums, and reproducible token inventory are checked separately.
