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
The inherited weekly charge uses the current delivery snapshot at that tick;
there is no accumulated daily/hourly GW/GWh delivery ledger in this package.

`test_source.py` checks narrow byte boundaries against `c1420b108`, BOM/EOL,
actual billing integration, report IDs, localization and existing sprites.
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
