# Infographic Studio provider feasibility

The first-release candidate implements the execution handoffs; it does not claim that any account
has successfully generated or edited an image. CLI help/feature discovery and
scripted tests incur no provider work. Manual live acceptance remains separate.

## Supported configurations

| Configuration | Generation/editing | Inspecting the actual result |
| --- | --- | --- |
| Codex | Native image job with `image_generation` enabled, prompt on stdin, optional staged `--image` references; collect actual regular PNG files from the owned `generated_images/` folder | Separate image-input job with returned assets attached through `--image`; do not enable shell/browser access to read them |
| Claude Code with Gemini API | Claude Code authors the complete image brief; a server-side standard-library HTTPS adapter sends it and selected reference bytes to an image-capable Gemini model | Restricted Claude Code job in a disposable job folder with only the built-in `Read` tool and an explicitly empty MCP configuration; prompt names the staged returned image and scene |

The compatibility baselines inspected for this milestone are Codex CLI 0.162.1
and Claude Code 2.1.303. These are tested command-surface baselines, not claims
that older versions cannot work. Neither executable presence nor a feature flag
proves account access, image editing, multimodal inspection, or output quality.

The existing shared Codex worker keeps `image_generation` disabled. The native
image command keeps its other capabilities disabled and permits only the image
tool. Owned-file collection, durable intent, bounded timeouts and scoped
cancellation are implemented and covered with injected workers. Account access
and provider behavior still require separate live acceptance.

Claude Code inspection runs with restricted mode, only the Read tool and allowed
Read patterns scoped to the staged PNG names, strict empty MCP configuration,
no inherited setting sources, no permission prompts, no persistent session,
and a working directory containing only staged inputs. Managed policy and model
access can still refuse image reading. That is an incomplete visual check requiring
manual review, never a successful inspection inferred from a textual response.

Gemini generation/editing uses a configured image-capable model and an API key
read only by the server-side image adapter. The request carries the self-contained
brief and optional reference-image bytes. Preserve returned image bytes, MIME
type, request identity when available, and reported/unknown usage. Neither a key
nor a model name establishes access. No Gemini key reaches either assistant,
renderer, settings, prompts, logs, or browser response.

## Non-secret capability contract

`runner/provider_capabilities.py` separates missing assistant, sign-in required,
missing Gemini key, unavailable Codex image tool, inaccessible Gemini image model,
and unavailable inspection. Unknown observations remain unknown; local discovery
never upgrades a report to live verified. Readiness does not silently choose a
different provider or an OpenAI API-key fallback.

## Explicit manual acceptance, after implementation

1. Use a disposable workspace and synthetic inputs. Select one supported setup.
2. Generate an image from a pinned detailed brief. Capture actual returned bytes
   and owned request identity rather than trusting a success message.
3. Inspect that file and a composed page. Include a known required object and a
   deliberately mismatched relationship in separate fixtures; verify findings.
4. Request one exact edit referencing the original asset; inspect what changed
   and what was preserved. Save both revisions and reported/unknown usage.
5. Repeat for the other supported setup. Record runtime/model versions and
   sanitized conclusions. Leave capability unverified if a step cannot be run.

Real generation is not part of this milestone's automated checks, and no personal
credential or operational transcript belongs in this repository.

## Primary references

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex image generation](https://learn.chatgpt.com/docs/image-generation)
- [Codex image inputs](https://learn.chatgpt.com/docs/image-inputs)
- [Claude Code programmatic sessions](https://code.claude.com/docs/en/headless)
- [Gemini image generation and editing](https://ai.google.dev/gemini-api/docs/image-generation)

Official capability descriptions support these surfaces. The installed
command help establishes flag availability; only explicit future live acceptance
can establish generation/edit/inspection behavior for a particular account.

## First-release adapter contracts

The native implementation now exposes scoped generation, reference editing,
actual-pixel inspection, durable intents and recovery. Those implementations and
injected tests do not change the live acceptance status above.

The Gemini adapter follows the current documented [image generation interface](https://ai.google.dev/gemini-api/docs/image-generation)
and [Interactions API](https://ai.google.dev/api/interactions-api): fixed HTTPS host,
PNG/2K portrait image response, explicit model, no tools/search, `store:false`, staged
inline references, completed model-output image bytes and reported token usage.
Unsupported model options fail visibly; there is no protocol/provider downgrade or
uncertain-request retry. Credentials occur only in the request header, not the URL,
body, saved project, CLI environment or error text.

The Codex adapter uses the installed built-in image tool and collects actual regular
files in its owned `generated_images/` folder, as implemented by the official
[Codex image-generation extension](https://github.com/openai/codex/blob/main/codex-rs/ext/image-generation/src/tool.rs).
It does not invent an image event type or follow an output path mentioned by a model.
Planning/inspection disable image generation; only the image adapter enables it.

Codex outcomes use the same normalized result as Gemini and are classified only from
the worker's own failure diagnostics (exit status, `stderr` and terminal `turn.failed`
or `error` events), never from the model's prose:

| Observation | State and reason |
| --- | --- |
| A completed turn with one bounded valid PNG in the owned output folder | `complete`, with reported or unknown token usage |
| A completed turn with no saved image, an unknown `image_generation` feature or an unsupported argument | `failed`, `image-tool-unavailable` |
| Not signed in, unauthorized or "please run /login" | `failed`, `sign-in-required` |
| Retried stream `error` events followed by a completed turn | Not a failure; the image is collected as usual. Only an `error` with no later completed turn, or a `turn.failed`, ends the request, here and in local recovery |
| Usage or rate limit, including a `turn.failed` event after an exit status of 0 | `failed`, `quota` |
| A saved file that is not a bounded valid 8-bit PNG | `failed`, `invalid-asset`; nothing is adopted |
| Time limit or cancellation | `unknown`/`timeout` or `cancelled`/`stopped`; never retried |

`tests/test_codex_images.py` drives these from stubbed event streams. They do not
establish that a particular installed Codex or account can generate or edit images.

Claude Code inspection uses only staged PNG files, Read scoped to their names,
restricted mode, no inherited setting sources, empty strict MCP configuration,
no permission prompts/session persistence, and a minimal environment without Gemini
credentials. This follows the official [permissions](https://code.claude.com/docs/en/permissions)
and [CLI reference](https://code.claude.com/docs/en/cli-reference). Other text workers'
tool restrictions are unchanged. A failed multimodal check stays unfulfilled and
can be replaced by the user's explicit review of the actual current page.
