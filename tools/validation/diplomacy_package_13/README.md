# Remaining satellite access validation

Package13 starts from `150cb6f114f7f8896495f57206a1a854af06e056`. The current suite passes **285 actual-source scenarios in 35 groups**, with no new adapter-only cases. The runner executes the previous 5,647 scenarios separately, for **5,932 cumulative symbolic scenarios**. Source/API checks are reported separately and are not added to that count.

Run from the repository root:

```powershell
python -B tools/validation/diplomacy_package_13/run_checks.py
```

The suite loads only package12's ordered executor definitions, without running its scenario loops. Package12's registry also loads the actual extended definitions needed by the current shared COM reducer; its 106 existing behavior cases remain unchanged. Unhandled effects and triggers fail closed.

The behavior checks execute the current twelve native request, offer and revoke actions for GNSS military, COM military and SPY military/civilian. They cover all eight native acceptance/refusal callbacks, actor-owned serialization, frozen provider tiers, stale partner/incorrect kind responses, four free withdrawal decisions, legacy pointers, dormant consent, deduplicated provider IDs and all 24 service fields. Global tier bounds are read from current `set_all_sat_system_tech` literal arrays, including the negative SPY military weather bound. Mixed civilian/extended daily and both annex hooks execute in either order, with explicit callback scope and participant-existence fixtures. All six families can negotiate independently.

The four extended families now support a working first-tier constellation at literal index0 when its native current satellite-count variable is positive. This intentionally expands the original positive-index proposal policy using the existing tier0 capability table; higher-tier admission and provider-versus-recipient comparison remain unchanged. The checks cover both native proposal roles, all tier0 caps, count loss before acceptance, daily cancellation, dormant recovery and explicit revocation. Index0 with count0 remains unavailable and adds no service benefit. The older package12 civilian GNSS/COM first-tier policy is deferred and unchanged.

COM checks execute the actual current stats and receiver-load reducers: military overload uses military traffic, zero capacity removes stale military bonus, both zero-maximum coverage branches avoid division, unique treaty recipients contribute their native unit counts once, and the original capacity sums remain intact. The inherited weekly stats cadence is preserved. The two existing projected AI traffic predicates' possible zero-denominator behavior is deferred and is not represented as fixed here.

Initial focused public regressions failed against the unchanged baseline before production edits. The additional first-tier request, offer and refresh checks failed against the pre-extension helper hashes, and the parent observed these before extending the policy. Examples:

```powershell
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus duplicate --family gnss_mil
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus pending --family spy_civ
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus mil_overload
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus zero_max --family com_mil
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus negative_cap
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus zero_level --family spy_civ
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus zero_refresh --family gnss_mil
python -B tools/validation/diplomacy_package_13/test_satellites.py --focus zero_lifecycle
```

The output contains exact SHA-256 hashes for the nine changed gameplay files. Private baseline RED traces and final receipts stay under `.local/diplomacy-package-20261006-13/` and are excluded from Git.

These are bounded script proofs, not HOI4 engine or campaign acceptance. Country scopes, getters, arrays, dynamic modifier updates and timer flag presence are explicit fixtures. A recorded 30-day flag declaration proves its declared value, not elapsed native time or modal delivery. The strict zero-divide fixture identifies an unguarded script denominator without asserting how the native engine handles it. Undocumented first-versus-all duplicate removal is not assumed by production's identity-based array rebuilds. Unknown legacy pending ownership stays locked; old unidentified popups cannot be reconstructed. A forced unconsumed timeout or annex retires that actor/peer/family pair, while normal consumed refusal permits another round. No proof assumes the engine duplicates already consumed callbacks across later identical rounds. No game launch, save, subscribed Workshop file or launcher playset is changed by the runner.
