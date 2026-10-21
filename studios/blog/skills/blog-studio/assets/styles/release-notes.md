---
name: Release notes and changelog
summary: Grouped, scannable changes with version, dates and upgrade notes.
---
# Release notes and changelog

A reference a reader scans to find out what changed and whether it affects them. It is
read by people upgrading, debugging, or deciding when to move.

## Shape

1. **Heading**: product, version and date.
2. **Highlights**: at most three changes worth a sentence each, when a release has them.
3. **Grouped changes**: short headings such as Added, Changed, Fixed, Deprecated, Removed,
   Security. One line per change: what changed, where, and who notices. Link each to its
   documentation or issue when the material supplies one.
4. **Upgrade notes**: anything a reader must do, in order, with the consequence of
   skipping it. Breaking changes are named as such and listed first.
5. **Known issues**: what is still open, with a workaround when one exists.

## Length and register

As long as the changes require and no longer; most entries are one line. Neutral,
exact, past tense for what changed and imperative for what the reader must do. Same
wording for the same thing across releases.

## A reader expects

- To find their area by scanning headings, not by reading prose.
- Every breaking change flagged and placed first.
- Versions and dates they can match to what they run.

## Does not belong

- Marketing framing or adjectives.
- Internal refactors that change nothing a reader can observe.
- Promises about future releases.
