# Infographic Studio follow-up implementation ledger

Specification: [execution design](../specs/2026-10-28-infographic-followups.md).
Milestone 3: #144 with #173–#176 and user-requested Google Docs/PDF delivery #184.
Implementation follows the user's explicit instruction; first-release live/provider
and owner gates remain separate and are not inferred passed.

| Slice | Responsibility / interfaces | Verification outcome |
| --- | --- | --- |
| A — document intake | native documents.py, sources.py, source provenance/coverage, API/CLI/browser upload | Exact original/text/location hashes; bounded DOCX/PDF; visible gaps; no implicit OCR/provider/install; real installed reader acceptance |
| B — remote intake | independent shared Google transport, native remote_sources.py; account settings; safe public fetching | Fixed API destinations, explicit reads/stable revisions/all selected tabs; DNS pinning/redirect/private-address refusal; injected transports |
| C — document delivery | native google_delivery.py / DOCX packaging; exact approved PDF/Google/both choices | Intent before write, unknown reconciliation/no duplicates, current approval/review binding, private image conversion and PDF fallback |
| D — reviewed research | native research.py over existing schema-2 research_contract | Exact helper/capture/review digests, purpose/source-mode fidelity, counterfacts/gaps, missing/stale refusal; no implicit public work |
| E — handoffs/team | native handoffs.py, team.py; independent workspace/owned Git inventory | Selected-file imports, explicit refresh, private-data inventory, ownership/claim conflict, missing assets, non-fast-forward/offline recovery |
| F — integrated desk/distribution | native skill/docs/UI/readiness/installer; shared Tart runner | Desktop/phone full intake→review→approval→delivery; CLI parity; full relevant suite and source-independent bundle |

- [x] Slice A implementation and targeted acceptance: 35 native checks, actual installed PDF extraction, phone multi-file preview/review/replacement and the full editing/export browser journey.
- [x] Slice B: fixed Google transport, permission/version/tab captures and pinned public fetch; seven boundary checks.
- [x] Slice C: new Google Doc/PDF/both delivery, private OOXML package, durable intent and read-only recovery; four offline delivery checks.
- [x] Slice D: complete schema-2 research verification, exact purpose/source mode and immutable evidence; three real-helper synthetic checks.
- [x] Slice E: selected studio material import and independent team inventory/claim sharing; eight synthetic handoff/Git checks.
- [x] Slice F: 686 root and 139 native checks pass on the integrated tree; real installed PDF reader/renderer and synthetic schema-2 helper included. Phone bridge intake and Google/PDF delivery, authenticated suite return, and independent Apple Silicon install pass.
- [ ] Separately authorized real Google conversion/fidelity and applicable live/owner gates.

Every write uses an expected project revision. Capturing/refreshing a source clears
dependent story/page checks and approval; reviewed research never skips that rule.
A Google delivery binds account/destination, payload identity and current approved
revision; uncertain writes are reconciled read-only. Sharing requires an exact
selected inventory and never transfers approval or publishes unrelated private files.


## Final verification

The final application tree at `4b15913e` passed 686 root tests and 139 native tests
with no skips on macOS 27.0.1/Python 3.14.5, including the installed PDF reader and
renderer and source-only Harness Research fixture. Integration includes main's
Blog Studio migration; its absent optional-cache regression was corrected and its
nine shared sync-guard checks pass. All four native setup/launch journeys, 41 Hub
steps and 39 shared CLI commands pass on the integrated source.

A stopped-base disposable macOS 27.0 Tart clone passed the focused final bridge,
team/delivery and browser checks, the authenticated desktop/phone round trip, and
source-independent Apple Silicon bundle acceptance; the clone was deleted. Broad
684-root/138-native VM suite results are retained as earlier evidence. The first
broad VM run's application checks passed, but its mounted shell program changed
while running and its shell completion failed; the final entry points freeze the
program before execution and the subsequent VM run completed successfully.

The final rebuilt Apple Silicon archive also passes independent install/removal,
all four local formats and Word preview/import after both the source download and
Marketing Studio are removed. Its SHA-256 is
`f992c77e9ba8f79e127a1ea2f93b1e44125a8624ec20e26ce4f748432b603f08`.
No account/provider commands were allowed in bundle acceptance. Real Google
conversion/fidelity and first-release live/provider/owner gates remain separate.
