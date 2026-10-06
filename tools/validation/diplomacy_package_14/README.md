# Civilian first-tier and satellite arithmetic validation

Package14 starts from `f25dcfa040df4de947fe87e7a70f8f5fdd9ed659`. The current suite passes **94 actual-source scenarios in 18 groups**, plus **2 adapter-only checks** for native temporary division. Its 96 total checks do not imply 96 gameplay scenarios. The runner executes the previous 5,932 scenarios separately, for **6,026 cumulative symbolic scenarios**; the two adapter checks and source/API checks are reported separately.

Run from the repository root:

```powershell
python -B tools/validation/diplomacy_package_14/run_checks.py
```

The suite loads only package13's ordered executor definitions, not its 285 scenario loops. Previous suites run separately. Unknown effects and triggers fail closed. The only permitted historical behavior edits make two existing package12 absence fixtures explicit: an index0 provider has native satellite count0 in its dormant and unavailable scenarios. The 106 existing cases and their assertions stay unchanged; the 285 package13 cases stay unchanged.

Civilian GNSS and COM now share the working first-tier rule already used by the four extended families: index0 requires a positive corresponding native satellite-count variable. Higher tiers and provider-versus-recipient comparisons remain intact. Actual request/offer callbacks, all eight civilian fields at literal tier0 caps, unknown legacy ownership, wrong partner/kind responses, count loss before reply, daily cancellation, dormant recovery and explicit revocation are covered. Two same-tier providers sum once and use the tier0 bound; a mixed first/higher-tier pair uses its strongest eligible native cap. Revoking one preserves the other. Both existing annex hooks remove active first-tier consent and retire unconsumed pending pairs while allowing a new different partner. All six families can negotiate independently; withdrawing one civilian proposal leaves the other five intact and grants no economic reward.

The native SPY military base calculator runs for all eight actual table levels with bonus0,0.25,1 and2. Its negative weather field stays between its nominal bound and weakest literal bound; full and proportional coverage no longer clip toward zero, and excess bonus cannot exceed the nominal cap. The other five positive fields retain their original calculations. Global min/max arrays come from current `set_all_sat_system_tech` declarations, without invented capability bounds.

Both projected COM predicates are checked at zero and negative provider capacity, without executing a divide, and at positive capacity with the original current/projected traffic thresholds and native recipient-unit getters. ROOT is the provider and THIS is the prospective recipient. The existing positive-capacity behavior at traffic1 remains unchanged. The helper result affects existing offer/revoke AI evaluations; their weights remain unchanged, and complete AI decisions are not represented as verified. It adds no native action, human admission gate or political policy. Package14 models the installed1.19 documentation's temporary-divide default `if_zero=0`; the baseline defect returned false for projected overload at capacity0. It is not an engine-crash claim. The two adapter checks cover that default and a nonzero ratio; custom explicit `if_zero` syntax is not exercised. Historical primitive fixtures remain unchanged.

Focused public RED traces were captured before production changes:

```powershell
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus zero_level --family gnss
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus zero_offer --family com
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus zero_refresh --family com
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus weather_base
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus weather_overlimit
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus projected_zero --family mil
python -B tools/validation/diplomacy_package_14/test_satellites.py --focus projected_zero --family civ
```

The output records the exact SHA-256 hashes of the six changed gameplay files. Private RED traces, fixture-preservation proof and final receipts remain under `.local/diplomacy-package-20261006-14/`, outside Git.

These are bounded ordered script proofs, not HOI4 engine or campaign acceptance. Scope, unit getters, current constellation counts, arrays and dynamic updates are explicit fixtures. Timer flag presence is supplied, rather than elapsed native time or confirmed modal delivery. Unknown legacy ownership remains locked, and old unidentified popups are not reconstructed. The runner does not launch the game or change a save, subscribed Workshop file or playset. Weekly statistics cadence, existing native IDs, AI weights and cooldown flags, including the shared civilian/military COM accepted flag, remain unchanged. A safe typed cooldown migration and immediate full traffic/base refresh are deferred.
