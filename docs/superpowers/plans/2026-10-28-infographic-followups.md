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
- [ ] Slice B implementation and targeted acceptance.
- [ ] Slice C implementation and targeted acceptance.
- [ ] Slice D implementation and targeted acceptance.
- [ ] Slice E implementation and targeted acceptance.
- [ ] Slice F final integrated verification.
- [ ] Separately authorized real Google conversion/fidelity and applicable live/owner gates.

Every write uses an expected project revision. Capturing/refreshing a source clears
dependent story/page checks and approval; reviewed research never skips that rule.
A Google delivery binds account/destination, payload identity and current approved
revision; uncertain writes are reconciled read-only. Sharing requires an exact
selected inventory and never transfers approval or publishes unrelated private files.
