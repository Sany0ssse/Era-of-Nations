# Era of Nations 0.1.0 — initial development baseline

Source status updated on 2026-10-06; earlier startup evidence remains dated 2026-10-05.

The graphite/navy UI update is now installed. Its 109 sprite opt-ins and final
DirectX 11 startup passed mapping and compilation checks; visual acceptance of
the unobstructed menu and campaign controls remains pending. See
[UI_THEME.md](UI_THEME.md) for scope, receipts and exact limitations.
The existing diplomacy audit and sixteen implementation packages are complete at
source level. The earlier SCO rejection and Arctic observer repairs are retained.
The first package reconciles NATO/CSTO/SCO membership and native exits,
repairs investment cancellation, debt assumption and operative ransom/exchange,
and gives the existing energy agreement a guarded proposal/response/execution/
revision/termination cycle. Reproducible source models and independent reviews
passed. The second package guards trade and mutual investment treaty proposals,
responses and bilateral cleanup, freezes foreign building proposals before
consent, rechecks execution conditions and repairs refunds. It retains existing
prices, political rules and separate storyline paths. The third package opens
ordinary defensive alliances without a great-power rank: a consensual diplomatic
proposal, a native template, current national rights, retained join thresholds,
defensive call guards and lifecycle cleanup. AI national alliance-desire modifiers
are retained. No diplomacy package has been launched in HOI4; new-campaign acceptance,
native callback timing, actual accounting and save/load remain pending. See
[DIPLOMACY_PACKAGE_03_UK.md](DIPLOMACY_PACKAGE_03_UK.md),
[DIPLOMACY_PACKAGE_02_UK.md](DIPLOMACY_PACKAGE_02_UK.md) and
[DIPLOMACY_PACKAGE_01_UK.md](DIPLOMACY_PACKAGE_01_UK.md) for changes, checks and
runtime checklists. [ORDINARY_ALLIANCES_PLAN_UK.md](ORDINARY_ALLIANCES_PLAN_UK.md)
retains the original D1 audit; its source implementation is now package 03.
Standard no-DLC creator callback coverage, native rule composition and exact
selected-war treaty obligations remain runtime acceptance items. [DIPLOMACY_AUDIT_UK.md](DIPLOMACY_AUDIT_UK.md) preserves the earlier
baseline audit and subsequent priorities.

The fourth diplomacy package implements a bounded repair after the player's
report of rejected larger electricity exports. It covers signed quantity,
buyer/seller AI inputs, replacement capacity, partner selection, current cached
supplier-capacity rechecks and initial resets of contractual aggregates.
Fresh cumulative source models passed 4510 scenarios (4423 earlier plus 87 new),
with 27 new source assertions and the repeated package 03 source checks.
Final independent review completed with no unresolved P1/P2 findings;
the reported gameplay sale is unverified.
The old signed-volume AI acceptance cliff was reproduced for a human buying
from an AI supplier; GUI replacement limits affect both directions. The latest
cached balance is used without immediate global-generation recalculation.
The later package05 caps the former raw-GW bonus at 20 points; full
contract affordability remains unproven. No physical grid or new budget law is added.
See [DIPLOMACY_PACKAGE_04_UK.md](DIPLOMACY_PACKAGE_04_UK.md) for scope and runtime
acceptance criteria. [DIPLOMACY_ROADMAP_UK.md](DIPLOMACY_ROADMAP_UK.md) explains
why alliances came first and prioritises one existing energy negotiation cycle,
state support, consultations and mediation before broader new relations.

The fifth package develops the existing energy agreement into editable human
counteroffers, one automatic AI counteroffer, proposal withdrawal, draft reopening
and immutable reason notices. Active deliveries/payments persist until agreement;
counterdraft zero/reversal and stale responses are guarded. Contracts remain
explicitly indefinite. The bounded volume bonus cannot override every price or
budget concern merely through huge GW. Source scenarios, byte boundaries and
independent review passed 4620 cumulative scenarios (110 new) and 86 new source
checks. Two invalidated-response P2 findings were repaired and reproduced;
no unresolved P1/P2 findings remain. See [DIPLOMACY_PACKAGE_05_UK.md](DIPLOMACY_PACKAGE_05_UK.md).
Native GUI/callbacks, real AI choice, accounting and save/load still require
new-campaign acceptance.

