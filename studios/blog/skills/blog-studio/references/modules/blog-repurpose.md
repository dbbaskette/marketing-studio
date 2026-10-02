# Repurposing capability

Keep private inputs in the user's existing harness and selected private hub.
Apply [data boundaries](../privacy.md) before research, media, or document
posting; upstream suggestions do not authorize external disclosure.

**Input:** complete source article, voice, requested channels/length, actual post
URL if available.
**Output:** channel-specific text plus length results and any unresolved links.

Support LinkedIn feed posts/articles, X threads, newsletter intros, announcement
emails, TL;DR, metadata, and shorter/longer article variants. Load only the chosen
channel conventions. Use current host/platform limits when material; verify
changeable platform constraints rather than treating old prompt limits as law.
Editorial length targets are preferences, distinct from platform hard limits.

Preserve the original argument, essential evidence, facts, and voice. An expanded
version develops existing reasoning rather than inventing experiences or data.
A summary cuts repetition/secondary detail before essential qualifiers. Threads
have a readable sequence and useful standalone items. Newsletters/emails lead
with why the article matters. No invented live URL or automatic brand promotion.

Measure actual words/characters using `scripts/text_checks.py count`. Make one
focused correction if outside a requested range; report a remaining mismatch
honestly. Save derived artifacts separately from the original manuscript.
This operation prepares copy; posting or sending requires separate authorization.

Adapted from BlogForge `generate/repurpose.py`. Existing [copywriting](copywriting.md)
and [content strategy](content-strategy.md) can supply detail when actually needed.
