# Harness Brand Plan 8: Release 1.0.0

**Goal:** Harness Brand 1.0.0 released with the archive Marketing Studio's installer accepts.

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
section 5. Earlier plans: [5](2026-11-03-harness-brand-5-worker.md).

## Steps taken

1. Version set to 1.0.0 and `CHANGELOG.md` added (dbbaskette/harness-brand-skill#9).
2. The release archive built from the merged commit `fc82918` with `node scripts/package.mjs`
   from the files Git tracks: `harness-brand-1.0.0-mac.zip` (50 files under
   `harness-brand/`) and `harness-brand-1.0.0-mac.zip.sha256`
   (`1d0b80ea505144b6d0996ea0d50fc9572af37bb6aa9667f9917f1ccdfed0d688`).
3. Checked from that archive in a throwaway home, as Marketing Studio installs it:
   `install-mac.mjs --yes --research skip` from the unpacked folder, with
   `HARNESS_BRAND_DATA` naming the real packs and the installed Harness Slides 0.16.0. The
   installed copy listed the four brands; every slides contract (five brand and variant
   pairs, live and reading) exported and passed `contract check`; `doctor` reported ready;
   `look samples` built the VMware by Broadcom dark looks; `icons` answered.
4. Tag `v1.0.0` pushed, and the GitHub release published with the archive and its checksum:
   https://github.com/dbbaskette/harness-brand-skill/releases/tag/v1.0.0

## Notes

- The test suite (216) passes on Node 22 and Node 24. Node 20 is not installed on this
  computer; a search of the code found no API newer than Node 20.
- Marketing Studio's pins require brand skill 0.14.0 or newer, so 1.0.0 needs no pin change.
- The person switches to Harness Brand by setting the brand skill's repository in Settings
  to `https://github.com/dbbaskette/harness-brand-skill`; no one's settings were changed.