The sixth package completes the existing one-time economic aid flow: frozen
5/15/35-billion tiers, paired draft/response reservations, donor-owned escrow,
explicit recipient consent, withdrawal, fresh cash/policy checks and refund
claims retained above the treasury cap. It repairs AI weights, restores only
identifiable older prepaid tiers, and keeps ambiguous legacy or disappeared
pairs retired while other partners remain available. Debt support preserves
its existing consent, national policies, 75PP cost and cash-funded settlement;
fresh sending guards, dead-partner cleanup, AI cooldown/affordability and
truthful frozen-ceiling descriptions are repaired. Aid and debt remain separate
consent flows. Cumulative source checks passed 4786 scenarios (166 new);
exact-byte boundaries cover five existing and nine new game files.
See [DIPLOMACY_PACKAGE_06_UK.md](DIPLOMACY_PACKAGE_06_UK.md) for limitations
and new-campaign acceptance. No diplomatic package has been run in HOI4.
The seventh package adds human-initiated bilateral economic consultations:
literal trade, electricity or support topics; free draft/cancellation, a single
10PP send cost, recipient consent/refusal, withdrawal and a 30-day active channel.
Its financial follow-up opens the existing separate grant draft under the
actual aid policy and funding checks. Forced pending expiry or structurally
invalid/missing-partner cleanup retires only the affected pair permanently;
other partners stay usable. Normal consistent channel
closure preserves independent contracts and pending support. Source models
passed 4942 cumulative scenarios (4786 previous plus 156 new), with 208
new source checks; 68,270 existing gameplay files remain byte-identical and
exactly seven new game files were added. Independent source review and native
documentation checks passed; native compilation, GUI, timers, scopes, AI,
save/load and campaign acceptance remain pending. See
[DIPLOMACY_PACKAGE_07_UK.md](DIPLOMACY_PACKAGE_07_UK.md).
The eighth package adds a bounded three-country mediation mandate. A human
initiator selects a specific opponent and a deescalation or humanitarian agenda
through targeted decisions. A 20PP send, explicit mediator consent and separate
opponent consent precede the 30-day mandate. Each participant can withdraw;
current war/neutrality, reciprocal identities, callbacks, expiry and annex
cleanup are guarded. No peace, access, territory or treasury effect follows
from the mandate. Forced unresolved cleanup permanently retires the A/M and
M/B channels; another eligible mediator remains possible. Source models passed
5151 cumulative scenarios (209 new), with 301 new source checks and
68277 preserved old gameplay files. Native compilation, decision/GUI
scopes, timers, AI, save/load and campaign acceptance remain unverified.
See [DIPLOMACY_PACKAGE_08_UK.md](DIPLOMACY_PACKAGE_08_UK.md).
Its procedural terms and revision are implemented in package09 below; actual
peace execution requires separate native multiwar/subject/faction acceptance.

The ninth package adds concrete procedural review of the mediation mandate:
six literal agenda/duration offers, separate M then B consent, free proposals,
unchanged accepted agenda/deadline while pending, and atomic 30/60/90-day renewal
after final consent. Every human participant can cancel the pending revision.
A single pre-clear hook in package08 protects outstanding original replies
before any base identity is erased; forced cleanup quarantines terms-only A/M
and M/B edges while package08 mandates retain their own independent rules.
Normal consumed replies allow successive review rounds. Orphan cancellation
and missing existing AI opinion weights were reproduced and repaired.
Source models passed 5289 cumulative scenarios (5151 previous plus 138 new),
with 292 new source/API checks. Exactly 68285 old gameplay files remain
byte-identical, one has the sole pre-clear hook, and eight new files were added.
These terms govern talks only. Binding peace, humanitarian access and delivery
monitoring require separate mechanisms and native acceptance. Native scopes,
timers, AI, GUI, save/load and campaign remain unverified. See
[DIPLOMACY_PACKAGE_09_UK.md](DIPLOMACY_PACKAGE_09_UK.md).

The tenth package repairs the existing native antiterror agreement. A paired
30-day proposal and fresh consent apply exactly one .05/-5/+5 contribution per
participant and partner. Native proposal/active termination costs remain 75PP;
the new free withdrawal belongs only to the original human sender. Existing
political AI weights remain weighted rather than becoming universal bans;
the original 120-day send cooldowns are now enforced for human sends too.
Termination and both old/new annex hooks reverse only identifiable pair
components, preserving other CT and AI command-power sources. Legacy active
flags are adopted without adding a second contribution; ambiguous old pending
pointers and unidentified historical bonus residues are not reconstructed.
Forced unanswered cleanup permanently retires only the known CT pair.
Six game files and one action are added; only two treaty actions and two annex
branch bodies change inside two existing files. The 31 existing paid delayed
operations remain byte-identical and are the next execution-lifecycle task.
Source checks passed 5401 cumulative scenarios (5289 previous plus 112 new)
and 178 separate new source/API checks; 68292 existing gameplay files and all
unowned bytes inside the two changed files remain exact. Independent review
closed duplicate completion/termination, annex residue, incoming withdrawal
and orphan cancellation findings.
See [DIPLOMACY_PACKAGE_10_UK.md](DIPLOMACY_PACKAGE_10_UK.md). Native GUI,
cost timing, scopes, timers, AI, save/load and campaign acceptance remain pending.

