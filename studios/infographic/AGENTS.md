# Infographic Studio working agreements

- Keep the native pipeline independently runnable and reuse Marketing Studio core
  infrastructure. Application code uses Python 3.11+ and the standard library.
- No source material, generated artwork, prompts from real projects, or exports
  belong in this repository. Tests generate synthetic material in disposable folders.
- Verification never starts providers, reads personal credentials, changes a real
  workspace, or installs software. Live provider acceptance is a separate action.
- Shared settings retain the existing studios-config file and adjacent lock.
  Gemini credentials stay in the image adapter's environment, never saved settings.
- Preserve existing studios' worker confinement. Image tools and image inspection
  require explicit, narrowly scoped native adapters.
- New work uses the editing desk. Story selection and final approval are
  checkpoints, not legacy guided pipelines or review-level controls.
