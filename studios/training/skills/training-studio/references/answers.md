# Actual look and design answers

Read `studio desk context --folder PATH --target look@101` or `design@101` (omit @level for a plain training). Use `studio desk answer --folder PATH --input FILE` only after the person gives the actual answer. Never infer answers from permission to draft. These operations start no assistant, approve no Training Studio gate and mark nothing Ready.

For `look`, context supplies the current questionId, actual offered IDs and PNG previews. Show those previews before a named choice. Submit:

```json
{"target":"look@101","expected_basis":"<basis>","answer":{"questionId":"<current question>","choice":"default","response":"<person’s actual response>"}}
```

Choice is an offered ID or the explicitly requested `default`; default never means first option. Failed previews allow only an explicitly chosen unseen brand default. Look requires drawing scope; an existing answered look is preserved.

For `design`, context reads the actual Harness Slides project question and revision. Submit:

```json
{"target":"design@101","expected_basis":"<basis>","answer":{"questionId":"<question.id>","planRevision":"<revision>","decision":"approve","feedback":"<person’s actual response>"}}
```

Use the actual offered decision and nonempty response. Initial design requires drawing scope. For a drawing-bound word proposal, design context uses part scope and binds the actual saved token, question, revision and seen version; the response goes through Training Studio's existing checked word-decision path. `cancel` discards that proposal without changing words. A title/word proposal alone does not approve drawing changes; notes do not require this design approval.

Context and rejected answers preserve canonical training and local proposal/project bytes. Checks run on disposable copies, outside the short write lock. Before publication, ownership, workers, scope, all training inputs and external proposal/project bytes are checked again. Changed questions, revisions or inputs refuse; read context again. Settle a pending word proposal before another change. History, source pins, citations, practice metadata and Google records remain.
