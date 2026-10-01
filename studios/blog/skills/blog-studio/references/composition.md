# Coherent composition

Use the original [blog-write module](modules/blog-write.md) for article craft,
and the [argument-outline module](modules/blog-argument-outline.md) for structure.
Compose the complete argument with the outline and selected evidence in view.
Each section advances prior reasoning rather than restarting the thesis.

Preserve author-supplied or approved headings/order unless restructuring is
requested. Avoid repeated examples, metaphors, openers, and summaries. Vary
section entrances; budget detail according to substance rather than equal-length
sections. Keep author voice and factual boundaries stable. Cite verified claims
near their support; label missing evidence outside the finished prose.

The [BlogForge composition prompt](blogforge/generate/prompts/document.j2) is
conditional reference material, not a required Jinja runtime. Its splitter-driven
H2 and separate-hook requirements are implementation details: use the requested
article format here and include the opening exactly once.

First-draft mode may build an internal outline and continue. Outline-only stops
before composition. If the brief is already clear, do not force research quotas,
media, FAQs, CTAs, or an extra approval. Save the draft and checkpoint.
