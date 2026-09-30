# B08 — Fit notes

Selected 2026-09-30 on `codex/b08-fit-notes` from delivered master `93d020de`.
Live default master and no open PRs verified. B03 is done; this task owns F01.06.
Deliver multiline Unicode notes for the correct fit, durable copies/restart and
preservation of pending text across navigation and activity recreation. Keep the
existing serialized EOS bridge, declarative graph store and native Compose UI.

## Original behavior and bounded decisions

The pinned `NotesView` edits plain multiline text, delays saves by one second,
flushes the previous fit when switching, normalizes absent notes to empty display
and shows an optional character count. `service.fit.Fit.editNotes` assigns the
exact text and commits; EOS copies notes with a fit. The desktop pane is disabled
for structures. Preserve that UI boundary and exact whitespace/Unicode, including
empty notes; retain existing structure notes in saved graphs/copies without adding
an unrelated structure editing capability. B09 owns undo/redo; note saving itself
uses the original non-command service path.

- [x] Inspect pinned notes pane, edit service and copy behavior; select scope.
- [x] Export independent original service/pane cases and repeat in fresh processes.
- [x] Add strict note operation/query and optional durable graph input, preserving
  old graphs, copies, independent fits and unchanged fitting results/history.
- [ ] Add multiline editor with one-second autosave, explicit save, navigation
  flush and retained drafts on errors/recreation; never apply text to another fit.
- [x] Verify exact empty/whitespace/non-ASCII text, stale/malformed and failed-save
  rejection, linked fit isolation, legacy graph replay and fresh-process restart.
- [ ] Native offline touch checks cover typing, quick navigation, switching fits,
  recreation, copies/reopen, structure availability and errors; inspect screenshots.
- [ ] Pass required final-head host/native CI, review and merge the focused fork PR,
  retain exact evidence, update checkpoint and advance to B09.

No release, phone installation, new editor framework or unrelated refactoring.

## Implementation and focused verification

The independent original service, pane event methods and EOS copy repeat three
fits/13 states. The pane uses inert text/timer ports and real wx events/SQLite;
this verifies original save routing, not wx rendering or TextCtrl newline changes.
An absent fit ID raises the original `TypeError`; Android's editor never submits
without a fit. No original method body is rewritten.

Four focused host tests pass exact multiline/whitespace/empty/combining/emoji text,
character counts, independent copies and fits, unchanged calculations/history,
linked fit isolation, malformed and stale rejection, failed-save recovery,
legacy graphs and five-fit fresh-process restart. No desktop imports or network
attempts occur. The serialized note operation/query, optional graph input and
retained Compose drafts are implemented. Main/instrumentation Kotlin compilation,
both final APKs/lint (1m34s) and 162-source/pinned-data/license/ABI package inspection
pass after review refinements. The native gate is prepared with an explicit durable flag and initial
suite exclusion, 85/90 fit-count guards, ten protocol rejections and seven screens.
Its execution and screenshot review remain required; no native success is claimed.
