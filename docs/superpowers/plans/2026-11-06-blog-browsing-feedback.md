# Blog Studio browsing feedback

Issue #413; authorized audit implementation and PR merge.

The task path is list → search/filter → matching items or a recoverable empty
result. Filtered results must not pretend the underlying collection is empty.
Show “No matching items” with “Clear search and filters”; clear the current view's
actual controls and pagination, reload, and return focus to Search. An obsolete
page has a separate first-page recovery. Genuine empty collections retain their
onboarding copy; existing unreadable-item notices remain visible.

The three-second native run poll skips hidden tabs and catches up when the tab
becomes visible. Hiding an editing desk still performs its existing share/save
work. No server job, save cadence, provider behavior or readiness changes.

Verification covers four filtered views, real filter/offset reset, stale response
ordering, hidden request counts and return-to-tab refresh. A real native browser
journey checks keyboard focus, no-match recovery and visibility event wiring.

The complete Blog Studio offline suite passed in the shared disposable Tart
runner: 1,878 tests from 72 files, four at a time (171 seconds), plus pinned lint,
format, package/guidance and management-client checks. Environment: macOS 27.0,
Python 3.13.15, Node 22.23.2. The native browser observed zero reads across five
hidden ticks and one catch-up read on visibility; no-match recovery and focus
passed at 390/1280px. All 47 shared layout/UI checks passed. The VM was deleted.
No live content, provider access or paid work was used.
