# Blog Studio command inventory

Generated from `studio.py`; use `--help` on a listed command for required inputs and choices. Prefix each with `--root /absolute/workspace`. Optional global `--compact` returns the bounded outcome contract described in [capabilities](capabilities.md).

| Command | Options |
| --- | --- |
| `studio.py run` | — |
| `studio.py run create` | `--title`, `--author`, `--audience`, `--goal`, `--tone`, `--profile`, `--style`, `--id`, `--brand`, `--variant`, `--research`, `--stop`, `--engine`, `--seconds`, `--source`, `--mode`, `--manuscript`, `--outline-text`, `--point` |
| `studio.py run list` | — |
| `studio.py run status` | `--id` |
| `studio.py run submit` | `--id`, `--expected`, `--stage`, `--file`, `--notes` |
| `studio.py run approve` | `--id`, `--expected` |
| `studio.py run changes` | `--id`, `--expected`, `--request`, `--stage` |
| `studio.py run handoff` | `--id`, `--expected` |
| `studio.py run choose` | `--id`, `--expected`, `--angle`, `--note` |
| `studio.py init` | — |
| `studio.py list` | — |
| `studio.py library` | — |
| `studio.py library read` | `--id`, `--query`, `--limit`, `--max-chars` |
| `studio.py library locate` | `--collection`, `--path` |
| `studio.py library setup` | `--file` |
| `studio.py library collections` | — |
| `studio.py library preview` | `--collection` |
| `studio.py library import` | `--preview`, `--limit`, `--retry` |
| `studio.py library voice-links` | `--file`, `--author`, `--site`, `--import`, `--keep`, `--retry`, `--purpose` |
| `studio.py library find` | `--reusable-only`, `--query`, `--status`, `--collection`, `--author`, `--topic`, `--product`, `--since`, `--until`, `--role`, `--kind`, `--limit`, `--offset` |
| `studio.py library curator` | `--harness` |
| `studio.py library analyze` | `--id` |
| `studio.py library curate` | `--id`, `--file` |
| `studio.py library lesson` | `--file` |
| `studio.py library promote` | `--item`, `--confirm` |
| `studio.py manage` | `--port`, `--open`, `--harness` |
| `studio.py research` | — |
| `studio.py research import` | `--id`, `--case` |
| `studio.py research plan` | `--id`, `--file` |
| `studio.py research record` | `--id`, `--file`, `--run`, `--item` |
| `studio.py research status` | `--id` |
| `studio.py editorial` | — |
| `studio.py editorial board` | `--id`, `--limit`, `--offset`, `--query`, `--stage`, `--owner` |
| `studio.py editorial inbox` | `--id`, `--limit`, `--offset`, `--online`, `--account`, `--query` |
| `studio.py editorial schedule` | `--id`, `--file` |
| `studio.py editorial evidence` | `--id`, `--file` |
| `studio.py editorial package` | `--id`, `--file` |
| `studio.py editorial visual` | `--id`, `--file` |
| `studio.py editorial assets` | `--id` |
| `studio.py home` | `--query`, `--stage`, `--limit`, `--offset` |
| `studio.py context` | `--id`, `--compact`, `--limit`, `--offset` |
| `studio.py readiness` | `--harness`, `--online` |
| `studio.py team` | — |
| `studio.py team join` | `--repository`, `--branch`, `--share` |
| `studio.py team status` | — |
| `studio.py team sync` | — |
| `studio.py team take` | `--id` |
| `studio.py team takeover` | `--id` |
| `studio.py team handover` | `--id` |
| `studio.py team publish` | `--id` |
| `studio.py team migrate` | `--from-workspace`, `--article`, `--source`, `--profile`, `--memory` |
| `studio.py resume` | `--id` |
| `studio.py passages` | `--id`, `--source`, `--query`, `--limit`, `--offset`, `--max-chars` |
| `studio.py check` | `--id`, `--rules-file` |
| `studio.py cache` | `--clear` |
| `studio.py select` | `--id` |
| `studio.py status` | `--id`, `--query`, `--online`, `--account`, `--details`, `--format` |
| `studio.py route` | `--id`, `--destination` |
| `studio.py changes` | `--id`, `--kind`, `--revision`, `--google-file`, `--observation`, `--against` |
| `studio.py defaults` | — |
| `studio.py defaults show` | `--id` |
| `studio.py defaults set` | `--scope`, `--key`, `--value` |
| `studio.py defaults reset` | `--scope`, `--key`, `--value` |
| `studio.py prepublish` | `--id`, `--title-limit` |
| `studio.py plan` | `--topic` |
| `studio.py profile` | — |
| `studio.py profile create` | `--name`, `--id`, `--guide-file`, `--background-file`, `--rules-file`, `--status`, `--sample` |
| `studio.py profile save` | `--id`, `--name`, `--guide-file`, `--background-file`, `--rules-file`, `--status`, `--sample` |
| `studio.py profile show` | `--id`, `--revision` |
| `studio.py profile retire` | `--id`, `--expected-revision`, `--confirmed` |
| `studio.py style` | — |
| `studio.py style create` | `--name`, `--id`, `--guide-file`, `--status`, `--sample` |
| `studio.py style save` | `--id`, `--name`, `--guide-file`, `--status`, `--sample` |
| `studio.py style show` | `--id`, `--revision` |
| `studio.py style retire` | `--id`, `--expected-revision`, `--confirmed` |
| `studio.py source` | — |
| `studio.py source add` | `--name`, `--file`, `--text-file`, `--origin`, `--purpose`, `--author`, `--note`, `--status` |
| `studio.py source show` | `--id` |
| `studio.py source update` | `--id`, `--text-file`, `--status`, `--note` |
| `studio.py article` | — |
| `studio.py article create` | `--title`, `--id`, `--mode`, `--profile`, `--author`, `--voice`, `--tone`, `--audience`, `--blog-type`, `--review-folder`, `--research`, `--stop` |
| `studio.py article show` | `--id` |
| `studio.py article rename` | `--id`, `--title` |
| `studio.py article research-policy` | `--id`, `--policy` |
| `studio.py article author` | `--id`, `--name` |
| `studio.py article remember` | `--id`, `--key`, `--file` |
| `studio.py article forget` | `--id`, `--key` |
| `studio.py article detach-context` | `--id`, `--item` |
| `studio.py article attach` | `--id`, `--source`, `--purpose` |
| `studio.py article save` | `--id`, `--kind`, `--file`, `--label` |
| `studio.py article restore` | `--id`, `--kind`, `--revision`, `--expected`, `--apply` |
| `studio.py article progress` | `--id`, `--stage`, `--next-step`, `--pending-question`, `--stop` |
| `studio.py article context` | `--id`, `--file` |
| `studio.py article guidance` | `--id`, `--adopt` |
| `studio.py article note` | `--id`, `--kind`, `--text` |
| `studio.py article voice` | `--id`, `--profile`, `--revision`, `--voice`, `--tone` |
| `studio.py article review` | `--id`, `--check`, `--status`, `--file` |
| `studio.py article derive` | `--id`, `--name`, `--file` |
| `studio.py google` | — |
| `studio.py google pull` | `--id`, `--accept`, `--expected`, `--comparison`, `--confirmed`, `--resolution-file`, `--discard-remote` |
| `studio.py google start` | `--title`, `--snapshot`, `--observation`, `--file` |
| `studio.py google capabilities` | `--file` |
| `studio.py google source` | `--name`, `--purpose`, `--author`, `--observation`, `--file` |
| `studio.py google status` | `--id`, `--kind`, `--online`, `--account` |
| `studio.py google prepare` | `--id`, `--kind`, `--snapshot`, `--observation`, `--file`, `--new-document` |
| `studio.py google confirm` | `--id`, `--kind`, `--snapshot`, `--observation`, `--file`, `--transfer` |
| `studio.py google compare` | `--id`, `--kind`, `--snapshot`, `--observation`, `--file` |
| `studio.py google accept` | `--id`, `--kind`, `--snapshot`, `--observation`, `--file`, `--expected-comparison`, `--resolution-file`, `--discard-remote` |
| `studio.py google receipt` | `--id`, `--file` |
