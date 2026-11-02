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
| Blog Studio | [Blog Studio header](../../studios/blog/docs/assets/blog-studio-header.svg) |
| Presentation Studio | [Presentation Studio header](../../studios/presentation/docs/assets/presentation-studio-header.svg) |
| Training Studio | [Training Studio header](../../studios/training/docs/assets/training-studio-header.svg) |
| Infographic Studio | [Infographic Studio header](../../studios/infographic/docs/assets/infographic-studio-header.svg) |

Previously generated PNG headers and their prompt notes remain historical assets.
The Blog Studio editorial-desk screenshots illustrate their linked older guide;
they are not used as current README screenshots. Do not replace a real screenshot
with a diagram and label it as the running application.
