# README illustrations

The suite and four studio READMEs use a matching set of lightweight SVG workflow
illustrations. They are diagrams, not screenshots or samples of generated work.
Each README supplies descriptive alternative text and explains the workflow in prose.

The illustrations follow the shared identity colours: Marketing Studio and Blog
Studio blue, Presentation Studio orange, Training Studio violet, Infographic Studio
teal. Reading surfaces are opaque. System-font fallbacks keep text independent of
remote fonts; the SVGs contain no scripts, remote assets or embedded image data.

## Rebuild

From the repository root, with Python 3.11 or newer:

```sh
python3 scripts/readme_graphics.py
python3 scripts/readme_graphics.py --check
```

Edit the product descriptions, workflow labels or drawing functions in that script,
then regenerate and commit the SVGs with their source. Generation is deterministic
and uses only Python's standard library. Check returns nonzero for missing or
outdated graphics without changing files. No image provider or application starts.

| Product | Asset |
| --- | --- |
| Marketing Studio | [Suite header](marketing-studio-header.svg) |
| Marketing Studio | [The route every studio follows](marketing-studio-roadmap.svg) |
| Blog Studio | [Blog Studio header](../../studios/blog/docs/assets/blog-studio-header.svg) |
| Presentation Studio | [Presentation Studio header](../../studios/presentation/docs/assets/presentation-studio-header.svg) |
| Training Studio | [Training Studio header](../../studios/training/docs/assets/training-studio-header.svg) |
| Infographic Studio | [Infographic Studio header](../../studios/infographic/docs/assets/infographic-studio-header.svg) |

## Workflow diagrams

Each studio's docs also show its workflow as a flowchart: the steps in order, where
you decide, and where a step loops back. Filled boxes in the studio's identity colour
are your decisions or input, tinted boxes are assistant work and grey boxes are studio
steps; each diagram carries this legend. Box titles are the studio's own button and
screen names, or say plainly what a step does. Each diagram embeds its own light and
dark colours from the shared tokens and sits on an opaque page, so it reads on either
background when shown through a Markdown image.

```sh
python3 scripts/workflow_diagrams.py
python3 scripts/workflow_diagrams.py --check
```

Edit the steps in that script and regenerate. Building stops if a box would overlap
another, a line would cross a box or a label would not fit. Check returns nonzero for
missing or outdated diagrams; `tests/test_readme_graphics.py` runs both checks with
the root suite. Draw what a studio does now: saved work that keeps an older flow is
mentioned in the prose beside the diagram, not drawn.

| Studio | Diagram | Shown in |
| --- | --- | --- |
| Blog Studio | [Start and write](../../studios/blog/docs/assets/blog-studio-workflow-write.svg) | [Blog Studio README](../../studios/blog/README.md) |
| Blog Studio | [Finish and send](../../studios/blog/docs/assets/blog-studio-workflow-finish.svg) | [Blog Studio README](../../studios/blog/README.md) |
| Blog Studio | [GEO report for a published post](../../studios/blog/docs/assets/blog-studio-workflow-geo-report.svg) | [Blog Studio README](../../studios/blog/README.md) |
| Presentation Studio | [Start and slide text](../../studios/presentation/docs/assets/presentation-studio-workflow-text.svg) | [Presentation Studio README](../../studios/presentation/README.md) |
| Presentation Studio | [Design, refine and deliver](../../studios/presentation/docs/assets/presentation-studio-workflow-deck.svg) | [Presentation Studio README](../../studios/presentation/README.md) |
| Training Studio | [Plan](../../studios/training/docs/assets/training-studio-workflow-plan.svg) | [Training Studio README](../../studios/training/README.md) |
| Training Studio | [Build and finish](../../studios/training/docs/assets/training-studio-workflow-build.svg) | [Training Studio README](../../studios/training/README.md) |
| Infographic Studio | [Story and build](../../studios/infographic/docs/assets/infographic-studio-workflow-story.svg) | [Infographic Studio README](../../studios/infographic/README.md) |
| Infographic Studio | [Review, approve and prepare](../../studios/infographic/docs/assets/infographic-studio-workflow-approve.svg) | [Infographic Studio README](../../studios/infographic/README.md) |

Previously generated PNG headers and their prompt notes remain historical assets.
The Blog Studio editorial-desk screenshots illustrate their linked older guide;
they are not used as current README screenshots. Do not replace a real screenshot
with a diagram and label it as the running application.
