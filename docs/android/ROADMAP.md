# Android task queue

[STATUS](STATUS.md) is the single current execution entry point and owns the
pause/authorization, candidate and next action. This roadmap owns feature state,
scope, dependencies and delivery order. Readiness does not authorize execution.
Only one implementation outcome is active by default. States: ready, queued,
active, blocked, paused, verified-local, done. Verified-local means required
local proof is complete but reserved external delivery is pending; it may satisfy
a technical dependency on the same validated inputs, not publication/release.
Completed setup is not an implementation milestone.

## Current bounded outcome: reconciled starting point — 19 October 2026

The authoritative working copy, its composition and all verification results are in [STATUS](STATUS.md) ("Start here"). D05.4 is closed
(archive SHA256 `f91cb91c…`, independently verified) and D04.2 pilot security is an audited source/evidence package
(`ACCEPTED_AUDITED_SOURCE_AND_EVIDENCE_HANDOFF_WITH_QUALIFICATIONS`; compile-only, no APK or device claim). Earlier "package pending" statements below are historical.
No new feature is selected; the next action is the verification-gap closure listed in STATUS. Readiness does not authorize execution.

### Reconciled feature inventory (19 October 2026)

Legend. Implementation: **impl** = code present in this variant, **partial**, **none**. Host/ref = synthetic or host tests and independent desktop-reference comparison.
Native = Kotlin compile, emulator instrumentation or device. "Cloud" = compiled/tested in the cloud lane at an earlier source, not on this variant.
Historical = earlier candidate commits; applicability to this variant is not established. Live acceptance (owner usability) is **none** for every row.
Missing evidence means unknown, not unimplemented.

