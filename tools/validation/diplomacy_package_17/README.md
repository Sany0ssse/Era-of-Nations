# Existing military-service agreement validation

Package17 starts from `b1568ffc7ae3d0809be0912be68bb76ab4fb0e28`. It executes current `influence.501` service choices, typed recipient responses, native withdrawal/termination actions, daily cleanup and annex hooks through the existing ordered interpreter definitions. Loading definitions does not execute earlier scenario loops. The runner separately executes all **6,240** previous scenarios against current gameplay.

```powershell
python -B tools/validation/diplomacy_package_17/run_checks.py
```

There are **173 current-source scenarios in 61 groups**, plus **two separate adapter checks** for current/previous-country temporary values and an in-memory cross-scope regression. Cumulative current-source scenarios: **6,413**. New source validation adds **164 source/API checks and 16 memory-only byte-boundary checks**, for **180** checks. Gameplay hashes must agree between source and behavior receipts.

The initial PUBLIC REDs were observed before the corresponding gameplay corrections:

```powershell
python -B tools/validation/diplomacy_package_17/test_services.py --focus legacy_replay
python -B tools/validation/diplomacy_package_17/test_services.py --focus legacy_insufficient
python -B tools/validation/diplomacy_package_17/test_services.py --focus cross_kind_reject
```

The unsigned original logistics callback charged its 3-unit fee twice and could debit a receiver with only 1 unit of treasury. The first owned draft still allowed a consumed logistics rejection to close a later reconnaissance proposal for the same pair. Current unsigned `influence.506.a/b/c` callbacks only close legacy type flags when no owned request exists. Two former acceptance IDs remain present but hidden; the visible close option does not buy a service. Current requests use separate logistics `.1` and reconnaissance `.6` events with a literal type for both acceptance and rejection.

Current-source coverage includes the original 3/4 upfront prices, 80-day ideas and influence/opinion call parameters, payment only after fresh consent, payer funds and provider treasury-cap boundaries, changed war/influence/industry/ERI restrictions, one provider pending record, wrong pair/type and repeated replies, competing providers, independent types, free withdrawal, partial records, timeouts and directed retirement, either-party termination, peace/war/idea/expiry cleanup, and both annex-hook roles before or after a fixture country disappears. A completed fee remains nonrefundable. The agreement adds no personnel, fuel, equipment stock, units or transport expenses.

The inherited GUI, national policy, mercenary choices and other events remain byte-exact. Original acceptance AI blocks remain byte-exact in their respective typed responses; the original rejection AI block is duplicated unchanged for both types. A new recipient ledger owns only the idea created by this agreement. Existing unsigned ideas are neither migrated nor removed by daily cleanup. An unknown pending partner quarantines only that provider's service-offer channel; unresolved known requests permanently retire that directed pair after timeout. Both cases remain explicit game limitations, not real-world diplomatic rules.

Only source-preservation validators use the exact old-byte view for the two named event bodies. Fifteen literal whole-validator journals cover source02–16, reject undeclared edits and preserve all original counter lines. All **59** prior public validation files outside those journals remain raw-byte exact; these include all **43** prior behavior/helper/runner Python files. Source01 remains unchanged; source02 adds only the three known native action IDs to its existing count. Historical validators retain their assertions and execute source checks with the separately validated new paths and IDs excluded from old ownership views. Prior behavior suites execute current gameplay, without restoration or relaxed cases.

Country identity, wars, government, influence slots, industrial capacity, idea ownership, flag values, scope frames and timer presence are explicit fixtures. The new adapter resolves temporary values by country and resets temporary namespaces for each new operation; it does not rely on GUI-trigger leftovers. Timed flags verify declarations and supplied expiry facts, rather than actual native elapsed time. Political macros are observed at their current-source call sites and arguments; full native political calculations are outside this suite.

The native engine provides no popup generation token for these callbacks. The suite proves wrong-kind and wrong-partner isolation and replays without a new matching reservation; it does not prove arbitrary replay of an already consumed popup across a later proposal of the **same type to the same partner**. Expired unresolved requests are covered through permanent directed retirement. Actual country-ID round trips, popup ordering, AI choices, save/load and native scheduling still require an in-game acceptance run. Existing unsigned service offers should be closed before upgrading an old campaign; existing unsigned timed ideas remain untouched.

This suite does not launch HOI4 or prove a playable campaign, real transport/personnel, intelligence sharing, end-user controls, export licensing or legal permission to provide military support. Saves, Workshop subscriptions and launcher playsets are untouched. Private receipts remain in `.local/diplomacy-package-20261006-17/`, outside Git.
