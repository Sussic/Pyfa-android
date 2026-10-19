# G08 read-only warp evaluation prerequisite

Source inspection after G07 identified a technical prerequisite, not an owner or
device-test permission gate. `fitWarpTime/cache.py` temporarily changes active
module, projected-fit/module/drone/fighter state to obtain warp-eligible subwarp
speed. It restores and recalculates before `getter.py` reads normal warp speed.
Copying this helper onto live objects is not a safe read-only graph operation.

Current HeadlessEngine is one global EOS saveddata session per process.
`create_fit` adds/flushes it; BridgeSession `_rebuild` resets storage and identities;
Fit `__deepcopy__` can flush/refresh linked sources. Swapping only eos.db's session
is insufficient because saveddata query/relationship modules retain aliases and
explicit flush paths. Do not use any of these as an isolation shortcut.

A bounded next design is a detached saved-input graph builder with entirely new
characters, additions and relationships, no add/flush/commit, no live saveddata
references and no Fit deepcopy. Use the existing serialized worker and discard
scratch objects. Prove pending ORM new/dirty/deleted sets, attribute histories,
live identities, durable bytes, revisions and history are unchanged under success,
calculation error and cancellation before integrating G08. This prerequisite can
be implemented later; independent C05 fighter editing is currently ready.

The future warp contract must retain normal-state maxWarpDistance/warpSpeed while
obtaining disabled-state subwarp speed only. Normalize distance to metres, clamp
both endpoints separately per fit to [0,maxWarpDistance*AU], sample 500 intervals,
and denormalize x back to AU/km. Different fits may have different effective
bounds/counts; equal or underflowed-step ranges yield a singleton. Original default
ranges are 0–50 AU and 150–5000 km. y is warp-only seconds, without align time.