The eleventh package completes the existing 31 paid CT decision lifecycles:
25CP charged once, immutable territory owner, the original five-day delay,
fresh bilateral cooperation and national checks, one inherited random outcome,
individual free cancellation and measured CP refund claims. Existing >25CP
admission, 35-day native re-enable, all original visibility/AI/NOR rules and
virtual terrorism accounting tags remain unchanged. Cancelled records retain
the original timer lock; a seven-day unresolved watchdog or operator annex
retires only the affected per-country decision. Refund claims survive capacity
limits and stay owned by the payer after annexation. Negative observed native
credit moves clipped over-cap CP into the claim; native cap behavior is not yet
accepted. Old untracked paid decisions are not inferred or refunded. Exactly
31 blocks in one existing file change, 23 unrelated decisions and all unowned
bytes are preserved, and seven game files add 31 cancellation decisions.
Native diplomatic action IDs remain 65. Full source checks and independent
review passed 5541 cumulative scenarios (5401 previous plus 140 new in 23
groups), with 1381 separate new source/API checks and no new adapter cases.
All eight owned game-file hashes agree; 68299 unrelated existing gameplay
files remain byte-exact. See
[DIPLOMACY_PACKAGE_11_UK.md](DIPLOMACY_PACKAGE_11_UK.md). Native scopes, timers,
CP limits, GUI, AI, extinct-country variable persistence and save/load remain
unverified. Civilian satellite access is addressed by package 12 below.

The twelfth package develops the existing six civilian GNSS/COM actions:
actor-owned outgoing partner/kind/frozen-level records, fresh acceptance,
free withdrawal, a 30-day response window and a separate native revocation
reason. Pending records stay reserved until their response is consumed;
forced cleanup quarantines only that sender/partner/family route. Live
reciprocal provider IDs are canonical, cached tiers rebuild from those IDs,
and current-country bonuses use the original native cap tables. Zero,
invalid or weaker systems and direct war leave dormant consent without
foreign bonuses; service recovery cannot recreate a revoked agreement.
Existing COM demand now sums all recipients' 100 receivers per controlled
state. Two files change only inside six civilian action and five civilian
effect blocks; seven game files are added. All 65 native action IDs and
military/SPY behavior remain unchanged. Full source checks passed 5647 cumulative
scenarios (5541 previous plus 106 new in 23 groups), with 347 separate new
source/API checks and no new adapter cases. All nine game-file hashes agree;
68305 unrelated existing gameplay files remain byte-exact. The existing full
COM traffic-stat calculation retains its weekly schedule. See
[DIPLOMACY_PACKAGE_12_UK.md](DIPLOMACY_PACKAGE_12_UK.md). Unknown old outgoing
pointers remain conservatively locked; native scopes, timers, arrays,
modifiers, GUI/AI/save-load and campaign acceptance are unverified. Existing
COM traffic/base guards and shared cooldown need separate follow-up.
Correction after package 13 audit: capacity already summed qualifying tiers;
the earlier overwrite claim was incorrect. Its capacity arithmetic is preserved.

## Diplomacy package 13

The remaining twelve native military GNSS/COM/SPY and civilian SPY access
actions now use separate actor-owned proposals, frozen provider levels,
fresh acceptance, withdrawal, reciprocal canonical IDs and current bonuses.
Revocation removes the exact provider; dormant consent gives no foreign benefit.
Existing native IDs, costs, AI policy and historical cooldown flags remain.
The original positive-tier rule is extended only for a working tier0 provider
with a positive native satellite count; its benefit uses the native tier0 cap.
The original provider>=recipient comparison and rules for tiers1–7 are retained.
Military COM demand counts each consenting recipient once, checks military
overload and clears stale service at zero capacity. Both zero coverage maxima
use explicit guarded zero coverage. Negative SPY weather benefits use the
native lower cap. Capacity sums and the weekly COM stats schedule are retained.

