# Debt bailout source checks

Run from the repository root with Python:

```text
python -B tools/validation/debt_bailout/test_lifecycle.py
python -B tools/validation/debt_bailout/test_source.py
```

The first check executes current decision, option and helper AST. The interpreter
uses shared execution temporaries and native-calibrated country flag selectors.
Country identities, popup consumption, time expiry, autonomy and economy refresh
are explicit fixtures or native-call boundaries. It does not prove native AI
event consumption, autonomous policy, a campaign or save/load migration.

The initial RED proof is retained privately under
`.local/debt-lifecycle-audit/bailout-implementation/red.txt`. It exercised the
actual old money command island before replacement and caught an old popup
charging donor cash despite borrower debt already being zero. The complete
original four accounting reproductions are in `legacy-reproductions.json`.

The source check reconstructs both old files from a pinned Git baseline and
an exact byte journal. It never strips whole mutable blocks or normalizes the
files to make comparisons pass. Legacy unresolved receipts are inert; the old
shared `debt_bailout` field remains untouched because IMF also uses it.
