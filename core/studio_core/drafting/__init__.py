"""Blog Studio's desk parts, shared so every studio's desk keeps text by the same rules.

An item on a desk is a title, an opening and sections (or, through another codec, slides),
each a part with its own versions. The modules here are the rules for keeping that text:

- `store`: the object a studio passes in for its own folders, lock and writes;
- `parts`: splitting Markdown into parts and joining them back, and the codec;
- `record` and `versions`: the per-part check, saves, History and removed parts;
- `basis`: a job's result lands only while its part is unchanged;
- `prompts`: the edit rule and the scope sentences a desk job is asked with;
- `guards`: whether a rewrite changes a fact or the part's structure;
- `proposals`: Finishing's suggestions, applied or skipped by the person;
- `findings`: a review's findings as proposals whose Apply is a note on their part;
- `proofread`: the in-process mechanical checks.

Core never imports a studio, reads no settings and starts no job: each studio passes its
store and codec, and keeps its own job queue, screens and writing context.
"""