The cumulative source run passes 5932 scenarios (5647 previous plus 285
new actual-source traces) and 656 new source/API checks; no new adapter cases.
Nine gameplay file hashes agree and 68312 unrelated old gameplay files are
byte-exact. The previous capacity-overwrite description has been corrected;
the append-only archive of prior evidence is preserved. See
[DIPLOMACY_PACKAGE_13_UK.md](DIPLOMACY_PACKAGE_13_UK.md).
Native scopes/timers/arrays/modifiers/UI/AI/save-load and campaign acceptance
remain unverified. The civilian GNSS/COM tier0 ban and old SPY weather
base/COM AI predicates were deferred at this stage and addressed by package14.
Unknown legacy callbacks, shared COM cooldown and immediate traffic/base
freshness remain open. No game, saves, launcher or Workshop changes were made.

The fourteenth package admits working first-generation civilian GNSS/COM
services using positive corresponding satellite counts in current system stats,
and applies their native tier0 bonus caps. It fixes the negative SPY weather
base interval and adds explicit nonpositive-capacity branches to two projected
COM AI predicates. Positive-capacity arithmetic, traffic thresholds, native
action IDs/weights, proposal/consent lifecycle and weekly stats cadence are retained.
The native documentation gives divide_temp_variable a default if_zero=0;
the reproduced defect was a permissive AI traffic result, not a proven crash.
Fresh checks passed 6026 cumulative source-model scenarios (5932 earlier plus
94 new actual-source scenarios),
with two adapter checks counted separately and 108 new source/boundary checks.
Six existing game files changed in nine blocks/eight locale lines; 68,315 others
remain byte-exact. Historical assertions remain enabled through narrow byte
restoration, with two old absent-system fixtures made explicit about zero inventory.
Independent review binds the current six game hashes. See
[DIPLOMACY_PACKAGE_14_UK.md](DIPLOMACY_PACKAGE_14_UK.md).
Game acceptance remains pending. The shared COM cooldown and event-driven
traffic/base freshness deferred here are addressed at source level by package15;
unknown legacy callbacks retain their prior limitations. No game, saves,
launcher, Workshop, DLC, source ZIP or attribution changes were made.

The fifteenth package separates new civilian/military COM actor-owned 180-day
AI cooldowns while retaining old shared flags until natural expiry. It updates
own native COM data before known proposal/response checks and refreshes a bounded
provider/client neighborhood on consent, revocation, daily and level-selection
hooks. All own bases precede aggregate bonuses; foreign aggregates are not lent
again. Active service, client load and AI current-client detection share reciprocal
consent, live/level/peace and positive physical-capacity checks. Signed unavailable
service is dormant; positive-capacity overloaded service still counts client load.
Native own weak floors, higher-tier sending rights, unit/state weights and full
weekly update/news/downgrade remain unchanged. AI prospective traffic now covers
the current 1–1.249 gap and does not double-count active existing clients, retaining
the >1.249 threshold and native scoring weights. Four EN/RU granted rows reflect
active recipients. Fresh checks passed 6148 cumulative source-model
scenarios (6026 prior plus 122 new actual-source scenarios), separately
2 adapter semantics cases and 155 new source/boundary checks.
Eleven existing game paths contain
20 changed blocks within 22 allowed boundaries/six helpers/four locale rows;
68,310 other game files are exact. The two original revoke bodies are preserved.
All 106/285/94 previous satellite scenarios remain enabled with physically coherent
fixtures executing current game code; narrow historical byte views affect source
assertions only. Independent review binds all eleven gameplay hashes. See
[DIPLOMACY_PACKAGE_15_UK.md](DIPLOMACY_PACKAGE_15_UK.md).
Native execution, performance, AI choice, timers, arrays, modifiers, GUI, annex and
save/load still need new-campaign acceptance. Unhooked raw orbital/unit/control
changes update daily; no instantaneous global atomicity is claimed. Old request/
offer cooldown ownership asymmetry remains; it is soft AI scoring, not a human
termination ban. No game, saves, launcher, ZIP, Workshop, DLC, playsets or attribution
changes were made. Next: accept existing service cycles in game and extend the
verified lifecycle to other existing diplomatic agreements/support.

