# Style storage

Use the [workspace](../workspace.md) command prefix. A style is the shape of a kind of
writing, apart from who writes it; a [profile](profiles.md) is one author's voice. The
eight starter styles for tech-industry writing are listed from the start (`list styles`
and the page) as confirmed, editable styles. A starter is copied into the workspace only
when it is saved, retired or used for a blog; reading never writes. Until then
`style show` returns `guide: null` and the starter's text as `guide_text`.

```text
... list styles
... style create --name <kind> --guide-file <guide> --sample <source-id>
... style save --id <style-id> --guide-file <revised-guide> --status confirmed
... style show --id <style-id> --revision <number>
... style retire --id <style-id> --expected-revision <number> --confirmed
... run create ... --style <style-id>
```

Samples must be ready and classed `style-sample`; one post may be both a `voice-sample`
and a `style-sample`. Learn a style from examples of the kind by anyone: describe
structure, moves, length, headings and register, never the author. Save it provisional
until the author confirms. A run pins a style revision; later saves do not move it.
Where a style and a voice conflict on wording, the voice wins; on structure, the style
wins.

Links to public examples arrive through `library voice-links --purpose style-sample`
(no byline check, no author needed) or the page's **Add links to examples**. A source
that is already a sample for a voice becomes a style example with **Use as an example**
on the page; nothing is fetched again.
