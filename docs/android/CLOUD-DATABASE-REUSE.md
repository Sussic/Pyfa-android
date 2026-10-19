# Bounded cloud build database reuse

`android/prepare-engine.py --reuse-only-database PHYSICAL_CACHE
--reuse-sha256 TRUSTED_SHA256 --reuse-bytes TRUSTED_SIZE` permits a candidate-local
`android/build/engine/assets/engine/eve.db` symlink to an exact verified previous
cloud candidate cache. Supply identity from the earlier trusted receipt, never
from a newly invented manifest. The optional cloud mode confines the physical
cache to `/workspace/shared` and leaves original file permissions unchanged.

Reuse and build modes are mutually exclusive. Reuse has no regeneration fallback:
missing/corrupt/wrong-target/physical/logical identity fails closed. SQLite reads
are read-only; pending WAL, SHM or journal sidecars reject. Normal preparation and
direct database building also refuse symbolic-link destinations or ancestors and
multiply linked files, so omitting reuse mode cannot regenerate through the link.
Physical identity is checked before and after logical verification. Keep the cache
quiescent, with no concurrent writer: these are preventive program guards, not
an OS write lock. The original private build database remains preserved.

All generated Python, manifests, test assets and build outputs must remain in
physical candidate-local directories. Do not point staging ancestors at another
candidate. Record before/after cache hashes around staging and compilation. This
mode changes no acceptance criteria and cannot supply missing frozen fixtures.
Private regular-file builds retain the normal verified-regeneration behavior.
