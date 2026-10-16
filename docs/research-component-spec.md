# Shared research component: spec

> Historical proposal. See [the implemented architecture](architecture.md) for the current Marketing Studio scope.
**Date:** 2026-10-15 · **Status:** approved direction; Blog Studio is the first studio built to it
**Applies to:** Training Studio, Presentation Studio and Blog Studio, and the Marketing Studio core later

## 1. Goal

Every studio researches in the same way and produces the same research output, so that the code doing it is one shared component. What differs between studios is only what each one does with the findings afterwards.

| Layer | Shared or per studio | Examples |
|---|---|---|
| **Research layer** | **Shared: this component** | The harness-research runtime and its pin; planning questions; one worker per question, with research tools; recording findings; the record and report on disk; staleness; installing and checking harness-research |
| **Use layer** | Per studio | Who may allow public research, and how; how the questions are worded for the item; the gate pages; what findings feed: a training blueprint, a deck outline, a blog draft or fact-check |

The component is a Python package, `studio_research/`, standard library only. Until the monorepo exists, each studio carries an identical copy, recorded in `studio_research/vendor.json`. In the monorepo it becomes `core/studio_core/research/` (plan, Phase 7).

## 2. What exists today

| | Training | Presentation | Blog (before) |
|---|---|---|---|
| Runtime | harness-research 0.8.1 | harness-research 0.8.1 | Its own Python engine |
| Wrapper | `runner/research.py` | `runner/research.py`, 23 lines different from Training's | None |
| Plan file | `.training-studio/research-plan.json` | `research/plan.json`, plus `plan.md` | `derived/research.json` |
| Report the gate shows | `research-report.md`, a copy | `research/report.md`, written from the record | `derived/research-report.md` |
| Workers | Agents with worker tools | One agent per question with worker tools (`research_steps.py`) | Tool-less; the browser runner writes free Markdown and records nothing |
| Supplied documents | In the training folder | The deck's `sources/` | Attached references in Blog's source store |

Presentation's flow is the most complete, so the component is cut from it. Training's wrapper is its smallest piece, so `runtime.py` starts from that.

## 3. The component

```text
studio_research/
  __init__.py      the public surface below, and the version of the component
  runtime.py       Research(): plan / record / status / version over the installed harness-research
  project.py       the item's research folder: layout, document snapshots, plan building, status
  tools.py         the research tools a worker is given, and the stdio server that offers them
  steps.py         the flow: draft plan → plan → one job per question → record → report
  stand_in.py      a harness-research that needs neither Node nor the skill; tests only
  vendor.json      where this copy came from, file by file (until the monorepo)
```

### 3.1 `runtime.py`

- `Research(runtime=None, run=None)` finds the installed harness-research. The lookup order is:
  1. `HARNESS_RESEARCH_RUNTIME` when it is set;
  2. the installer's folder (`~/Library/Application Support/Harness Research/current`, or `~/.local/share/harness-research/current`);
  3. each assistant's skills folder.
- It exposes:
  - `plan(project, file, allow_web=False)`;
  - `record(project, run, item, finding)`, which passes a `headline` through;
  - `status(project)`;
  - `version()`, which calls `--version`.
- Each returns the command's own JSON.
- **Refusals.** `Refused` carries the command's one line; `busy` is true when another save held the lock. Every refusal is a `ValueError`, so each studio shows it as it shows its own.
- **Node.** Node 20 or newer is required, and its absence is one refusal sentence that names the fix.
- **Tests.** `STAND_IN` (`STUDIO_RESEARCH_STAND_IN`) names a Python stand-in that is run in place of Node and the skill.

### 3.2 `project.py`: the research folder

Every studio uses this layout inside the item's own folder (a training, a deck or a blog).

| Path | What it holds | Shared with the team |
|---|---|---|
| `.harness-research/research.json` | harness-research's record: plan, pins, findings | Yes |
| `.harness-research/research-report.md` | harness-research's report, rewritten on every save | Yes |
| `.harness-research/history/` | Earlier runs, kept by harness-research | Yes |
| `research/plan.json` | The plan as handed to harness-research | Yes |
| `research/plan.md` | That plan, readable, for the plan gate | Yes |
| `research/report.md` | The report the research gate shows: a copy of harness-research's, written when research finishes | Yes |
| `research/web/<sha256>.md` | Public pages a worker saved, as readable text, named by content | Yes (public text) |
| `research/sources/<key>.md` | Snapshots of the documents the studio supplied | **No**: rebuilt on each computer |

