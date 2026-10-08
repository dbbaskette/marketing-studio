# Verification boundary

Blog Studio owns its test suite, package checks, installer checks and supported
Python/platform matrix. Run its portable check entry point with a supported
Python interpreter and a fresh results directory:

```sh
bash scripts/ci/check.sh /path/to/python3 /path/to/results
```

The repository workflow runs the same checks on macOS and Linux with Python
3.11 and 3.13. Existing self-hosted runner labels and the workflow filename are
retained for compatibility with the configured external service. A temporary,
read-only Linux readiness check also keeps the already-active trusted-base
workflow usable during this transition; it performs no provisioning.

VM provisioning, runner registration, queue monitoring, credential handling,
resource limits and machine cleanup belong to the separate shared CI
infrastructure. They are not Blog Studio features, installation prerequisites,
roadmap items or project-owned services. Configure and operate that
infrastructure in its own repository and local instructions.

`scripts/ci/macos-guest.sh` contains only this project's isolated Mac checks.
A shared runner supplies its source/results mounts and lifecycle. Historical
validation reports record the environments actually used; they do not make
those test tools product dependencies. Local success does not waive required
GitHub or release gates.
