# Simulation work regression checks

Run `python -B tools/validation/performance_policy/run_checks.py` from the
repository root. These tests execute actual source ASTs with explicit engine
inputs, reject changes outside the owned source regions, and verify reduced
repeated work. They do not measure FPS or native campaign duration.

- Ammo: preserve production, consumption order, war/volunteer eligibility and
  the potato rule while sharing one daily participation query.
- Energy: preserve ordered reciprocal delivery, former-participant cleanup,
  war/annexation handling and settlement calls while iterating a fresh participant
  array instead of every country in every phase. Test an unrelated caller break.
- EU: preserve public helper behavior and both lifecycle boundary refreshes,
  membership/withdrawal/deadline outcomes, and source bytes. Only the redundant
  GUI invalidation serial increment is intentionally removed.

Fixtures are exact pre-optimization source files, including original line
endings. The energy compatibility catalog preserves historical package checks
through an exact, hash-bound source projection; unknown edits fail closed.

Native timing, fixture details and limits are recorded in
`docs/development/PERFORMANCE_UK.md`. Private profiles and receipts stay in
`.local/performance-audit-20261012/` and `.local/ai-audit-20261012/`.

Port tally checks cover the whole actual fleet/air/land calculator and its source
bytes. The inherited result min(actual docked ships,100) remains. Adaptive
queries never exceed the original across 307 controlled counts; dense maximum
is 14 queries and 100+ ships takes 8 versus 101. Zero ports still take 1, one ship
takes 2 versus 3. This is query work, not FPS or measured campaign duration.
Native 1.19.3 pure-helper observation covered 5 countries, 2590 state traversals,
22 positive ports and a real 100+ ship port with matching capped count 100.
Native while resets its break temporary on entry. A new explicit unique break
preserves the unrelated caller temporary; no old physical-count bug was found.
Private receipts and failed fixture probes remain outside Git.
