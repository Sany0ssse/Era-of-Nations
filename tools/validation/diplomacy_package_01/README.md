# Diplomacy package 01 checks

Run from any checkout containing the pre-package Git commit:

```powershell
python tools/validation/diplomacy_package_01/run_checks.py
```

Requires Python 3.10+ and Git; no third-party Python dependencies. The scripts
read the current gameplay source and preserved baseline commit
`15de79473f59ada089b98d1757a8c1fe34893f9b`. Fetch that commit if using a shallow
clone. They do not modify game files, saves or private test receipts.
Whitespace checks recognize the game's uniform CRLF files as line endings and
inspect both staged and unstaged changes without changing Git configuration.

The models execute supported source branches and reject unsupported statements.
They check alliance admission/removal, delayed SCO eligibility, financial and
operative callbacks, bilateral energy proposals, cancellation, annex cleanup,
weekly energy accounting, source boundaries, localization and byte formats.
Inherited GUI refresh/influence/AI calculations have explicit model limits.

These are source checks, not a substitute for the new-campaign, native callback,
AI, actual treasury and save/load checks in
[`DIPLOMACY_PACKAGE_01_UK.md`](../../../docs/development/DIPLOMACY_PACKAGE_01_UK.md).
