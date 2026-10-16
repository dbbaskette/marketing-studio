# Shared infrastructure status

| Area | Shared source | Remaining studio-specific behavior |
| --- | --- | --- |
| Settings storage | `core/studio_core/studios_config.py` | Product validation, errors, and Blog Studio migration |
| HTTP protocol/server | `core/studio_core/server.py` | Domain routes; Blog Studio's specialized server |
| Companion installation | `core/studio_core/companions.py` | Native installation records, product prerequisites, and reporting |
| Shared stylesheet and Markdown renderer | `ui-kit/` | Product controllers and layout additions |
| Dependency pins | `pins/companions.json` | Each studio uses its applicable companions |
| Bundle traversal and staging | `core/studio_core/packaging.py`, `bundles.py` | Product inventory rules and native smoke checks |
| Git, sharing, brand, engine, research, and job workflows | Native studio directories | Preserved; drifted implementations are not combined in this migration |

The compatibility module loader creates isolated product contexts from one source
file, retaining native constants and exception identities. Companion bindings
retain native patch points while sharing the implementation. Tests explicitly
check context isolation, native package completeness, and source-independent use.
