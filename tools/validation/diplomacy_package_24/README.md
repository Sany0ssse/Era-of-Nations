# Investment construction lifecycle, package 24

Run from the repository root:

```powershell
python tools/validation/diplomacy_package_24/run_checks.py
```

The package executes the actual current proposal, project, selected-state GUI,
daily clock, cancellation, refund and annex-hook scripts in a bounded interpreter.
The interpreter is adapted from package 02; it adds native `OWNER` scope,
separate country/state temporary namespaces, explicit PREV/ROOT temporary
reads/writes, targeted-variable addressing and a successful/rejected building-level
outcome. A rejected native command is deliberately possible in the model. Random
success and corruption are separate fixture outcomes, not probability estimates.

The financial invariant includes cash, pending principal, operating assets,
recorded losses and durable refund claims. Recipient advances and consumed
cofinancing are tracked separately. Tests include all 15 buildings, fractional
unit accounting, exact final residuals, policy/war/ownership/control pause,
resumption, real cancellation visibility/enabled/click paths, wrong state-slot
protection, original payer refunds, treasury ceilings, native rejection and retry,
corruption, partial cancellation, two projects and actual annex hook effects.
Scope regressions poison same-named state/recipient temporary values and check
later-entry cleanup in a state after an earlier cleanup in the same environment.
Per-unit checks require both the donor and recipient pending ledgers to decrease.

The source verifier reads the real baseline Git blobs and compares unchanged
regions directly. The inherited legacy body has one native comparison syntax
repair and proposal eligibility has two; these three exact literal replacements
are explicit in the baseline comparison. All other legacy and unauthorized
GUI/effect bytes are preserved. It does not reverse a saved byte journal. If installed engine
documentation is available, it checks and hashes the primary native API docs
and installed vanilla scoped-temporary examples.

Native probe 02 rejected six shorter `check_variable` comparisons using `>=`
or `<=`. They now use the documented `var`, `value`, `compare` form. The model
rejects undocumented short operators and executes all six documented full-form
comparisons, including equality boundaries and scoped variable right operands.
The separate 35 grammar cases and 455 current-source checks supplement the 402
project scenarios and 12 source groups. These fixes still require a new native
compiler probe; source parsing does not establish engine acceptance.

Package 02's original immediate-ROI and exact-byte expectations intentionally no
longer describe the new protocol. Those validators are unchanged and are not
reported as passed against this change. Older existing projects remain on an
explicit legacy path rather than receiving guessed financial metadata.

These are source checks. Engine scheduling, read-after-instant-build behavior,
real UI rendering, annex ordering, saves and multiplayer still require the
campaign checklist in `docs/development/DIPLOMACY_PACKAGE_24_UK.md`.
