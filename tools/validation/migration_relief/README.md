# Migration and refugee flow validation

```powershell
python tools/validation/migration_relief/test_flows.py
```

The bounded interpreter loads and executes actual migration effect and trigger
AST from the game files. It reuses the repository's parser and fails closed on
unsupported primitives. Country counters, global scratch pointers, STATE
population, and origin-indexed STATE arrays are separate model objects.

Country scope tokens are deliberately fractional and distinct from the integer
origin slots used by the STATE ledgers. The actual registry AST is executed:
append-only mapping, repeated registration, recovery of an overwritten slot,
copied variables on a genuinely new country, and full-token cohort return.
Restricted aid balances and weekly payment locks survive same-country recovery;
only a genuinely new copied registration discards inherited financial receipts.

Coverage includes exact conserved debit/credit, refugee and worker receipts,
returns and onward relocation, missing/wrong pointers and amounts, source-stock
limits, fresh-arrival and long-term-resident exclusion, weighted cohort ages,
integration and prolonged-residence calibration, territorial control changes,
once-weekly fund consumption, integration/long-term emergency-cost tapering,
controlled damaged home-state relief needs, and zero denominators. Monthly phase
order, the 27-day pulse lock, and final scratch cleanup are inspected in source;
flow scratch consumption and the first global fresh-clear phase execute the AST.

Long-term residence is an aggregate game calibration, not a citizenship grant.
Domestic relief is a needs estimate rather than a second population stock. Both
have regressions confirming no copied or removed residents and actual fund debit.

No national role table is used: state cohorts retain their origin when ownership
or control changes. Native selection is modeled deterministically by taking the
first eligible scope. Native random choice, actual engine country/state IDs,
variable-scope binding, array resizing, population/manpower behavior, campaign
balance, multiplayer synchronization, and performance still require an actual
HOI4 probe and campaign. The tests do not launch a game or alter saves.

`build_native_probe.py` prepares a separate, hash-bound fixture and manifest.
It does not launch the game. `analyze_native_probe.py` requires both completed
game/error logs and verifies every ordered assertion, the frozen production
bytes, fixture bytes and installed engine documentation. Missing, duplicated or
interleaved records, a partial run, changed files or relevant script errors fail
the receipt. Native helpers use real STATE population and country scopes; a
helper receipt still does not establish diplomatic UI, save/load or MP acceptance.
