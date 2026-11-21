---
name: presentation-studio
description: Make a slide deck in your organisation's brand from an idea, a document or an existing deck, one approved step at a time, with harness-slides, harness-research and your brand skill. Use to start, resume, check or revise a deck kept under presentations/.
---

# Presentation Studio

This entry finds the guidance for making a deck in this conversation. A new deck takes the newest guidance. A deck in progress keeps the instructions it was saved with, and always runs the installed scripts.

1. From the directory the harness was launched in, run this command, which the installer wrote:

   ```sh
   ~/.local/share/presentation-studio/presentation guidance start
   ```

2. It prints JSON. If there is an `error`, show it and stop; do not improvise guidance. If there is a `notice`, tell the user once.
3. Read the file named by `entry` and follow it. Its links are relative to that file. `helper` is a command: wherever guidance says to run the helper, run `helper` itself, as in `"<helper>" status`. Never put `python3` before it.

Nothing needs doing after an update: a deck carries on by itself. Only when the user asks to move a deck to newer guidance: run the same command with `update` in place of `start`.
