# Debt accounting checks

Run `python -B tools/validation/debt_accounting/run_checks.py` from the mod root.

The suites execute actual current GUI callback/helper ASTs and test conservation,
cash/debt/nominal bounds, exact and partial settlement, zero/negative cash,
repeated repayment, loan capacity including the inherited 1% capitalized fee,
automatic overdraft borrowing, and matching button eligibility.

Economic aggregation is an explicit boundary in the source interpreter. Native
probe 38 uses actual callback copies and the product economic updater with
synthetic financial inputs. Neither source checks nor callback probes establish
rendered GUI clicks, a full fiscal campaign, save/load, or multiplayer behavior.

Byte guards preserve unrelated original bytes/BOM/EOL. `byte_compat.py` is an
exact digest-bound inverse used only for historical source comparisons; it
rejects altered accepted debt bodies before restoring the baseline. Actual
behavior tests always execute current game files.
