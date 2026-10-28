# Explicit look and design answers

Use `studio desk answer --folder PATH --input FILE` only for the person's actual answer. Read `desk context` for target `look` or `design` first. Both require `drawing` in the finite scope; if an outline-only request later includes drawing, explicitly change scope first. Answers do not add a submission kind, approve Studio gates, mark Ready, deliver, hand off or start workers.

## A later look choice

Target `look` requires a checked outline and an unanswered look question. Context prepares bounded local brand samples on a disposable copy, returns offered IDs, inline PNG previews, the actual brand default and `questionId`, and publishes nothing. Show the returned previews before asking the person to select a named look. If previews fail, context reports that fact; the person may explicitly choose the unseen brand default. Never choose the first option or infer default from permission to draw.

Submit this envelope using the returned basis and question:

```json
{"target":"look","expected_basis":"<basis>","answer":{"questionId":"<question>","choice":"default","response":"<person’s actual response>"}}
```

`choice` is an offered ID or the explicit token `default`. The existing brand choice API records its actual direction, house and layouts without approving a gate. Original words and History remain. Then read drawing context and supply checked compositions in the same conversation. A saved look is retained; this operation refuses an already answered question.

## A current companion question

Target `design` reads Harness Slides `design_status` for the desk’s canonical `work/` project. Context returns its current question (including offered options), revision and slide state. Missing or closed questions refuse; this command does not create a design plan.

```json
{"target":"design","expected_basis":"<basis>","answer":{"questionId":"<question.id>","planRevision":"<revision>","decision":"<actual offered decision>","feedback":"<person’s actual response>"}}
```

The exact four answer fields go through Harness Slides `design_respond`. Its continuation rules and genuine design decision remain authoritative. A changed question/revision refuses; no answer, waiver or approval is fabricated.

## Guarded publication

Both targets bind current deck bytes, scope and canonical requirements. Look identity also binds exported brand-contract bytes, offered metadata and preview PNG chunks, excluding only nonvisual text/time chunks; pixel, color and animation data remain bound. Disposable paths and render timestamps do not identify a question. Companions run outside the write lock. Before bounded publication, the same process/workspace/team/worker and changed-input guards run again. Refusals leave canonical materials and History unchanged; read fresh context and ask for any changed answer.
