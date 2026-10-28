# Infographic Studio provider feasibility

This milestone defines the execution handoffs; it does not claim that any account
has successfully generated or edited an image. CLI help/feature discovery and
scripted tests incur no provider work. Manual live acceptance remains separate.

## Supported configurations

| Configuration | Generation/editing | Inspecting the actual result |
| --- | --- | --- |
| Codex | Native image job with `image_generation` enabled, prompt on stdin, optional staged `--image` references; collect the returned image events and copy validated files into the owned attempt | Separate image-input job with returned assets attached through `--image`; do not enable shell/browser access to read them |
| Claude Code with Gemini API | Claude Code authors the complete image brief; a server-side standard-library HTTPS adapter sends it and selected reference bytes to an image-capable Gemini model | Restricted Claude Code job in a disposable job folder with only the built-in `Read` tool and an explicitly empty MCP configuration; prompt names the staged returned image and scene |

The compatibility baselines inspected for this milestone are Codex CLI 0.162.1
and Claude Code 2.1.303. These are tested command-surface baselines, not claims
that older versions cannot work. Neither executable presence nor a feature flag
proves account access, image editing, multimodal inspection, or output quality.

The existing shared Codex worker keeps `image_generation` disabled. The proposed
native command keeps its other capabilities disabled and permits only the image
tool. Production collection, capability attestation, timeouts, and cancellation
belong to the image-adapter issues. Do not execute these proposals as a provider
test during automated verification.

Claude Code inspection runs with `--restricted --tools Read --allowedTools Read`,
strict empty MCP configuration, no permission prompts, no persistent session,
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

Official capability descriptions support the proposed surfaces. The installed
command help establishes flag availability; only explicit future live acceptance
can establish generation/edit/inspection behavior for a particular account.
