# Training Studio overall progress map

The user approved implementation of the map proposed in issue #392, followed by
push, pull request and merge. Use the Golden Gate v2 language already applied to
the desk. No provider jobs, user-state edits or app restart are part of verification.

## Contract and implementation

1. Add a read-only projection of the existing survey, saved approvals, material
   cards and observed run state. Reuse these values; do not add file reads, worker
   requests, timers, storage or a second scheduler. Report actual counts, never
   an overall percentage or ETA.
2. Show Outline, Research, Materials and Your review. Older researched-topics runs
   show Research then Teaching plan; conversation-only desks show only retained
   materials and review. Generation and creator readiness are separate.
3. Stage buttons disclose details without starting work. Materials groups selected
   plans/guides/briefs, practice/Yoodli and slides; each item shows its own state and
   opens the existing material. Completed drafts remain reachable during later
   work. Research acceptance with creator flags retains an explicit warning.
4. Preserve selected detail, focus and scroll during polling. Fit a compact map on
   a phone, use semantic buttons and explicit text states, and keep selection
   distinct from focus. Details are optional; existing recovery/approval controls
   stay authoritative.
5. Verify projection edge cases and native journeys, inspect populated light/dark
   phone/desktop states, then run the relevant Training Studio suite in Tart.
   Update the README and flow guide with the implemented behavior before merging.

## State-transition matrix

| Saved/observed state | Map result | Verification |
| --- | --- | --- |
| Outline awaiting approval | Outline needs you; research waits | Native outline journey |
| Slot/source wait | Waiting/Needs you, no invented active worker | Projection tests |
| Research collecting/writing/checking | Research current phase and actual area counts | Projection tests |
| Creator choices accepted | Research accepted with flags, warning retained | Projection and browser |
| One guide active, peers queued | Materials working; separate branch/item states | Native progress journey |
| Deck approval pending | Slides needs you; readable peers stay available | Native deck integration |
| Cost/time/problem stop | Owning stage stopped with recorded explanation | Projection and browser |
| Queued update with prior file | Prior draft remains openable; not complete/ready | Native standing regression |
| Drafts complete, not marked ready | Materials complete; Your review needs you | Native standing regression |
| All selected materials marked ready | Your review complete | Native standing regression |
| Conversation-only retained work | Saved material/review map, no synthetic history | Projection test |
| Stage/item clicked or poll arrives | No jobs started; focus/disclosure retained | Browser journey |
