# C04 active counts: conservation selected

Status: user decision received and implemented, 2026-10-13. The user explicitly
chose to preserve total active drone counts during split/merge, matching F08.03.
This is the approved exception to the pinned desktop split/merge active-count
behavior; all calculations still use pinned EOS. No unrelated scope changed.

| Operation | Before (stored/active) | Implemented conservation |
| --- | --- | --- |
| Split two | 5/3 | Original 3/1 + new 2/2; total active 3 |
| Merge into inactive destination | source 2/2, destination 3/0 | destination 5/2 |
| Merge into active destination | source 2/0, destination 3/3 | destination 5/3 |

Within the chosen policy, the implementation allocates active drones to the moved
stack first: `min(requested amount, original active)`. It was announced before
implementation and is explicit in independent literal expectation tables. The
original stack retains all remaining active drones. A split must leave at least
one stored drone in each resulting stack. The new stack is appended with a fresh
identity, while the original identity remains unchanged.

A merge sums stored and active counts, retains the destination identity and
removes the source. Only the same item, base, mutaplasmid and exact rolled values
can merge; distinct rolls stay separate. Self-merges and total count overflow
reject atomically. Clone behavior remains pinned desktop behavior.

[Machine decision](../evidence/c04-conservation-decision.json),
[independent expectation fixture](../../../tools/android_reference/fixtures/drone-conservation.json),
and [host evidence](../evidence/c04-conservation-development.json) retain the policy
and validation. [Historical desktop boundary witnesses](../evidence/c04-desktop-boundaries.json)
remain unchanged and explicitly show why the exception was needed.

The semantic blocker is resolved. F08.03 acceptance remains pending native and
full exact-candidate verification; approval is not a test pass. Heavy execution
awaits dot's fresh shared-memory check and explicit slot grant. No merge, release
or publication is authorized.
