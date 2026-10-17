# Marketing Studio working agreements

- Marketing Studio owns shared settings and launching. Studio pipelines stay in
  their independently runnable directories under studios/.
- Use full product names in code, documentation, issues, and commits.
- Python 3.11 or newer, standard library only, and no frontend build step.
- UI changes follow the shared Golden Gate-inspired design in
  `docs/design/golden-gate.md`; use the `macos-golden-gate-design` skill when
  available. Reserve material for navigation, toolbars and transient controls;
  keep forms and reading surfaces opaque.
- No writing or training content belongs in this repository.
- Tests use disposable settings, workspaces, Git identities, and processes. Never
  touch the person's real studio state or start provider jobs during verification.
- Shared settings must use the existing studios-config file and its adjacent lock.
  Preserve unrelated values and reject conflicting edits from outdated forms.
- Preserve existing workspaces. Only initialize an unconfigured studio after an
  explicit setup or launch action. Never automatically install or update studios.
- Work in coherent increments. Run targeted checks at milestones and the full
  relevant suite once before completion; prefer the shared Tart runner on macOS.
- Public content must not contain session keys, credentials, private team content,
  or machine-specific operational records.