| Family (tasks) | Intended behaviour | Implementation | Host/ref verification | Native/device verification | Source / manifest | Evidence | Remaining work | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 library, search, notes (B02, B03, B08) | Save, search, duplicate, filter and annotate fits offline | impl | historical, done | historical emulator; not re-run here | merged manifest | tasks B02/B03/B08 | desktop tags/folders not found (Q01) | include in R01 |
| F02 fitting, charges, modes (B04, B06) | Modules, rigs, charges, hull modes, subsystems, structures | impl | historical, done | historical emulator | merged manifest | tasks B04/B06 | none known | R01 |
| F03 bulk edit, undo (B05, B09) | Multi-select ammunition/state/variation changes with undo/redo | impl | historical, done | historical emulator | merged manifest | tasks B05/B09 | mixed-family bulk coverage open | R01 |
| F04 cargo (B07) | Cargo stacks, transfers, presets | impl | historical, done | historical emulator | merged manifest | task B07 | none known | R01 |
| F05 resources, capacitor, defenses (C01) | CPU/PG, cap, resists, EHP, tank | impl | historical, done | historical emulator | merged manifest | tasks C01 | none known | R01 |
| F06 output stats (C02) | Firepower, bombs, mining | impl | historical, done | historical emulator | merged manifest | task C02 | none known | R01 |
| F07 targeting, attributes (C03) | Targeting, navigation, full item/ship attributes | impl (C03.2 verified-local) | historical, done | historical emulator; C03.2 delivery unpublished | merged manifest | tasks C03 | C03.2 delivery step | R01 |
| F08 drones (C04) | Stacks, split/merge with active counts, bandwidth, control range | impl, integrated (not missing) | host and reference proof; approved active-count conservation | Kotlin debug APK built earlier; **native acceptance not achieved** (API36 diagnostic guest ANR; that guest's ownership/source state is incompatible) | merged manifest (11 owner C04 files identical) | task C04 and plan | native acceptance, F08.04/F08.05 evidence | C04 native plan on a compatible guest |
| F09 fighters (C05) | Squadrons, abilities, recent/similar selection | impl | cloud host proof | cloud compile; device open | merged manifest | tasks C05 | device gates | emulator acceptance |
| F10 character profiles (C06) | Offline skill/security profiles, requirements | partial (profiles/history integrated; requirements/affectors need native acceptance) | host proof | cloud compile; device open | merged manifest | OFFLINE-INTEGRATION | native acceptance, skill refresh (ESI) | native acceptance |
| F11 implants (C07) | Fit-local implants, shared character implants, detached sets | partial (C07.1–C07.3 cloud reviewed/compiled) | cloud host proof | compile only | merged manifest | C07 docs | device gates | emulator acceptance |
| F12 boosters (C08) | Boosters and side effects | impl | cloud host proof | cloud compile; device open | merged manifest | C08 doc | device gates | emulator acceptance |
| F13 heat, spool, reactive armor (C09) | Spool override, heat detail, built-in RAH | partial (C09.1/C09.2) | cloud host proof | compile only | merged manifest | C09 docs | broader module options | emulator acceptance |
| F14 mutated items (C10) | Edit rolled attributes of mutated modules and drones | **none** (queued; no editor) | none | none | — | ROADMAP row | all | schedule after verification gaps |
| F15 projections (D01, D02) | Projected modules/fits/drones/fighters, ranges, linked recalculation | partial (D01.1–D01.9 impl) | finite reference parity (D02.1, D02.2) | compile only | merged manifest | D01/D02 docs | individual/bulk and interaction coverage | D02 qualification |
| F16 command fits (D03) | Saved command fits and bursts | partial (D03.1) | cloud proof | compile only | merged manifest | D03 doc | broader editor | later |
| F17 environments, security (D04) | System and pilot security, environment effects | partial (D04.1 structure security; D04.2 pilot security) | D04.2: 629 host methods planned, 601 pass here; numerical 203 observations accepted in the audited package | compile-only in cloud; none here | merged manifest | D04-1 doc, D04.2 package receipts | wormhole/weather/environment editor not implemented | decide scope |
| F18 patterns, profiles (D05) | Named target profiles, incoming damage patterns, Selected Ammo, local RAH | partial (D05.1–D05.4) | cloud proof | compile only | merged manifest | D05 docs | global/default profiles, interchange | later |
| F19 graphs (G01–G11) | Every graph family with fit comparison | partial: impl G03, G04, G05, G06, G07, G09; **none** G01, G02, G08, G10, G11 | finite reference parity for implemented families | compile only; execution open | merged manifest | G docs | five families, shared actions | G08 prerequisite, then G01/G02 |
| F20 interchange (I01, I02) | EFT plus DNA, XML, EFS, multibuy, CSV, HTML, skills/profile formats | partial: EFT import/export (I01); **none** I02.01–I02.08 | host proof for EFT | compile only | merged manifest | I01 doc | all non-EFT formats | after C10 |
| F21 ESI, prices (I03, I04) | Optional online sync and cached prices | **none** (optional, requires network) | none | none | — | ROADMAP rows | all | later, optional |
| F22 preferences (I06) | Calculation/display defaults, overrides, localization | **none** except task-specific settings | none | none | — | ROADMAP rows | all (including global defaults) | later |
| F23 data and backup (A07, I05, R02) | Bundled data; refresh, backup/restore; upgrades keep fits | partial: bundled data (A07); **none** refresh/backup | A07 only | A07 x86_64 historical; ARM64 and upgrade-over-data unverified | merged manifest | A07 receipt | I05, R02 | later |
| Release (R01–R04) | Full offline audit, packaging, device review, final build | none | — | — | — | ROADMAP rows | all | last |

Offline core means F01–F20 (without the online parts of F20/F21); F21 and the refresh half of F23 are optional online capabilities.

## Superseded outcome (historical): D05.4 package closure and D04.2 planning — 18 October 2026

D05.4 local named RAH has accepted source, Python/current-source reuse, finite candidate and actual native codec/wire proof. Main/instrumentation Kotlin compilation passed; final package remains pending; [STATUS](STATUS.md) owns the single next action. Complete the distinct docs-only delivery freeze, eleven direct cumulative reconstruction routes, archive audit and Library round-trip before selecting another implementation. Earlier G05.2 downloads/hashes were verified at 15:28 UTC and isolated local integration was underway at 15:47 UTC; no manual-transfer request is pending for that batch.

After D05.4 closure, the next bounded design is D04.2 pilot security plus its necessary C06 character-security inheritance field. Freeze original semantics, defaults/copy behavior, source/schema representation and actual six-hull fixture availability before coding. This does not open all environments, change graph requirements or waive device acceptance.

## Earlier integrated scope (historical) — 17 October 2026

The initial C06 profiles/history, atomic-import portion of I01, and G03 capacitor
sampling were one explicitly authorized native-source integration outcome. See
[the integration contract and qualification boundary](OFFLINE-INTEGRATION.md).
Source implementation and host proof do not close their native acceptance gates.
I01 outbound export/copy/save/share is integrated and cloud compiled; full
interchange coverage and native acceptance remain open. The bounded importer
does not claim the whole milestone. C06 requirements/
affector inspection still needs its existing native integration acceptance.
Native compilation has passed. Deferred device qualification remains an acceptance
gate, not a blanket implementation gate. Continue dependency-ready, integrated
capabilities with focused tests, native compilation and independent review; keep
unfinished work bounded. C05 fighter Recent-use/context refresh and its separate
broad host/source integration proof are reviewed. Source-backed similar-fighter selection is also reviewed and cloud compiled,
retaining the same-type action. D01.1 saved-fit projection management is now
reviewed and cloud compiled, including original command-policy semantics and
LOCAL cache boundaries over the existing durable link graph. Its remaining
individual-object/bulk and D02 interaction coverage are open. D03.1 saved command-fit management is also reviewed and cloud compiled using
existing profiles and fit-local implants. D01.2 single-row individual projected
modules is reviewed and cloud compiled with optional durable records/identities,
exact history, source-reference numerical proof and fresh-process restoration.
D01.3 single-stack projected drones are integrated and source-reviewed with measured
active-count/operation-specific admission, full host and runtime regressions;
main and instrumentation Kotlin compilation passed. D01.4 selected projected-module
bulk state/range/removal is integrated and independently source-reviewed; all 176
host methods passed across bounded chunks and mobile-runtime restart passed.
Main and instrumentation Kotlin compilation passed; eight new native methods
remain unexecuted. D01.5 selected incoming-drone activation, nullable range and
remove-stacks are reviewed and cloud compiled, with all 182 host methods passing
in planned bounded chunks and eight original-command methods plus fresh-process
restoration passing. Nine new native methods compiled only. D01.6 incoming fighter
squadrons are integrated and independently reviewed with ordered records, complete
ability states, duplicate identities and audited grouped-effect admission. Eight
original-command methods, all 195 host methods in seven bounded chunks and actual
runtime fresh-process restoration passed; main and instrumentation Kotlin compiled.
Ten new native methods remain unexecuted. D01.7 selected incoming-fighter
activation, range, complete removal and main-driven ability toggling are reviewed
and cloud compiled. Eight independent original-command methods, all 202 host methods
in seven bounded chunks and actual-runtime fresh restart passed. Twelve new native
methods compiled only. D01.8 incoming same-type/similar selection is reviewed and
cloud compiled, with a bounded metadata-only query and exact identity/epoch guards.
Eight independent original-helper methods, all 209 host methods in seven bounded
chunks and actual-runtime fresh restart passed; nine new native methods compiled
only. D01.9 selected projected-module ammunition/script load/clear is integrated,
source-reviewed and cloud compiled, with explicit selection/similar scope,
source-filtered preview and one transaction. Seven focused and eight independent
methods, all 216 host methods in eight bounded processes, and actual-runtime fresh
restart passed. Nine new native methods compiled only. D02.1 multi-source EWAR parity is now source-reviewed and cloud compiled:
16 processes, 138 stages, 551 full-fit snapshots and 21,489 stat comparisons passed;
all 324 inherited source/test bindings stayed exact. One new native method compiled
only. D02.2 remote-support parity is reviewed and cloud compiled:142 stages,426 full
observations, six populated restarts plus legacy reopen,216 rerun host methods and
one new compiled-only native method. Durable projection order is preserved.
G05.1 repair rate versus distance has a reviewed source/host/compile checkpoint. G04 complete shield graph is independently source-reviewed and cloud compiled:608 supported curves/119,008 points,107 host methods and22 compiled-only native methods. G05.2 now has reviewed source, finite original parity, host proof and cloud compilation for selected-time distance rate, amount-distance, rate-time and amount-time. Its external package receipts and all packaged member hashes passed local verification; one exact direct G04 route passed before local documentation and harness reconciliation. Android execution and full qualification remain open.
G09 now implements all seven original EWAR-distance modes, complete 1–8-fit
comparison, original null units and nullable/clamped resistance on the shared plot.
Source reviews and 15 actual host-JVM contract methods plus 1,656 original-sampler/
mutation cases passed. Independent finite seven-family parity audit passed
5,128 curves / 88,410 points, with 5,206 exact wire pairs retained under the
reconstructed/supplemental source qualifications. Actual-codec host acceptance and
byte audit passed a finite 1,262 retained pairs: 1,259 successes, three complete
errors and 59,892 points, with zero skipped pairs. This is not all 5,206 parity
wires. Independent resource/lifecycle audit accepted ten successful lanes with
55 wires / 156 original-equal series / 11,536 points, including nine actual states,
undo/redo and fresh reopen. Failed harness attempts remain retained. Receipt
`REVIEW-G09-SUPPLEMENTAL-EVIDENCE.json` is bound by SHA256
`900b195f7c06c8bd947182334bc599ea4e8cc42aa956a579d467d1a593945312`.
All 225 affected host methods passed exactly once in 12 bounded chunks without
skips and with unchanged inputs. Guarded main/instrumentation compilation passed
33 tasks in 164.065 seconds without a guard trigger; 30 native methods compiled
only, with no Android execution. The exact 965-entry compile manifest remains in
`COMPILE-SOURCE-FREEZE.json`; final documentation rebind and exact-byte package
verification are pending external receipts, not inferred from compilation.
See [the G09 contract](G09-EWAR-DISTANCE.md).
Mixed-family bulk and broader interaction coverage remain separate source/schedule
audits. Shared
character implant collections are not required for the completed D03.1 subset.
Character collections and named sets remain separate dependencies. The owner
reauthorized MSI development and prefers emulator qualification. The isolated local
candidate now includes G05.2 through one verified direct G04 route, preserving the
original checkout, prior candidates and local projected-module-charge wiring.
The separately reviewed G04 adapter adds only the opt-in 22-method shield phase;
default190, initial5 and projected9 remain unchanged. Its 27 prior isolated host
checks are harness evidence, not Android or a new combined-candidate test run.
STATUS and the final local freeze own the current source identity and intentional
cloud-freeze deviations. Cloud source/host/compile evidence remains distinct from
native acceptance; incoming G05.2 phases are not automatically registered or run.
The next local task is narrow local-delta review, then applicable focused host
checks and complete build-input/source qualification. The unchanged 32 GiB cap and
standing 8 GiB native/build reservation still require separate admission. Newer cloud
slices remain separately coordinated. C04/native/release acceptance stays open,
and closed C03.2 gates are not rerun by this integration.

## Historical cleanup-first prerequisite - H01 (completed)

[H01](tasks/H01-cleanup-first.md) is the one bounded implementation checklist for
the hygiene/code-quality findings. Complete its recoverable checkpoint and
supported-path/artifact handoff before new feature work. Fix concrete safety
defects before their affected operation; package identity is required before
distribution. Do not make every optional maintenance item a prerequisite to C04.

H01 closure does not require emulator success, a purge, a target reclaimed size
or a broad rewrite. Ambiguous assets may be retained with an owner and reason.
Historical-harness isolation, explicit navigation state and diagnostic extraction
have narrow triggers/acceptance in H01; unrelated formatting and upstream
refactoring are excluded. Parent review/release is recorded in STATUS. H01 source
preservation and eight retain/defer dispositions are verified; no purge occurred.
Continue the agreed development stages. C04 native execution still needs its
separate parent host slot and storage admission; optional maintenance is deferred
until its recorded trigger.

## Delivery order and finite user-visible checkpoints

These checkpoints group existing task IDs, not a second task inventory.
Full SCOPE/PARITY stays binding. No checkpoint waives a gate or equates a
development APK with full parity. Preserve actual proof provenance.

| Order | User-visible checkpoint | Existing work and completion boundary |
| --- | --- | --- |
| 1 | Dependable local fitting candidate | Preserve completed B/C01-C03 proof; close C04 native/full acceptance through its bounded diagnostic/fallback. C03.2 awaits reserved delivery, not new implementation. |
| 2 | Safe, reviewable phone build | Bring R02 signing/versioning/install-over-data proof forward. Review U01 with the user; integrate only approved native presentation in bounded screen changes preserving existing behavior. Begin R03 feedback on the declared feature set with authorized device access. No design approval is assumed. |
| 3 | Fits using the user's inputs | C06 offline skill profiles, I01 EFT import/export/sharing, then C07/C08 and C09 settings; close each existing matrix. Plan I05.02 backup scope here; close full backup/restore after its later data-type/interchange dependencies. |
| 4 | Linked fitting scenarios | D01/D02 projections and D03 commands are core requirements. Complete C05 fighter coverage for projection closure; add D04/D05 scenario/profile inputs. Earlier core editor work need not wait for every addition type. |
| 5 | Complete analysis and remaining parity | Deliver graph families on one shared plotting surface; C10 mutations; remaining I interchange, optional online refresh, preferences, localization and recovery. Close every owner row, not just common cases. |
| 6 | Everyday-use/full-scope release | R01 full offline/parity audit, final R02 upgrade proof, R03 supported-device/usability closure and R04 build/notes. Requires all A-I scope, accepted fixes and explicit release authorization. |

Optional private trial: after checkpoint 2, a clearly limited build may be
considered for feedback with its verified feature list and missing capabilities.
It requires explicit distribution/device authorization and safe data handling;
without verified backup/restore, use disposable fits only. It is not the agreed
everyday-use deliverable, approval of omissions, or a replacement for projections,
commands, graphs or other full-parity requirements.

## Technical dependencies versus sequencing preference

Depends on identifies full-outcome acceptance dependencies, not a ban on all
earlier work. New dependencies need a concrete contract/data reason; task order
or a missing unrelated screen alone is insufficient.

- R02 can begin from completed A07/B02, without C04/R01. Current-candidate
  native/device operations still require reliable execution.
- C06 and I01 use completed bridge/library/fitting contracts and need not wait
  for C05. They are permissible independent work if C04 stays blocked, once
  development resumes and a distinct scope is selected. Do not accumulate
  unverified features silently on the C04 candidate.
- D01 fit/module controls can begin against B02/B04 and existing projection
  bridge contracts; C04/C05 remain necessary for full drone/fighter acceptance.
  D03 can begin with C06; C07 remains necessary for implant-source acceptance.
  Neither editor is complete if those required cases are omitted.
- The first graph family supplies the single reusable plot surface. C01-backed
  capacitor/shield plots need not wait for damage/projection inputs. G01 still
  requires D02/D05/C09 for full damage behavior. Numerical samples, controls,
  units and relevant comparisons stay mandatory for each family.
- Keep graph-specific dependencies explicit: G04 effective-shield modes need
  fit-local damage contributions, already delivered by C01.3.1 (PARITY F19.04;
  graphs/data/fitShieldRegen/graph.py). Named D05 pattern collections remain open
  but are not invoked by these graph getters. Likewise,
  G05 ancillary reload/spool behavior needs C09 as well as D02 (F19.05;
  graphs/data/fitRemoteReps/getter.py and cache.py). Removing G01 as a plotting
  prerequisite does not remove these calculation/control requirements. G11
  still closes shared target-profile and comparison interactions.
- R03 permits early feedback after R02 and authorized device access; final
  closure still requires R01. Observations apply to the actual build and may be
  reused only while applicable. Early feedback does not presume final usability.

Independent planning/reference work may proceed earlier under these rules.
This is not authorization for workers or overlapping heavy jobs; delegation and
shared-resource limits still apply. Freeze each task's accepted completion set.
Optional ideas go to separate existing-owner work; defects needed to satisfy
accepted behavior remain required fixes.

The 2026-09-21 local Windows setup and workflow maintenance is tracked in
[STATUS](STATUS.md) and [Windows setup](WINDOWS.md). It does not advance B03.2,
change the feature-task counts or reduce any host/native acceptance check.

The 2026-10-01 [W02 local verification setup](tasks/W02-windows-local-verification.md)
preserves every feature acceptance check and PR #33. Its goal ends at setup
verification/delivery. Explicit resumption on 2026-10-02 authorizes B09.1 delivery,
then sequential eligible roadmap work using local verification.

Each row is a bounded outcome with a minimum acceptance check, not a license to
omit related Pyfa behavior. Before implementing a row, expand it with the
[task template](../../.github/ISSUE_TEMPLATE/android-task.md) in the PR, issue or a
task brief. If it cannot fit one focused review, split it into child tasks first.
[The A02 checklist](PARITY.md) maps observable behaviors to delivery owners.
Read the owner's rows before expanding a task. Coverage cannot be reduced to make
a task appear finished.
Early dependency requirements are ordering constraints, not claims of feasibility.

## A — prove the calculation engine and native build

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| A01 | done | — | [Reproducible desktop reference](tasks/A01-desktop-reference.md) | Clean Python 3.11 setup generates pinned game data and records meaningful raw values for one synthetic fitted ship; exact commands and data hash are reproducible. |
| A02 | done | A01 | [Expand the parity inventory](tasks/A02-parity-inventory.md) | Desktop controls, context menus, settings, all stat/graph families and import/export paths map to observable behaviors, source locations and tasks; gaps stay explicit. |
| A03 | done | A01 | [Minimal headless adapter](tasks/A03-headless-adapter.md) | One fitted ship calculates without wx/UI initialization; required dependencies, import order and data paths are documented; raw values match A01. |
| A04 | done | A03 | [Projected-effect reference cases](tasks/A04-projection-reference.md) | A pinned desktop source/target case records apply, range/state change and remove results; adapter agrees and restores original values on removal. |
| A05 | done | A03 | [Command-burst reference cases](tasks/A05-command-reference.md) | A real booster/source fit and recipient produce matching results with skills/implants/state changes; disabling/removing the command source restores baseline. |
| A06 | done | A03 | Android skeleton and native CI | Pinned toolchain builds an installable APK; an emulator test executes a real app assertion; deliberate APK delivery, concurrency, timeouts and retention are configured. No engine parity claim yet. |
| A07 | done | A06 | Bundle data and boot EOS on Android | Fresh offline launch calculates A01 through embedded Python; x86_64 native test passes and arm64 package contains its required native dependencies/data. |
| A08 | done | A04, A07 | Android projection parity | A04 reference cases pass through the Android bridge, including changes/removal and stale-cache checks. |
| A09 | done | A05, A07 | Android command parity | A05 reference cases pass through the Android bridge with correct recipient updates and cleanup. |
| A10 | done | A02, A08, A09 | Decide embedding feasibility | Record measured startup/recalculation/memory/APK size, remaining ABI/device gaps and supported dependency pins; justify continuing or propose a viable correction. |

## B — make an editable, persistent fitting workflow

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| B01 | done | A10 | [Typed bridge operations and results](tasks/B01-typed-bridge.md) | One mutation/query contract carries raw units, errors and fit revisions; engine work stays off UI thread and serialized; failed edits do not leave partial state. |
| B02 | done | B01 | [Local fit persistence](tasks/B02-local-persistence.md) | Save/reopen synthetic fits and command/projection links across process restart; transactions and relationship identity preserve results. |
| B03 | done | B02 | Fit library screen (parent) | B03.1 and B03.2 complete; all original lifecycle and organization requirements retained. |
| B03.1 | done | B02 | [Fit lifecycle and search](tasks/B03-fit-library.md) | Create from fixtures, find, open, rename, duplicate and delete; resolve links atomically, retain independent inputs and reopen an empty library. Host and native workflow checks pass. |
| B03.2 | done | B03.1 | Library organization and open-fit navigation | Hull group/race browsing, hide/show empty groups, back-to-hull navigation, recently modified fits and multiple open fits with close one/all and optional restart restoration; preserve F01.03–F01.05 and audit desktop preferences. |
| B04 | done | B03 | [Equipment browser and fitting (parent)](tasks/B04-equipment-fitting.md) | B04.1 and B04.2 complete; all F02.01–F02.05/F02.09 requirements and arbitrary-hull creation retained. |
| B04.1 | done | B03 | Offline equipment discovery | Complete pinned market catalogue, group/search/meta filters and item-to-group navigation pass independent host and offline native checks. |
| B04.2 | done | B04.1 | Fitting editor and item history (parent) | B04.2.1–B04.2.3 complete; all arbitrary-hull, fitted-item, charge/variation/reorder, restriction/legality and recent-item requirements retained. |
| B04.2.1 | done | B04.1 | Arbitrary empty ship and structure creation | Every bundled hull can create a named empty fit with desktop-matched raw values and explicit absent attributes; native creation, copy, rejection and restart preserve inputs. |
| B04.2.2 | done | B04.2.1 | Module editing, legality and recent use | Add/replace/remove modules, rigs and service modules with positions, state rules, EOS legality and restriction re-enable behavior; persist a desktop-matched bounded recent-use list. |
| B04.2.3 | done | B04.2.2 | Charges, variations and rack ordering (parent) | B04.2.3.1–B04.2.3.3 complete; all charge/discovery, variation/addition and ordering/heat acceptance retained. |
| B04.2.3.1 | done | B04.2.2 | Charge editing and active-fit discovery | Load/replace/unload compatible ammo, scripts and crystals through native controls; complete compatible and active-fit sets match desktop; atomic failures, recipients and restart retain exact results. |
| B04.2.3.2 | done | B04.2.3.1 | Fitted and addition variations | Supported module and existing addition variations reconcile states/charges/locations exactly as desktop with atomic failures, independent values and native restart evidence. |
| B04.2.3.3 | done | B04.2.3.2 | Rack ordering and heat behavior | Swap occupied or vacant same-rack positions without losing states/charges; independent positional heat results and native reorder/restart workflows pass. |
| B05 | done | B04 | [Bulk weapon/module editing (parent)](tasks/B05-bulk-editing.md) | B05.1–B05.4 delivered: selection/ammo/state/fill/clone/variation/removal match pinned desktop behavior with native offline restart; B09 owns undo/redo. |
| B05.1 | done | B04 | Bulk ammunition selection | Selection-only and all-similar touch scopes expose exact targets/skips; original mixed-compatibility rules, atomic save/recovery and native restart pass. |
| B05.2 | done | B05.1 | Bulk module states | Native multi-selection exposes original cycle/offline/overheat behavior and supported state fallbacks; recipients, restrictions and restart match desktop. |
| B05.3 | done | B05.2 | Clone and fill modules | Clone selected modules and fill free slots from an item or fitted module; preserve inputs, stopping limits, legality and history with native persistence evidence. |
| B05.4 | done | B05.3 | Bulk variations and removal | Selection-only/all-similar actions apply original family and removal rules; show affected/skipped modules and retain atomic graph/history/restart behavior. |
| B06 | done | B04 | [Hull-specific configuration (parent)](tasks/B06-hull-configuration.md) | Supported ship/structure modes and subsystem changes update legal slots and bonuses correctly; test a mode hull and strategic cruiser. |
| B06.1 | done | B04 | Hull modes | Expose exact available tactical/other ship modes, recalculate EOS bonuses and persist/reopen the chosen mode with native touch and independent desktop evidence. |
| B06.2 | done | B06.1 | Strategic-cruiser subsystems | Add/replace/remove subsystem choices; reconcile changed slots, fitting legality and hull bonuses with desktop/native restart evidence. |
| B06.3 | done | B06.2 | Structure-specific controls | Complete service-slot/restriction/bonus interactions and compare independent structure fixtures with native restart evidence. |
| B07 | done | B04 | [Cargo management (parent)](tasks/B07-cargo-management.md) | Add/remove/change stacks and move fitted equipment/ammo to/from cargo; quantities survive restart and agree with Pyfa behavior. |
| B07.1 | done | B04 | Cargo stacks and quantities | Persist cargo in the fit graph; add, remove and change stack amounts, showing EOS volume/capacity and native offline copy/restart. |
| B07.2 | done | B07.1 | Selected cargo actions, presets, fill and variations | Multi-select quantity/removal including zero-to-remove; match original ammunition presets, fill-to-capacity boundaries and variation/quantity merging. |
| B07.3 | done | B07.2 | Fitted equipment and charge transfers | Move/copy fitted modules and charges to/from cargo, preserving desktop fit/charge/state and atomic behavior. |
| B08 | done | B03 | [Fit notes](tasks/B08-fit-notes.md) | Edit and persist per-fit notes, including multiline/non-ASCII content, without losing unsaved text on navigation. |
| B09 | done | B05 | [Undo/redo for fit edits (parent)](tasks/B09-undo-redo.md) | Single and bulk edits undo/redo as user actions; recalculated values and selection state stay consistent after reversal. Extend through later mutation tasks. |
| B09.1 | done | B05 | Single and bulk module undo/redo | Per-fit 100-action history, atomic reversal/reapply, branch invalidation, safe selections and native offline recreation/restart match independent desktop evidence. |
| B09.2 | done | B09.1 | Remaining supported mutation history | Verify hull/cargo/addition/linked-effect and rename reversals, enumerate original gaps, and require later mutation tasks to extend the tested contract. |

## C — expose the full fit inputs and statistics

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| C01 | done | B04 | [Resources, capacitor and defenses (parent)](tasks/C01-fit-statistics.md) | Every audited resource/capacitor/tank field has correct units/rounding and matches raw reference results under relevant assumptions. |
| C02 | done | B04 | Firepower, bombs and mining stats | Audited outgoing fields match representative turret, missile, bomb and mining cases; unsupported/absent values remain distinguishable from zero. |
| C03 | verified-local | B04 | [Targeting/navigation and attribute inspector](tasks/C03-targeting-attributes.md) | Drone control range and all audited miscellaneous/ship/item attributes are reachable and correct; search/detail behavior works on a phone. Both children have local proof; C03.2 external delivery is pending. |
| C03.1 | done | B04 | Targeting/navigation and complete cargo details | All F07.01–F07.30 verified in the [full local receipt](evidence/c03-1-native.json): original lock/sensor/navigation/hold values, modifier edits and native/offline/restart proof. Delivered [PR #41](https://github.com/Sussic/Pyfa-android/pull/41), merge745fc1e2. |
| C03.2 | verified-local | C03.1 | Complete ship/item/charge inspection | F07.31–F07.32 and F07.34–F07.48 grouped current/base/raw attributes, affectors, effects, variations and every equipment detail family. |
| C04 | paused (code integrated; native acceptance blocked, not missing) | B04 | [Drone editing](tasks/C04-drone-editing.md) | Add/split/merge stacks, activate/select counts and respect bandwidth/limits; damage and drone control range react correctly. |
| C05 | cloud-compiled; device gates open | B04 | Fighter editing | Squadron quantities and ability states update statistics; save/reopen retains abilities and selected states. |
| C06 | active | B01, B03 | Offline character profiles | All-V/custom skills can be selected, edited and saved; requirements and affectors are inspectable and bonuses match references. |
| C07 | partial; C07.1–C07.3 cloud reviewed/compiled; device open | C06 | Implants and implant sets | Slot handling and applying/saving sets match Pyfa; profile changes update dependent fits. |
| C07.1 | cloud reviewed/compiled; device open | C06 | Fit-local implant editing | Add/replace by slot, toggle/remove selected implants and reuse source variations; preserve current durable records and linked/profile/history/restart behavior. Character collections and sets remain open. |
| C07.2 | cloud reviewed/compiled; device open | C06, C07.1 | Shared character implants and fit source selection | Custom collection add/replace/remove, complete detached copy, preserved local/character collections, reversible source choice, atomic linked recalculation/history and restart. Named sets and defaults remain separate; native host/parity/reopen and offline compilation pass, device gates remain open. |
| C07.3 | cloud reviewed/compiled; device open | C06, C07.1, C07.2 | [Reusable detached implant sets](C07-3-IMPLANT-SETS.md) | Original predefined browse/apply, custom CRUD/ordered editing/duplication, save-current and one atomic fit-local or editable-character merge with history/reopen. No live template binding or implicit source switch. Defaults/interchange retain existing owners; exact-package/Library acceptance belongs to external receipts and device gates remain open. |
| C08 | cloud-compiled; device gates open | C06 | Boosters and side effects | Add/toggle boosters and individual supported side effects; raw results and persistence match references. |
| C09 | partial; C09.1/C09.2 cloud compiled | B05 | Heat, reload and spool options | Audited state/reload/spool and adaptive-module options affect the correct stats; transitions and undo have reference tests. |
| C09.2 | cloud reviewed/compiled; device open | C09.1 | Local reactive armor built-in selection | Fit inheritance, disabled adaptation and explicit built-ins stay distinct through edits/history/restart; named-pattern management remains D05. |
| C09.1 | cloud reviewed/compiled; device open | B05 | Local spool override/reset and heat detail precision | Original supported module groups expose cycle choices and raw/effective values; overrides survive copy/variants/history/restart and heat details retain full EOS precision. Global defaults/reload remain open; individual projected spool override/reset is implemented in D01.2 with device qualification still open. Local RAH is C09.2, while named patterns remain D05. |
| C10 | queued | C04, B04 | Mutated items | Enter/edit rolled module and drone attributes; exact values survive saves and affect calculations without reverting to base stats. |

### C01 bounded children

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| C01.1 | done | B09.2 | All fitting resources | F05.01–F05.11 raw values, units, compact/detail precision, overload and native read-only/restart behavior match independent reference evidence. |
| C01.2 | done | C01.1 | Capacitor details | F05.12–F05.15 stable/range/depletion units, capacity, rates, neutralizer resistance and effective details match independent/native cases. |
| C01.3 | done | C01.2 | Defenses and tank | F05.16–F05.27 all resistances, raw/effective HP, damage inputs, reinforced/sustained repairs and spool details pass independent/native checks. |

### C01.3 bounded children

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| C01.3.1 | done | C01.2 | Defenses and incoming damage | F05.16–F05.22 all resistances/multipliers, raw/effective layer/total HP, HP/EHP toggle and four independently editable damage contributions pass original desktop/native/history/restart checks. |
| C01.3.2 | done | C01.3.1 | Repair and tank details | F05.23–F05.27 passive/active raw/effective reinforced/sustained tank, capacitor/projected repairs and pre/full/current spool details pass independent/native checks. |

## D — expose interacting fits and scenarios

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| D01 | active (D01.1 cloud reviewed/compiled; remaining scope open) | B02, B04, C04, C05 | Projection editor | Add fits/modules/drones/fighters as supported, adjust range/count/state, and remove them; edited source values update every recipient correctly. |
| D02 | D02.1/D02.2 finite cloud proof complete; full qualification open | completed D01 controls for each child | Projection interaction coverage | Multiple sources, stacking, remote reps/capacitor and supported reciprocal links match desktop; no arbitrary cycle suppression or stale effects. Split by interaction family as needed. |
| D03 | active (D03.1 cloud reviewed/compiled; broader scope open) | B02, C06, C07 | Command-fit editor | Select/configure command sources, their enabled states and applicable strengths; recipient results persist and match A05/A09 plus audited options. |
| D04 | partial; D04.1 cloud compiled | B04 | Environments and security modifiers | Supported wormhole/weather/site/security scenarios can be applied/removed; stacking and restored baselines match reference cases. |
| D04.1 | cloud reviewed/compiled; device open | B04 | Structure system security | Four original security choices, EOS rig effects, history and saved graph restoration. No pilot-security or environment expansion. |
| D04.2 | audited source/evidence package accepted (compile-only; no APK or device claim) — queued design text is historical | D04.1, C06 profiles/history | Pilot security and character inheritance | Settle raw Character versus explicit values, protected character semantics, copying/migration and six source-menu hull availability before implementation. No broad environment editor or new graph family. |
| D05 | D05.1–D05.3 cloud compiled; D05.4 cloud reviewed/compiled and package closed; remaining scope open | C01, C02 | Damage patterns and target profiles | Named target profiles, incoming libraries, Selected Ammo and local named RAH have bounded child evidence. Global/default profiles, interchange and full native acceptance remain open; do not close the parent from cloud proof. |
| D05.1 | cloud source/host/compile checkpoint; device open | C01, C02 | [Reusable named target profiles](D05-1-TARGET-PROFILES.md) | Built-in/custom selection, atomic shared edits, history and restart preserve identity and exact raw/effective assumptions; device qualification remains separate. |
| D05.2 | cloud source/host/compile checkpoint; device open | C01.3, C02, C06, C09.2, D05.1 | [Named incoming damage patterns](D05-2-DAMAGE-PATTERNS.md) | Built-in/custom library, live per-fit binding, exact anonymous detach, Uniform reset/delete, shared edits/history/restart; preserve positive-total fit domain and existing RAH overrides. Global/default patterns remain separate; ammo-derived patterns are D05.3 and local named RAH bindings are D05.4. |
| D05.3 | cloud reviewed/compiled; device open | D05.2 | [Selected-item incoming pattern](D05-3-SELECTED-ITEM-PATTERN.md) | Equipment derives protected Selected Ammo from base item damage, with atomic shared binding/history, finite reference/reopen and actual-wire proof. Positive-total boundary remains; zero-total incoming assignment and global/default patterns remain open. Local named RAH is D05.4. Exact package/Library acceptance belongs to external receipts. |
| D05.4 | cloud reviewed/compiled; package closed; device open | D05.2, D05.3, C09.2 | [Local named RAH patterns](D05-4-LOCAL-NAMED-RAH.md) | Durable custom/Selected Ammo module references, atomic holder edits/delete/history, zero refusal and fresh reopen; accepted 25-row/250-scalar candidate and 47/9 actual-wire proof retain publication/positive-zero qualifications. No new graph sampling. All 532 instrumentation methods in 139 classes compiled only; final delivery and device gates remain separate. |

## G — port one graph family at a time

Each graph task includes reference-matched sample values, applicable desktop input
controls, multiple-fit comparisons, readable axes/units and a focused interaction
test. The first implemented family supplies shared plotting UI; do not add a new framework for
each graph. Keep heavy sample calculation off the UI thread.

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| G01 | queued | D02, D05, C09 | Damage graph using the shared plot surface | Port `fitDamageStats` with audited modes and projection/target assumptions; numeric samples and touch controls pass. |
| G02 | queued | G01 | Application profile graph | Port `fitApplicationProfile`, including applicable ammo optimization and projected effects; samples match and repeated edits do not accumulate stale results. |
| G03 | active | C01 | Capacitor graph | Port `fitCapacitor`; selected time/fit inputs and sampled capacitor behavior match. |
| G04 | cloud source/host/compile checkpoint; native execution open | C01.3.1 fit-local damage contributions; named D05 collections remain separate | Shield regeneration graph | Port `fitShieldRegen`; sample rates and axes match. |
| G05 | G05.1/G05.2 source-reviewed and cloud-compiled; full qualification open | D02.2 finite source preparation, C09 local controls; bounded cycle-cache preparation completed | Remote repair graph | Current and selected-time rate versus distance, accumulated HP versus distance, and rate/amount versus time are implemented with original ordered events and explicit range/reload assumptions. Finite parity and unchanged-cap resource proofs passed; external receipts and exact direct-route source reconstruction passed locally. Android execution and full `fitRemoteReps` qualification remain open. |
| G06 | cloud-compiled | C03 | [Lock-time graph](G06-LOCK-TIME.md) | Port `fitLockTime`; target/fit changes and sampled times match. |
| G07 | cloud-compiled | C03 | [Mobility graph](G07-MOBILITY.md) | Port `fitMobility`; applicable input modes and sampled values match. |
| G08 | isolation-prerequisite | C03 | [Warp-time graph](G08-ISOLATION-PREREQUISITE.md) | Port `fitWarpTime`; distances/fit assumptions and sampled times match. |
| G09 | cloud-compiled; final rebind/package and device gates open | delivered D01 inputs and D02.1 LOCAL/cache behavior; broader D02 qualification remains separate | [Electronic-warfare graph](G09-EWAR-DISTANCE.md) | Seven original distance ordinates, null units, nullable/clamped resistance and complete 1–8-fit adaptive comparisons are implemented. Source, host contract/shape, finite original parity, resource/lifecycle audit, 1,262 actual-wire host acceptance, all 225 affected host methods and main/instrumentation compilation passed. Thirty native methods compiled only; package and Android execution remain separate gates. |
| G10 | queued | D02 | ECM/burst/scan-resolution-damp graph | Port `fitEcmBurstScanresDamps`; audited inputs and samples match. |
| G11 | queued | G02, G03, G04, G05, G06, G07, G08, G09, G10 | Remaining shared graph actions | Verify audited overlays (including drone control/lock ranges), selections, exports and comparisons across families; split any remaining substantive feature into its own task. |

## I — interchange, optional refresh and updates

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| I01 | active | B04 | EFT import/export and phone sharing | Paste/import/export a fit; valid states/charges round-trip as supported, and malformed input does not partially overwrite saved work. |
| I02 | queued | I02.01, I02.02, I02.03, I02.04, I02.05, I02.06, I02.07, I02.08 | Remaining Pyfa interchange formats — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I03 | queued | I03.01, I03.02, I03.03, I03.04 | Optional character/fitting synchronization — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I04 | ready | B04 | Prices and price preferences | Refresh supported sources online, retain timestamped cached values offline and preserve supported pricing options; resolve the manual-price question in PARITY_AUDIT Q02. Unavailable values are not zero. |
| I05 | queued | I05.01, I05.02 | Data refresh and user backups — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I06 | queued | I06.01, I06.02, I06.03, I06.04, I06.05, I06.06, I06.07 | Remaining preferences and localization — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |

## I child tasks — bounded delivery units

A02 split four broad I rows before implementation. Parent IDs remain as rollups
so existing dependencies retain their meaning; children never depend on their
own parent. A parent becomes done only when every child is done. These 21 child
rows increase the queue from 55 to 76 tracked rows: 72 work items and four rollups.
Task counts measure bookkeeping, not equal effort or a percentage of app parity.
Use the delivery order above and STATUS, not alphabetical order, to select the next authorized outcome.

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| I02.01 | queued | I01 | DNA interchange | Plain, chat-tagged and alternate DNA fixtures pass; supported formatting and losses are documented. |
| I02.02 | queued | I01, C10, D03 | XML interchange | Single/multi-fit XML and Pyfa extensions match supported fields; notes truncation and absent relationship/state fields are explicit. |
| I02.03 | queued | C05, D02 | EFS export | Fit/type exports match the implemented EFS schema, including weapon/fighter/projection data and unsupported-effect reporting. |
| I02.04 | queued | I01, I04 | Multibuy export | Quantities and inclusion/cheaper-equivalent options match reference exports without mutating the saved fit. |
| I02.05 | queued | C01, C02, C03 | Fit stats and item CSV export | Formatted fit reports and current/base attribute CSV retain units, assumptions and Unicode. |
| I02.06 | queued | I01, C10, C05, C07, C08, B07 | Mutation and additions clipboard interchange | Mutation text and all/selected additions round-trip their supported fields; malformed pastes preserve saved work. |
| I02.07 | queued | C06, D05 | Skills and profile interchange | Character XML, skill text/training exports and damage/target-profile clipboard formats preserve supported values and validate errors. |
| I02.08 | queued | I01, B02 | HTML fit collection export | Styled/minimal collection exports contain correct fitting links/data and work through Android file sharing. |
| I03.01 | queued | C06 | Android ESI sign-in and identity management | Supported authentication return path, character selection/removal, cancellation/expiry and offline startup are verified; desktop server/token preferences have an explicit disposition. |
| I03.02 | queued | I03.01, C06 | Character skill refresh | Linked-character refresh updates skills/security; failures retain cached values and do not silently discard pending edits. |
| I03.03 | queued | I03.01, I01 | ESI fittings and JSON interchange | Browse/import/upload and explicitly confirmed remote deletions work; JSON losses and inclusion options are documented; local fits remain usable offline. |
| I03.04 | queued | C10 | Dynamic mutated-item link resolution | Supported online item links resolve exact rolls that persist offline; malformed/unavailable links preserve the current fit. |
| I05.01 | queued | A10, B02 | Dataset refresh and recovery | Validate a pinned update before activation; interrupted/corrupt/incompatible data leaves user state recoverable and calculation offline. |
| I05.02 | queued | B02, C06, C07, D05, I02.02 | User backup, restore and database maintenance | Complete Android backup scope is explicit and tested beyond lossy XML fit export; corrupt restore and clearing referenced profiles are handled safely. |
| I06.01 | queued | C06, C07, C09, D05 | Calculation/default preferences | Reload/spool, strict skill prerequisites, global character/pattern and default implant settings persist and update all affected fits. |
| I06.02 | queued | B05, B08, C03, C10 | Display and interaction preferences | Audited statistics, rack/details, context actions and market/meta controls have persistent touch equivalents and remain discoverable. |
| I06.03 | queued | A07, C03 | UI and game-data localization | Enumerate/pin available locales; bundled UI/data languages, fallback, formatting and Unicode work offline. |
| I06.04 | queued | B01, C03 | Attribute overrides | Edit/toggle/remove/import/export global overrides with exact recalculation/restoration and safe invalid CSV handling. |
| I06.05 | queued | I03.01, I04 | Network and proxy controls | Master/per-service controls and supported proxy behavior work on Android; local calculations never depend on refresh. |
| I06.06 | queued | A06, C03 | Diagnostics, notices and help | Source/version/notices/help and privacy-preserving diagnostic export are reachable; desktop-only tools have documented equivalents or a recorded product decision. |
| I06.07 | queued | R02 | Optional app update notifications | Personal-build delivery equivalent supports prerelease/suppression/download choices or records an explicit product decision; no store/backend requirement is introduced. |

## R — close actual gaps and deliver

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| R01 | queued | B06, B07, B08, B09, C08, D04, G11, I02, I03, I04, I05, I06 | Full parity and offline audit | Every A02 behavior maps to passing evidence; fresh offline install, restart, backup and interacting-fit scenarios pass. File each uncovered behavior as a bounded fix, not a waived check. |
| R02 | ready | A07, B02 | Stable install/update packaging | Stable signing/versioning, required notices and exact source identification are established; an install-over-previous-build test preserves fits. Complete before distributing successive persistent-use APKs. |
| R03 | queued | R02 for early entry; R01 for final closure | Real-device usability review | Verify the supported phone/ABI, record measured responsiveness and user feedback on bulk edits, statistics and linked fits; turn each issue into a small fix. |
| R04 | queued | R03 | Final acceptance build | All parity, offline, update and agreed usability issues are verified closed; provide installable APK, matching source and concise release/install notes. |

R01 also requires every A–I task and its discovered child tasks to be complete
even if not transitively listed in its dependency cell. R02 can run
early once its dependencies pass; it is not deferred until the final feature audit.
