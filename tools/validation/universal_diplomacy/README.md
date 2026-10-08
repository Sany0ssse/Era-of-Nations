# Representative-country diplomacy checks

Run from the mod checkout:

```powershell
python -B tools\validation\universal_diplomacy\test_relations.py
python -B tools\validation\universal_diplomacy\test_registry.py
python -B tools\validation\universal_diplomacy\test_maritime.py
python -B tools\validation\diplomacy_package_26\run_checks.py
python -B tools\validation\diplomacy_package_28\run_checks.py
```

The embassy regression executes the current source AST for USA, GER, UKR,
BRA, SWI and NEP using explicit eligible fixture states. Execution temporaries
are shared within an invocation; scoped variable reads access persistent
country state. The old scoped dispatch mutant must reproduce the missing
incoming proposal and the old frozen source is retained privately.

Native selector controls also distinguish country flags from variables:
literal tag flag suffixes store a different key from an actual country-scope
suffix. Package 26 checks the bounded historical writer inventory and exact-peer
compatibility for old literal receipts, with proper records taking precedence.
Variable key resolution remains unchanged.

The maritime checks exercise shared actor/target guards and bounded equipment
effects. Country tags, major status and continental naval power must not confer
permission. Peace, dependencies, missing capabilities, stale legacy flags,
repeat execution and restart during cooldown must remain guarded.

These are source regressions. Private native HOI4 fixtures separately test
representative country flows and retain immutable source hashes, launch
identity, labels, counters and logs. Neither layer proves a complete campaign,
player UI, native save/load or multiplayer synchronization. The Ukrainian
product report records the actual native result and legal boundaries.
