# C10.F14.02.READER-PROCESS1

Correct the finite EOS verifier's Windows virtual-environment process launch.
The original 9bf candidate and failed MSI queue189 remain frozen evidence.
This derivative changes verification code only; application behavior, original
oracles, tolerances, atomicity, history and reconstruction assertions remain.

The Windows venv redirector creates an intermediate process, invalidating the
original reader's immediate-parent assumption. Use the pinned CPython3.11.9
multiprocessing pattern: launch the base executable with child-only
__PYVENV_LAUNCHER__ pointing to the qualified venv executable. Keep both strict
direct-parent and actual-reader-PID-equals-Popen-PID assertions. Match creation
time from the retained Popen handle and retain the exact writer process handle
before and after graph reconstruction. Record the outer writer's pinned launcher
parent separately for canonical guard linkage.

Shared windows_venv_identity.py validates interpreter image, venv/configuration,
package metadata and process birth/liveness without creating another Job or
changing resource policy. Its any-job query is corroboration; containment and
actual closure remain the unchanged canonical guard's responsibility.

The exact helper and metadata probe passed on qualified MSI CPython3.11.9 x64
through the unchanged canonical light guard. Raw INPUT/CHILD/RESULT and guard
receipts were copied and independently hash-verified on Initia. Direct PID/birth,
runtime retention, live writer snapshots and actual root/tree zero closure were
reviewed. This establishes the process route only. The corrected finite
module+drone EOS run, native seed and all Android/fullC10 acceptance remain pending.

References: CPython v3.11.9 Lib/multiprocessing/popen_spawn_win32.py lines55-60;
Microsoft GetProcessTimes, QueryFullProcessImageNameW and WaitForSingleObject.
Keep raw JSON integers and byte hashes; creation FILETIME exceeds JavaScript's
exact-number range. Future reruns require fresh output and canonical admission.
