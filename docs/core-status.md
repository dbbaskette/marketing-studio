# Shared infrastructure status

| Area | Shared source | Remaining studio-specific behavior |
| --- | --- | --- |
| Settings storage | `core/studio_core/studios_config.py` (Blog Studio's `studios_config.py` is a thin face over it) | Product validation, errors, and Blog Studio migration |
| HTTP protocol/server | `core/studio_core/server.py` (`for_product`) | Domain routes; Blog Studio's own page rules (request checks, CSP, limits, serialized access) on the shared server |
| Companion installation | `core/studio_core/companions.py` | Native installation records, product prerequisites, and reporting |
| Shared stylesheet and Markdown renderer | `ui-kit/` | Product controllers and layout additions |
| Dependency pins | `pins/companions.json` | Each studio uses its applicable companions |
| Bundle traversal and staging | `core/studio_core/packaging.py`, `bundles.py` | Product inventory rules and native smoke checks |
| Runner modules both deck studios use | `core/studio_core/shared_runner/` | Each studio's pipeline, engine, jobs and the parts that differ |
| The deck studios' computer check, data folder and guidance sync | `computer_check.py`, `studio_home.py`, `guidance_sync.py` | Each studio's thin `computer.py`, `home.py` and `sync_guidance.py`: its name, words and the few functions that differ |
| The deck studios' desk script | `core/studio_core/deck_web/desk-base.js` | Each desk's own `app.js` |
| Google requests | `core/studio_core/google_api.py` | The hosts, paths and methods each studio uses, and its own sentences |
| PDF, Word and HTML text | `core/studio_core/source_documents.py` | Each caller's limits and sentences, and its archive opening for Word |
| The list of a project's parts | `StudioShell.parts` in `core/studio_core/deck_web/shell.js`, drawn by `ui-kit/style.css` | What each studio lists and the state of each part |
| Desk parts | `core/studio_core/drafting/`, `text_checks.py`, `step_times.py`, `ui-kit/drafting.js` | Job queues, kinds and writing context; each desk's own screens |
| Blog Studio's Git, sharing (`studio_sync/`), brand (`studio_brand/`), engine, research and job workflows; each deck studio's pipeline, engine and jobs | Native studio directories | Preserved. Moving Blog Studio's sharing and brand onto the shared runner needs a reconciliation of about 1,500 lines of Blog Studio-only logic, not done yet |

The compatibility module loader creates isolated product contexts from one source
file, retaining native constants and exception identities. Companion bindings
retain native patch points while sharing the implementation. Tests explicitly
check context isolation, native package completeness, and source-independent use.