The sixteenth package develops the existing 100,000-unit `Send_ammo` offer:
donor-owned reservation, explicit recipient consent, fresh supply-node storage,
withdrawal, exact-once credit/refund and unpaid refund claims. One outgoing offer
per donor does not lock other incoming donors. Known forced cleanup retires only
the unresolved directed pair; unknown or incomplete records conservatively close
the donor's ammunition channel. Annexation queues held ownership for the successor
without changing ordinary ammunition inheritance or paying before its native hook.
The inherited political AI weights remain, with one technical readiness gate.
Official ATT and ICRC sources inform the procedural design; export licences,
embargoes, humanitarian-risk assessment and historical treaty participation are
not implemented. The ATT's 2014 entry into force is not backdated to the 2000 start.
See [DIPLOMACY_PACKAGE_16_UK.md](DIPLOMACY_PACKAGE_16_UK.md).
Fresh cumulative checks pass 6240 source-model scenarios (6148 prior plus 92
new in 32 groups), with one separately counted adapter case and 142 new
source/boundary checks (125 source/API plus 17 memory-only boundaries).
Three existing and seven new game paths are bound by matching source/behavior
hashes and independent review. All 65 existing action IDs and 41 prior
behavior/helper/runner files remain unchanged; one withdrawal action and 14
bilingual keys are added. Fourteen strict historical source adapters use narrow
prior-byte views and account for the exact new ID; current behavior proofs are
not bypassed.
Native UI, country-ID resolution, callback order, AI, timers, annexation and
save/load need new-campaign acceptance. Complete pre-upgrade ammunition offers
before upgrading an existing campaign; their unrecorded ownership cannot be
reconstructed. No game, save, launcher, Workshop, DLC, playset or attribution
change is part of this package. Next: existing logistics/reconnaissance aid and
foreign support, then permanent diplomatic relations; the current broad peace
helper needs a separate war/authority audit before executing mediation outcomes.

## Completed setup

- Imported all 74,465 source files directly into `E:\Era of Nations`; the archive
  wrapper directory was removed and ZIP CRC checks passed during extraction.
- Renamed both mod descriptors, removed the inherited Workshop ID, and retained
  all source `replace_path` directives and HOI4 `1.19.*` compatibility metadata.
- Registered a private local **Era of Nations** playset and enabled only this
  mod. Existing playset memberships and all 10 DLC selections were preserved.
- Updated 104 visible localisation values across 36 files. Keys, UTF-8 BOMs and
  line counts match the imported source. No full upstream brand remains in
  quoted localisation values.
- Installed the new logo, cover, music/radio sheets and icons. Native image
  sizes, alpha and file formats passed validation; see [BRANDING.md](BRANDING.md).
- Retained original authors and all four music credit files byte-for-byte;
  moved visible upstream notices into the attributed source archive documents.
- Connected `origin` to `Sany0ssse/Era-of-Nations`, branch `main`. Initial GitHub
  publication uses five successive asset batches without Git LFS. The final
  publication receipt is local in `.local/publication-result.json`.

## Actual game startup

HOI4 **1.19.3.0.c01a** was launched with the local descriptor. Its fresh
`system.log` reports **Active Mod Count: 1** and **Active Mod: Era of Nations**.
`setup.log` records a completed frontend startup at game date 2000.01.01.
The game process remained responsive after startup.

This confirms startup and mod selection. An unobstructed screenshot of the game
menu, starting a country, and campaign simulation have not been accepted yet.
Existing saves were not opened or changed. Local log receipts are in
`.local/runtime-check/` and launcher backups are in `.local/launcher-backups/`.

## Inherited issues to investigate next

The startup log contains inherited errors. Targeted checks confirmed that the
affected gameplay files match the supplied ZIP; the frontend differs only in
project promotional controls and links.

- The inherited frontend omits the `change_background` GUI type and background
  selection controls expected by the current game. The engine explicitly warns
  that opening that feature may crash. Do not use the background selection
  feature until its compatibility is repaired.
- `common/doctrines/subdoctrines/land/land_equipment.txt` contains a rejected
  `sub_unit_bonus` token; unit/Special_Forces references also report errors.
- Some mesh/entity, landmark, radio-song and particle references are missing or
  duplicated in the source.
- The earlier generated `gfx/main_menu/main_menu.dds` fallback has been removed;
  the static sprite directly references existing `gfx/loadingscreens/load_1.dds`.
  The final restart has no former missing-path message, but still reports two
  binary-token parse errors for that DDS. The inherited frontend lacks the
  current game's root background and selector types; the exact internal parser
  call is unverified. This compatibility issue remains unresolved.

No observed startup error names the replaced Era of Nations textures or changed
localisation syntax. This is a development baseline for further work; campaign
stability and Steam Workshop readiness remain unverified. Workshop publication
is deferred by the user.
