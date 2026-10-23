# Research from your documents, your sites and/or the public web: design

**Date:** 2026-10-23, at main c2464c2. **Owner's words:** "On all the studios, I should
have the choice in research to search a specific list of base URLs I give it AND/OR the
public internet."

## What is wrong now

Each studio words where research may look in its own way, and none of them can keep
research to a list of sites:

- **Blog Studio.** A run's `research_policy` is `none`, `supplied-only` or `web-allowed`;
  the files screen offers "Also research the web". Public discovery fetches any public URL
  the discovery job returns (`scripts/synthesis_research.py`).
- **Presentation Studio.** "Research it first" switches research on; for a document it
  then asks "Where may research look?" with "Your documents only" or "Your documents and
  the public web" (`research_sources`: `documents` | `both`). The research plan's `scope`
  is `supplied-only` or `public-web`.
- **Training Studio.** Step 3 of the form asks for `sources`: `public`, `documents` or
  `both`.

The worker tools that save pages (`runner/worker_tools.py` in both deck studios,
`blog_library.fetch` in Blog Studio) refuse private addresses, but nothing narrower.

## The choice

Where research may look is up to three combinable choices:

| Choice | What it means |
|---|---|
| **your documents** | The files supplied for this piece of work, as today. Applies only when documents were given. |
| **your sites** | A list of base URLs. Pages are saved only from under one of them. |
| **the public web** | Any public page, as today's web-allowed / public research. |

At least one choice that applies must be on. A run saves the choice as

```json
"research_from": {"documents": true, "sites": ["https://blogs.vmware.com/tanzu"], "web": false}
```

`sites` empty means your sites are off. The run pins the exact list it used: a later change
to the shared list never changes a run that has started.

### Old saved runs stay readable

`studio_core.research_sites.legacy(value)` maps every older wording onto the new shape:

| Old value | New shape |
|---|---|
| Blog `supplied-only`, Presentation `documents`, Training `documents`, plan `supplied-only` | documents |
| Blog `web-allowed`, Presentation `both`, Training `public`, Training `both`, plan `public-web` | documents + web |
| Blog `none` | no research (Blog Studio keeps its research stage switch) |

Documents only applies when documents were given, so an old Training `public` run without
documents reads as "the public web".

## Your sites: the shared default list

The default list lives in Marketing Studio's shared settings, in the existing studios
config file, under `research.sites`:

```json
"research": {"sites": ["https://blogs.vmware.com/tanzu", "https://docs.example.com"]}
```

A site is a canonical `https://host[/path]`:

- https only (a bare `host/path` is read as https); no query, fragment, user name,
  password or custom port;
- the host is a public name: no IP literal that is private, loopback, link-local or
  reserved, no `localhost`, no single-label name, no `.local`, `.localhost`, `.internal`,
  `.lan`, `.home.arpa` or `.test`;
- the host is lowercased, the path keeps its case, loses its trailing slash and may not
  hold `.` or `..` segments;
- the list is deduplicated, keeps its order and holds at most 50.

Each site is shown as `host/path` (`blogs.vmware.com/tanzu`).

`core/studio_core/preferences.py` validates and canonicalizes the list on save, through
the studios config's lock, preserving unrelated values. A form that read an outdated list
is refused ("Another studio changed your research sites. Reload the page and try again.")
by the same leaf guard every other shared setting uses.

Marketing Studio's Shared settings page (and the same page inside each independently
launched studio) gets a **Research sites** card: the list as `host/path` rows with
Remove, and an Add field. It is shown in Shared settings, not in first-run setup.

## Each start form

Each studio's research control reads the same way:

> Research from: ☑ your documents ☑ your sites (3) ☐ the public web

- "your documents" appears only where documents can be given, and is checked by default
  when they are;
- "your sites (N)" opens the shared list prefilled, a checkbox per site, and an
  "Add a site for this piece of work" field that does not change the shared list;
- with nothing that applies checked, the form says "Choose where research may look: your
  documents, your sites or the public web." and does not start.

The stops/summary line names the sites: "Research from your documents and 3 of your sites
(blogs.vmware.com/tanzu, docs.example.com, …)", built by `research_sites.summary()`.

## Enforced at capture

Every place a research job saves or fetches a page asks
`research_sites.refused(url, choice)` on every hop, redirects included:

- with your sites on and the public web off, a URL is allowed only when it is https, its
  host equals a listed site's host exactly (case-insensitive, no subdomain or lookalike
  such as `blogs.vmware.com.evil.example`), and its decoded path equals the site's path or
  continues it at a segment boundary (`/tanzu/x` is under `/tanzu`; `/tanzu-other/` is
  not). A path holding `.`/`..` segments or an encoded slash is refused;
- with the public web on, any public URL is allowed;
- the existing private-address refusals stay in every case.

A refused URL is answered with a sentence naming the allowed sites, so the worker can
correct itself: "That page is outside the sites this research may use, so it was not
saved. Save pages from under: blogs.vmware.com/tanzu, docs.example.com." A redirect off
the sites names where it led.

| Studio | Where |
|---|---|
| Presentation Studio, Training Studio | `runner/worker_tools.py`: `save_source` → `_checked` on every hop; `prepare(..., research=)` writes the choice into `job.json` |
| Blog Studio | `blog_library.fetch(url, scope)` takes a `research_sites.Scope` and re-checks every redirect; `synthesis_research.py` discovery passes it and keeps refusals as source limits |

## Guidance to the worker

`research_sites.guidance(choice)` gives the worker:

- with your sites on: search the listed sites first, with `site:` queries
  (`site:blogs.vmware.com/tanzu …`) or the site's own search page when the tool offers it;
  save pages only from under the listed sites;
- with the public web also on: use the wider web only for gaps the listed sites leave.

Harness Research's `source_mode` stays `public` / `selected` / `mixed`. Pages from your
sites are public captures (permission `public`), so documents + sites is `mixed`, sites
only is `public`, documents only is `selected`. The research plan's `scope` stays
`supplied-only` / `public-web`: any choice with sites or web is `public-web`. The task's
`scope` text names the allowed sites (`research_sites.scope_text()`), and the run records
them in `research_from`.

## The research gate

When a capture was refused, the research gate and the refusal copy name the sites
("2 pages were outside your sites (blogs.vmware.com/tanzu) and were not saved").

## Out of scope

- Crawling a site or reading its sitemap: the worker searches and saves pages one by one.
- Per-studio editing of the shared list: each studio's form edits the list for one piece
  of work only; the shared list is edited in Shared settings.
