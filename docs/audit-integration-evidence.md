# Audit integration evidence

The audit scope is #297, #305 and #312–#325, tracked by #326. The implementation
landed in eight weekly cohorts, with one suite PR per cohort. Related spending
policy #304 and Infographic Studio first-release acceptance #224 remain separate.

## Observable work saved

| Fixture | Verified behavior | Boundary |
| --- | --- | --- |
| Outline edit | Local save/reload makes no research calls; removing a section excludes it from approved scope | A Quick scan is provisional; the new flow requires outline approval |
| Four-section research with one timeout | Three completed drafts survive; retry authors the remaining section | Final assembled report still needs independent whole-report verification |
| Source change relevant only to section B | Section A's packet/draft survives; B's investigator and combiner run again | Fresh final assembly/check and required dependent outputs remain necessary |
| Explicit unchanged Harness Research save | Matching evidence/context preserves eligible review; changed identities invalidate it | Opt-in contract; ordinary saves keep their revision-based behavior |
| One-slide edit in a 30-slide deck | One changed slide rasterized; slides 14–16 inspected in the middle-slide fixture; 27 compatible inspections reusable | Whole-PDF conversion still occurs; final whole-deck consistency and exact-revision approval remain required |
| Failed infographic preview | Retry invokes no assistant or image operation | Changed revisions reject stale recovery actions |
| Failed artwork placement | Retry places the existing generated asset; one original image generation and art-direction request | Uncertain image requests retain their separate recovery protocol |
| 5,000 saved work folders | Home scans at most 100 folders and returns at most 12 rows per studio; dense compact fixture took about 4 ms | One local macOS/Python 3.14 fixture, not a provider or network latency benchmark; bounded enumeration need not return all workspace items |
| Resting change-impact view | Two polls read selected bytes once; confirmation reads again | External unmanaged edits can remain visually cached for at most 30 seconds; confirmation always revalidates bytes |

The Activity log separates first saved useful result, assistant-active wall time,
recorded checks and person/queue waits. Scripted call counts demonstrate avoided
work. They do not establish live model latency, dollar savings or the proposed
60–90 second outline target. Unknown timing boundaries remain unknown.

## Verification ownership

The integration owner runs the full shared suite, four native suites and disposable
installer/CLI acceptance at the Week 7 boundary, then the final Week 8 browser and
package/guidance matrix. Passing evidence is reused where application code is
unchanged; corrected files receive affected checks. Cohort PRs and plans identify
tested commits and aggregate reruns rather than claiming one uninterrupted pass.

- Week 4: shared 960, Presentation Studio 2,179 and Training Studio 3,173 tests;
  native outline browsers, diagrams, package and installer/CLI checks.
- Week 5: shared 964, Presentation Studio 2,181 and Training Studio 3,175 tests;
  actual Harness Research scoped contracts, browsers and installer/CLI checks.
- Harness Research 1.1.1: canonical full gate, 233 tests, CLI/install/context checks,
  merged and released before the suite pin changed.
- Harness Slides 0.17.0: canonical full gate, 354 tests, browser/render/package and
  installed-workspace build/review checks, merged and released before pinning.
- Week 6: shared/native full-suite evidence plus affected-class compatibility
  corrections, actual-helper contracts, both browsers and installer/CLI acceptance.
- Week 8 browser matrix passed on commit `717bf2807734829be8a9d6742e883bffd3cfb5d1`
  (tree `1bcebcf2f02ded1f7b84ea4795de789f4157c5e5`) on macOS 27.0.1,
  Python 3.14.5 and Node 26.11.1. Four real browser journeys, 14 package/overview
  contracts, both native package/context-budget checks and nine workflow diagrams
  passed. The cohort plan records scope and evidence reuse.

## Appearance and accessibility coverage

The real protected home and native Training Studio, Presentation Studio and
Infographic Studio pages use disposable synthetic workspaces. Checks cover
320/390/1280 CSS-pixel layouts, light/dark, reduced effects, keyboard operation and
200% equivalent layout emulation; home additionally covers 800–1920 px. Native
outline forms preserve typing and caret through polling and save/reload. The
shared affected-work/section-progress surface is tested independently at the same
widths. Selected screenshots receive visual inspection.

The 200% check emulates a halved CSS layout viewport at doubled device scale. It
is not native browser zoom or hardware testing. Screen readers, hardware mobile
keyboards, real provider response time, signed-in Google delivery and multi-member
team workflows are not established by these checks. No test starts a paid job or
uses the person's real workspace. Runtime code remains standard-library Python;
Playwright and Ruff are development-only checks with pinned tools.

Both full shared and Infographic Studio VM suites have an explicit installed-PDF
reader acceptance skip. That unchanged reader path passed separately with a real
installed reader and synthetic PDF in Week 4. All disposable VMs are deleted and
private diagnostic logs stay outside the public repository.