- **Supplied documents.** The studio hands the component its documents as `{title, origin, text, status}`.
  - `key` is the first 16 hex digits of the SHA-256 of `origin + "\n" + text`. The same document therefore has the same name on every computer and every clone, whatever a studio calls it locally.
  - Only `status == "ready"` documents get a snapshot. Any other is listed in the plan with `file: null` and a `limits` sentence, which harness-research reports as a coverage gap.
  - Snapshots no longer supplied are removed.
- **Planning.** `build_plan(topic, purpose, scope, questions, documents, input_files)` returns the plan harness-research takes:
  - `sources` comes from the snapshots;
  - `input_files` names the item's own files whose change makes research stale (for a blog: BRIEF, OUTLINE, DRAFT);
  - a claim becomes `{file, quote, start}` in one of those files.
- **Writing the plan.** `save_plan(...)` writes `research/plan.json` and `plan.md` and calls `plan`. It returns the run and `carried`.
- **Recording.** `record(project, run, item, finding)` retries a busy save up to 20 times, as Presentation does.
- **Status.** `status(project)` returns the normalized status every studio shows:

  ```json
  {"run": "…", "status": "not-started|in-progress|complete|stale", "pending": [], "unresolved": [],
   "stale_items": [], "carried": [], "source_gaps": [], "completed": 0, "total": 0,
   "report": ".harness-research/research-report.md", "file": ".harness-research/research.json"}
  ```

- **Finishing.** `publish_report(project)` copies harness-research's report to `research/report.md` when research finishes. That copy is what the research gate shows and what is approved, so the gate's document doesn't change while it is being decided on.

### 3.3 `tools.py`: a research worker's tools

These are the research half of Presentation's `runner/worker_tools.py`: the same job folder, the same checks and the same server.

| Tool | Given when | Does |
|---|---|---|
| `list_inputs` / `read_input(name, part)` | Always | The job's inputs: the question, the item's context |
| `read_source(source_id, offset, length)` | Always | A window of a supplied snapshot or a saved page |
| `search_source(source_id, query)` | Always | Where words occur in a source |
| `save_source(url)` | Only when public research is allowed | Fetches a public page, saves it as readable text and returns its `source_id` |
| `submit_finding(item, status, summary, limits, evidence, headline)` | Always | Checks the finding, locates each quote in its source, and hands it back in the shape `record` takes |

- **Fetching.** Only public `http` and `https` addresses are fetched. Every address a name resolves to must be public, each redirect is checked again, and the connection goes to the address that was checked. A computer behind a proxy has the proxy connect instead.
- **Locating quotes.** A quote is located exactly first, then allowing for white-space, quote-mark and dash differences. The stored quote is always the source's own wording.
- **Handing back.** A finding can be handed back three times before the job counts as failed. A research job never asks the person anything.
- **Running a job.** `prepare(folder, question, sources, fetch)` sets a job up, `command(folder)` is how an agent starts the server, and `collect(folder)` returns the accepted finding and the pages saved.
- **The agent's flags.** Each studio runs the agent with its own process runner. Blog has `blog_worker` and Presentation has `agents.py`. The flags that hand an agent the server are the same everywhere:
  - **Claude Code:** `--strict-mcp-config --mcp-config <job>/mcp.json --allowedTools mcp__research[,WebSearch]`, with `--tools` naming WebSearch only when public research is allowed.
  - **Codex:** `-c mcp_servers.research.command/args`, `default_tools_approval_mode="approve"`, and `web_search="live"` or `"disabled"`.

### 3.4 `steps.py`: the flow

```text
draft plan ──► gate: plan ──► research, one job per pending question ──► gate: research ──► studio's own use
   (worker)     (person)        (workers, recorded one by one)            (person)            (per studio)
```

1. **Drafting the plan.** A tool-less worker returns `{"topic", "items": [{"id", "question", "public_query"}]}`. `public_query` is null unless public research is allowed. The studio fills in `purpose`, `scope`, the documents and the input files, and `save_plan` hands it over.
2. **Researching.** `research(project, worker, about, allow_web)` takes each question still `pending`:
   - It prepares a job with the question, the supplied snapshots, and `fetch=allow_web`.
   - It runs the studio's worker with the tools.
   - It copies any saved pages the finding quotes into `research/web/`, then records the finding.
   - A question with no accepted finding after three tries is recorded as `unavailable`, with the last reason.
   - A stopped run resumes at the next pending question.
   - `again=[ids]` researches named questions again, after a change was asked for at the gate.
