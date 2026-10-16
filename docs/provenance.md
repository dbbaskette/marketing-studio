# Source provenance

The MIT licenses and source notices of all three studios are retained under
`studios/`. Their committed histories were imported with directory prefixes.
[Import records](migration/imports.json) identify original revisions and prove
that the imported main trees matched before behavioral changes; the adjacent
commit maps relate original and prefixed histories.

| Shared component | Origin | Adaptation |
| --- | --- | --- |
| `core/studio_core/server.py` | Presentation Studio HTTP server | Isolated product identities, static roots, and exception types |
| `core/studio_core/studios_config.py` | Training Studio settings store and Blog Studio leaf patcher | Isolated product contexts, local workspace group, strict Marketing Studio form validation |
| `core/studio_core/companions.py` | Presentation Studio pinned companion installer | Common implementation bound to each native installer's context |
| `ui-kit/` | Identical assets from all three studios | Single source, resolved into ordinary files in release archives |

Marketing Studio's catalog, setup flow, bridge, CLI, bundle builder, and suite
installer coordinate the native studios. Each native pipeline, its tests, and
its own launcher remain in its studio directory.

The README header was generated for this project. Its brief is recorded in
[the asset prompt](assets/header-prompt.md).
