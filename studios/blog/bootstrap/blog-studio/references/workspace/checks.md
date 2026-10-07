# Mechanical checks

Run installed runtime helpers (offline: package `scripts/`):

```text
python3 <runtime>/text_checks.py lint --file <draft> --rules-file <rules>
python3 <runtime>/text_checks.py preserve --before <original> --after <revision>
python3 <runtime>/text_checks.py count --file <derived-copy>
```

Lint reports selected rule matches and advisory repetition; code, URLs, and
quotations are protected. Preservation compares numbers, URLs and quoted spans,
not meaning. Review semantic differences yourself. Counts are mechanical.
None establishes human authorship, factual equivalence, or ranking readiness.
Use [review records](reviews.md) only for checks actually performed; keep
limitations with the findings.