3. **The gate.** When no question is pending, `publish_report` writes `research/report.md`, and the gate shows it with `status()`. After approval, the studio uses `research/report.md` and the record as it chooses.

### 3.5 Rules every studio keeps

- **Scope.** Research is `supplied-only` or `public-web`. The studio decides whether public research is allowed: Blog by the article's research policy, Training at intake, Presentation by its research switch. Only then is `allow_web` passed.
- **Public queries** are generic. They never carry a private claim, title, customer name, internal URL, path or email address. harness-research refuses URLs, paths and emails, and the worker brief says the rest.
- **Evidence** must quote, exactly, a source the plan was made with, or a page saved during the run. A document supplied after planning needs the plan saved again. Supported and contradicted findings need at least one passage.
- **Staleness.** A changed input file, a changed snapshot, or a narrowed scope makes research stale. A changed plan keeps the findings of questions defined exactly as before (`carried`).
- **What leaves the computer.** Supplied document text never goes to search. Snapshots stay local. Public pages and findings are shared with the team, as the rest of the item is.

### 3.6 Installing and checking

- **Pins.** Each studio installs harness-research from the same pin, `installer/companions.json` (`schema: 1`), at harness-research 0.8.1, commit `d58d20d`, with its tree SHA-256. In the monorepo this becomes the one `pins/companions.json`.
- **The installer's step**, `--companions ask|install|skip`, is the same in each studio:
  1. fetch the pinned commit;
  2. check it file for file;
  3. confirm its `bootstrap/SKILL.md` names it;
  4. run its own `scripts/install.mjs`.
- **Versions** are read with `node scripts/harness-research.mjs --version`.

### 3.7 Testing

- **The stand-in.** `stand_in.py` behaves like harness-research 0.8.1 for plan, record and status. It pins `input_files`, sources and claim files, carries findings, accepts headlines and escapes its report as harness-research's `literal()` does. It runs in-process (`StandIn()`) or as a command, for studios whose tests start their own command line. Every studio's tests set `STUDIO_RESEARCH_STAND_IN` by default.
- **The live test** runs plan, record and status against the installed harness-research when Node and the skill are present, and is skipped otherwise.
- **Contract tests** ship with the component and run in every studio unchanged:
  - the layout;
  - snapshot keys across clones;
  - the plan builder;
  - the normalized status;
  - busy retries;
  - each tool's checks (the fetch rules, quote locating, finding checks);
  - the flow's attempts and resume.

## 4. Adopting it

| Studio | Becomes | Moves |
|---|---|---|
| **Blog**, first | The source of the component, until the monorepo | `deep_research.py` keeps Blog's rules (the article policy, attached references at their pinned revision, exact draft claims) and calls the component. The runner's `research-plan` and `research` stages run `steps.py`, its research workers use `tools.py`, and the stage documents become `research/plan.md` and `research/report.md`. |
| **Presentation** | A user of the copy | `runner/research.py` is replaced by `runtime.py`. The research half of `worker_tools.py` becomes `tools.py`. `research_steps.py` keeps its gate logic, marks and notes, and calls `steps.py`. Saved pages move from `sources/` to `research/web/`, and supplied documents to `research/sources/`. |
| **Training** | A user of the copy | `.training-studio/research-plan.json` becomes `research/plan.json`, and `research-report.md` becomes `research/report.md`. `runner/research.py` is replaced by `runtime.py`, and its research jobs use `tools.py` and `steps.py`. |

A studio that uses the component changes none of its files. Whatever differs belongs to that studio's adapter.

## 5. Where this is going: harness-research does more

[dbbaskette/harness-research-skill#9](https://github.com/dbbaskette/harness-research-skill/issues/9) moves the multi-agent research run into harness-research itself: one worker per question, several at once, with the research tools above, plus output every studio can consume directly (`findings.json` with stable citation keys, and `brief.md`). When that lands:
- `tools.py` and most of `steps.py` become one `harness-research research` call;
- `project.status` reads `findings.json`.

The component then keeps the layout, the snapshots, the plan building and the studios' rules. The contract in §3.2 and §3.5 stays as it is.

## 6. Open questions

1. Should Presentation keep saved public pages local (its `sources/` today) rather than share them as `research/web/`? This spec shares them, so another computer can check the evidence.
2. Should the component's version be its own (for example `studio_research 1.0.0`), or the studios' shared release number?
