# Compare two Training Studio versions

Use the first complete deck from each version. Keep all run data outside this repository. This exercise has a 20-minute canary decision workshop and a hands-on Git procedure. The canary benchmark uses the original two saved text snapshots of the [deployment guide](https://docs.cloudfoundry.org/devguide/deploy-apps/rolling-deploy.html) and [health checks guide](https://docs.cloudfoundry.org/devguide/deploy-apps/healthchecks.html). Reuse identical snapshots across both versions. The Git case creates its own sources and verifies its predicted commit in a disposable repository.

From Training Studio, prepare the inputs once per case. Supply the model, reasoning effort and brand actually selected for the paired runs.

```sh
python3 scripts/evaluation/teaching.py prepare canary /tmp/canary-input --model MODEL --effort EFFORT --brand BRAND --source deployments.txt --source health.txt
python3 scripts/evaluation/teaching.py prepare git /tmp/git-input --model MODEL --effort EFFORT --brand BRAND
```

For each pair, give both versions the same intake, source files, approved outline and settings. Record studio and companion revisions, actual model, optional seed if available, elapsed time, and any interruptions separately. Keep evaluation questions and answer keys outside the generator's inputs. Save the two first exports as BASE/deck.pptx and NEXT/deck.pptx in separate copies of the prepared input directory. Save the approved outline object (sections and objectives, without run IDs or approval timestamps) as approved-outline.json in each. The comparison checks the actual source snapshots, intake, controls and approved outlines. Record any deviations and start a separate comparison if inputs differ. Generating real decks is an operator-run evaluation. Ordinary CI uses disposable fixtures and starts no providers.

```sh
python3 scripts/evaluation/teaching.py blind BASE NEXT /tmp/teaching-pair
python3 scripts/evaluation/teaching.py compare /tmp/teaching-pair
```

Between those commands give a reviewer only the review directory and the source snapshots. Ask them to view each deck with its embedded speaker notes, trace each observation to its owner, and rehearse every demo and exercise with the supplied materials. Record elapsed teaching, practice and debrief time, missing props, answer leaks and consequential errors. In scores.json score each dimension 0 (missing or misleading), 1 (requires instructor repair), or 2 (usable as supplied). Cite slides, notes or a specific omission in every row. A wrong operational action is a release concern even with a high total. The comparison reveals identities after scoring and reports each dimension.

For a learner pilot, have an instructor deliver the class with the supplied materials. Give learners the held-out transfer question before showing its answer. Score one point each for a defensible action or command, an observation from the case, and a condition that changes the action. Record counts, time, unexpected help and sample size separately from the deck review. Use the same conditions for both versions. Record “not observed” until an instructor or learner actually participates.
