# Cult UI source adaptations

Marketing Studio adapts selected MIT-licensed Cult UI source to its existing DOM,
CSS and Golden Gate 2.1 system. These are source ports, not a React package installation.
There is no frontend build step, new runtime dependency, CDN request or provider work.

Upstream: [nolly-studio/cult-ui](https://github.com/nolly-studio/cult-ui), pinned at
`d71b1428b811c2779d46ea41b7ef8c9f9c9991c2`.

| Upstream component | Used in | Adaptation |
| --- | --- | --- |
| [Direction Aware Tabs](https://github.com/nolly-studio/cult-ui/blob/d71b1428b811c2779d46ea41b7ef8c9f9c9991c2/apps/www/registry/default/ui/direction-aware-tabs.tsx) | Training Studio slide tasks, Presentation Studio Slides/Outline, Blog Studio manuscript views | Shared moving selection pill; 400 ms transition. Training Studio content enters from the selected direction and its inputs stay mounted. Other desks retain their existing save and repaint behavior. |
| [Toolbar Expandable](https://github.com/nolly-studio/cult-ui/blob/d71b1428b811c2779d46ea41b7ef8c9f9c9991c2/apps/www/registry/default/ui/toolbar-expandable.tsx) | Training Studio workflow, Blog Studio phone tools, Infographic Studio brief/source/layout panels | Rounded shell, numbered stage rail and 250 ms native height transition. Uses native disclosure semantics and scrolling. |
| [Minimal Card](https://github.com/nolly-studio/cult-ui/blob/d71b1428b811c2779d46ea41b7ef8c9f9c9991c2/apps/www/registry/default/ui/minimal-card.tsx) | Marketing Studio launcher | Layered card frame, rounded surfaces and hover/focus emphasis using existing studio colors. |

## Intentional differences

React state becomes existing studio selection state. CSS replaces the shared-layout
pill and expandable height animation; the Web Animations API handles directional
content motion. Native scrolling replaces Radix Scroll Area. Existing ARIA labels,
keyboard handling, validation, permission checks and explicit save/start/send actions
remain authoritative.

The content offset is 24 px rather than upstream's 300 px, and text is not blurred.
Rapid selections interrupt motion rather than disabling controls. Background polls
do not replay transitions. Reduced motion removes movement. Browsers without native
auto-height transitions still open and close the disclosure immediately.

Reading and editing surfaces stay opaque. The shared Golden Gate color tokens replace
upstream neutral colors. Component helpers live in `ui-kit/drafting.js`; scoped styles
live in `ui-kit/style.css`. Both retain the upstream copyright and MIT permission text.

## Verification

Use the affected studio UI module suites, and look at the changed screens at phone and
desktop width over a disposable fixture. Check retained input, rapid selection, focus, no jobs from navigation, reduced motion,
light/dark appearance and page overflow. Reuse the full Training Studio suite recorded in
[the workflow plan](../superpowers/plans/2026-11-07-cult-ui-workflows.md) for unchanged runtime code.

The Tart wrapper `scripts/ci/guest-cult-source-ui.sh` runs the shared intake and
consistency suites. It no longer drives the five surfaces in a browser.
