# Local rendering measurement — 2026-11-04

Resolves investigation #346. Harness Slides 0.17.0 (`fecfe2b63de0620e6c5cbad841d11cf37ecf3d61`), macOS ARM64 27.0, Node 26.11.1, installed LibreOffice and Poppler. Synthetic diagrams, no selected brand, providers or Google. Three independent scratch/cache trials per deck size; scenarios within each trial run sequentially. Each conversion uses its own LibreOffice profile.

All values below are milliseconds, p50 / maximum observed (nearest-rank p95 with only three samples). This sample is too small to estimate a stable production tail. The neighbor case adds a second changed slide after the one-slide case; its first changed slide is already cached. Cache verification and inspection are additional file/digest probes; inspection verifies evidence files and makes no visual judgment.

| Slides | Scenario | Compile | Conversion | Raster | Cache verify | Inspection verify | First raster | Usable preview |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | cold | 28 / 55 | 1206 / 1382 | 448 / 473 | 3 / 4 | 1 / 1 | 1703 / 2214 | 2335 / 2885 |
| 6 | unchanged | 0 / 0 | 0 / 0 | 0 / 0 | 3 / 3 | 1 / 1 | cache at return | 246 / 248 |
| 6 | one-slide | 18 / 19 | 1064 / 1141 | 75 / 76 | 3 / 3 | 1 / 1 | 1522 / 1622 | 1772 / 1869 |
| 6 | neighbor | 17 / 18 | 1092 / 1138 | 73 / 76 | 3 / 3 | 1 / 1 | 1551 / 1615 | 1796 / 1864 |
| 6 | global-style | 16 / 23 | 1124 / 1220 | 448 / 458 | 3 / 3 | 1 / 1 | 1601 / 1704 | 2229 / 2341 |
| 6 | font | 3 / 4 | 1130 / 1153 | 449 / 486 | 3 / 4 | 1 / 1 | 1618 / 1624 | 2227 / 2302 |
| 6 | final-export | 0 / 0 | 1146 / 1178 | 443 / 459 | 3 / 4 | 1 / 1 | 1608 / 1676 | 2203 / 2297 |
| 30 | cold | 35 / 39 | 1119 / 1123 | 2230 / 2233 | 6 / 6 | 2 / 2 | 1616 / 1617 | 4937 / 4949 |
| 30 | unchanged | 0 / 0 | 0 / 0 | 0 / 0 | 5 / 6 | 2 / 2 | cache at return | 255 / 257 |
| 30 | one-slide | 35 / 37 | 1136 / 1142 | 76 / 81 | 6 / 6 | 2 / 2 | 1656 / 1664 | 2822 / 2840 |
| 30 | neighbor | 33 / 36 | 1127 / 1176 | 77 / 78 | 6 / 6 | 2 / 2 | 1640 / 1697 | 2806 / 2880 |
| 30 | global-style | 34 / 36 | 1132 / 1202 | 2241 / 2314 | 6 / 6 | 2 / 2 | 1641 / 1697 | 4986 / 5057 |
| 30 | font | 4 / 4 | 1176 / 1183 | 2254 / 2256 | 6 / 7 | 2 / 2 | 1663 / 1663 | 4980 / 4981 |
| 30 | final-export | 0 / 0 | 1112 / 1154 | 2240 / 2270 | 6 / 6 | 2 / 2 | 1592 / 1641 | 4891 / 4980 |
| 100 | cold | 60 / 75 | 1267 / 1273 | 7524 / 7559 | 14 / 14 | 7 / 7 | 1873 / 1888 | 13163 / 13213 |
| 100 | unchanged | 0 / 0 | 0 / 0 | 0 / 0 | 13 / 14 | 7 / 8 | cache at return | 289 / 291 |
| 100 | one-slide | 57 / 57 | 1267 / 1272 | 77 / 77 | 16 / 16 | 8 / 8 | 1902 / 1915 | 5725 / 5762 |
| 100 | neighbor | 60 / 66 | 1263 / 1281 | 77 / 80 | 15 / 15 | 7 / 7 | 1935 / 1935 | 5764 / 5773 |
| 100 | global-style | 56 / 56 | 1251 / 1255 | 7521 / 7523 | 16 / 17 | 7 / 8 | 1854 / 1866 | 13120 / 13167 |
| 100 | font | 8 / 8 | 1290 / 1293 | 7578 / 7580 | 16 / 16 | 8 / 8 | 1881 / 1884 | 13147 / 13154 |
| 100 | final-export | 0 / 0 | 1268 / 1319 | 7550 / 7626 | 16 / 16 | 8 / 9 | 1863 / 1910 | 13177 / 13183 |

The usable preview includes compilation, the native emitter, full conversion, screening, contact sheet, cache validation and materialization. The first raster exists earlier, but the helper returns the verified bundle only at completion; it is not a streamed preview. Warm unchanged builds perform zero conversion and zero raster calls; one-slide edits rasterize one slide; style/font changes and forced final refresh rasterize all slides.

## Decision and budget

Keep the existing verified cache and full native conversion. Conversion remains about 1.1–1.3 seconds at these sizes and is not the dominant 100-slide edit cost: the remaining native emission, screening, contact sheet and materialization account for much of its roughly 5.7 seconds. A second renderer would add theme, numbering, notes and provenance risks without evidence of a worthwhile conversion saving. No new renderer or approval shortcut is justified by this sample.

Use the observed upper bounds as local synthetic regression budgets: warm unchanged under 0.35 seconds, one-slide preview under 2/3/6 seconds at 6/30/100 slides, full 100-slide local preview under 14 seconds. They are comparison budgets for this fixture/environment, not customer/provider SLAs or promises about image-heavy or branded decks. Re-measure representative slow decks before changing this boundary. Final output still needs the exact full-deck consistency and approval gates.

## Reproduce

Run `node scripts/performance/render-benchmark.mjs HELPER_CHECKOUT NEW_SCRATCH_DIRECTORY` with the existing helper dependencies and installed local renderer. The script writes raw samples and a summary to that private directory. `BENCH_COUNTS` and `BENCH_REPEATS` can bound an investigation; `BENCH_SUMMARY_ONLY=1` regenerates a report from existing samples without repeating work. Never substitute fake conversion timings or mark generated critic packets as owner review.
