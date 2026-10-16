# Software claims and product relevance

Use when writing or reviewing feature behavior, availability, adoption or product
tradeoffs. Keep an internal link from each material claim to selected evidence.
This adds software-specific questions to the existing factual-support workflow;
it does not create another review pass or authorize outside research.

- Establish relevant product/release, edition, deployment type and feature state.
  Distinguish generally available, preview, planned, deprecated and removed.
  Name defaults, opt-in flags and required companion versions where they change
  the reader's outcome. Do not present a roadmap intention as delivered behavior.
- Explain the mechanism: what the software changes and why that could help the
  stated task. Then distinguish supported capability, observed result and your
  interpretation. Do not turn “supports” into “automates” or “can” into “always.”
- Include material adoption constraints: permissions, dependencies, compatibility,
  operating effort or licensing when relevant. Research changing availability
  only within the allowed policy; supplied-only gaps remain explicit.
- Compare alternatives against the same task and criteria. Keep versions, scope,
  measurement conditions and configuration differences visible. Explain which
  constraints favor each choice; avoid unsupported universal superiority.
- Link appropriate current product documentation or release evidence near the
  claim. Record the date/version of a check when it affects validity. Never infer
  present availability solely from an undated promotional page.

Example of editorial separation: documentation can establish that a feature
filters rows before an operation. A workload measurement is still needed to
claim a particular speedup. A customer's cost saving needs its own evidence.

Flag unsupported statements with their exact passage and missing evidence.
Neither removing a number nor adding “may” automatically makes a claim supported.
Do not guess edition names, release dates, prices or customer outcomes.

Basis: GitLab availability guidance and Blog Studio's existing evidence contract;
see [sources](sources.md) only for provenance or guide maintenance.
