# Source provenance

The MIT license in this repository covers Marketing Studio and retained source
notices. These files started from Presentation Studio at revision
`edf565acd3ebc87a7c024d5c59ab17887691017a`:

| Marketing Studio file | Original file | Adaptation |
| --- | --- | --- |
| `marketing_studio/server.py` | `skills/presentation-studio/scripts/server.py` | Product identity, imports, and static file catalog |
| `marketing_studio/shared.py` | `skills/presentation-studio/scripts/studios_config.py` | Local work-root group, repository validation, restrictive new-file permissions, and imports |
| `marketing_studio/web/style.css` | `skills/presentation-studio/scripts/desk/style.css` | Retained shared studio stylesheet |

Studio runtime code is neither copied nor modified. The compatibility bridge uses
interfaces in the independently installed studios.
