# Package 25 — actual electricity deliveries

Run from the repository:

```powershell
python tools/validation/diplomacy_package_25/run_checks.py
```

`test_delivery.py` interprets the current ordered effect/trigger AST. It does
not maintain a separately copied dispatch algorithm. It runs the actual
`calculate_energy_use` numerical source, including damage guards and storage;
the real price calculation, budget component replacement and inherited weekly
treasury arithmetic are read from current source too.

Native state/GDP aggregation is an explicit boundary: fixtures supply dynamic
power/demand inputs and state aggregates, then execute actual energy source.
Tax/welfare inputs are zero fixtures; `update_display` selects the actual rate
arithmetic nodes. Country enumeration, scopes, array indexing, numeric precision,
callbacks and actual cash remain interpreter assumptions requiring HOI4 checks.

Coverage includes multiple suppliers/buyers, proportional shortage/recovery,
import/reexport chains, source-free cycles, real-source cycles, 64-round limit,
country/contract permutation, zero price, missing/war/mismatched/duplicate
pairs, unsafe stale terms/prices, actual-only replacement capacity, daily date
latch, repeated reconciliation without another debit, weekly cash conservation,
storage bounds and zero-infrastructure denominators.

Additional scoped AI tests execute actual evaluate/prepare-counter effects:
supplier shortage returns its projection before the numerical false predicate,
fractional availability is floored, and structural failure retains the sentinel.
Terms/price snapshot tampering on either side makes both bills fail closed.
The displayed weekly energy forecast uses the current delivery snapshot;
the integrated cash update excludes this forecast. Package 27 separately meters
physical hourly GWh and executes payments, avoiding a second weekly charge.
Execution temporaries are shared within one invocation; explicit scoped reads
access persistent storage. The suite includes scoped-temp mutation regressions.

`test_source.py` checks narrow byte boundaries against `c1420b108`, BOM/EOL,
actual billing integration, report IDs, localization and existing sprites.
The historical comparison now explicitly restores exactly two later EU budget
eligibility gates and seven digest-bound migration98 money islands. The latter
match the sealed native98 money source (SHA256
`24c243eae9c63d45a6af1c0743bd411c5ea50d5c63384edc072d3e24836b6aaa`)
after the existing exact arsenal compatibility step. They cover private
remittances, physical workforce/refugee accounting, expense hooks, display
refresh and the capital-scope repair; they do not grant a general normalization.
Whole foreign prefix/suffix bytes still equal the original Git blob after the
reviewed restorations. Five EU controls and fourteen migration controls reject
missing/modified islands or preserve unrelated mutations for that comparison.
This baseline-scope migration changes tests only, not game source, and does not
add new native electricity or campaign acceptance.
Negotiation guards compare ordered AST predicates/operands after normalizing
documented var/value/compare syntax and explicit variable country targets.
The interpreter executes both comparison forms; source guards reject native
unsupported >=/<= shorthand in the owned energy files. Startup probe02 found
the former shorthand invalid; a new native probe is still required after repair.
It needs Git history for byte comparisons. Earlier package validators have
not been silently changed; their old contractual-delivery assumptions need
explicit integration adapters before claiming a cumulative green run.

Installed primary HOI4 reference: `documentation/effects_documentation.md`
(`every_country`, `for_each_loop`, `while_loop_effect`, `set_variable`),
`triggers_documentation.md` (`all_of`, temporary arithmetic) and
`dynamic_variables_documentation.md` (`global.num_days`). These support the
commands, not this mod's native compilation or campaign behavior.
