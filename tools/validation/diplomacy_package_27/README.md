# Package 27: electricity invoices

Run with Python 3, from the checkout:

```powershell
python -B tools/validation/diplomacy_package_27/run_checks.py
```

`test_settlement.py` executes the ordered AST of current delivery, contract,
invoice, actual decisions and event/on-action scripts. Execution temporaries
are shared by nested country scopes within one invocation. Explicit scoped
reads such as `PREV.name` access persistent country storage, rather than a
country-local temporary. Financial assertions use
the actual source: `charge = unpaid + paid`, `paid = received + escrow`, overdue
is a subset of unpaid, and treasury plus escrow is conserved.

Native one-hour event delivery is an explicit fixture. The fixture's numeric
date increment simulates a clock that changes every game hour; game scripts do
not subtract date values or assume their numeric unit. GDP/state aggregation,
country enumeration, native queue/save-load and rendered UI remain native
boundaries. Copying the fixture is not a native save-load test.

Finite precision modes (3 and 5 fractional digits, truncation on each write)
are adversarial cases. Installed documentation describes fixed-point math
expressions; the actual precision of these legacy variable effects has not
been calibrated. The scripts accumulate physical GWh before valuing cumulative
invoices; they do not sum 168 independently truncated tiny currency amounts.
Raw GWh, cumulative numerator and nonnegative remainder are never cleared by
payment or contract termination. A claim smaller than the engine's smallest
currency quantum is retained as measured physical history, not invented cash.

`test_source.py` pins the pre-package baseline `f2832b6` and proves exact bytes
for the two existing game files with hooks. It checks source/API/grammar,
immutable ledger columns, cash barriers, zero PP cost, numeric event IDs,
localization keys and BOM/EOL. It is not a native compiler.

The current clock latches by date equality. A missing callback under 24 hours
cannot be reconstructed from the documented `num_days` variable; native queue
delivery and hourly date changes must be verified before campaign acceptance.
A detected multi-day gap is flagged and unknown elapsed time is not billed.

`test_rounding.py` executes the actual cumulative-quota payment and receipt
scripts with synthetic historical-meter fixtures. Immutable invoice order is
used. Intermediate allocations are differences of cumulative proportional
targets; the final target uses the frozen total available budget directly.
This spends representable cash/headroom even where individually truncated
quotas used to leave an unpayable residual. Zero rows, paid history, clipping,
permutations, repeated controls and seeded ledgers are included. No currency
quantum is guessed, and no claim is written off.

A rounded reciprocal divisor can amplify the difference from the ideal
proportion. The suite reports its observed maximum, without claiming
one-quantum accuracy. Native precision and arithmetic range remain separate
acceptance checks. Native08 observed the unchanged `.100` hourly queue and
day-counter resets over more than fourteen days; it did not verify the newly
changed cumulative payment/receipt scripts or native save-load.

Source hashing and cases are printed by the runner. Package 25's existing
delivery suite loads the real new invoice hooks; it does not skip them.

Native31 (2026-10-09) accepted 34 backend guards over 168 real calendar hours
against tree bce6c853f7ab764604f5a97e72c01f1e737e6a10: actual 32/16 GW,
5376/2688 GWh and 2/1 invoice charges. A separately labelled fiscal replay
retained those measured volumes while resetting only receipt/debt columns
and synthetic budgets; payment, arrears, duplicate controls and seller escrow
passed. Source/observer ordering may lag by at most one jointly checked hour;
only the final callback closes the actual final interval. Synthetic agreements
and generation do not prove negotiation acceptance, UI clicks, save/load,
multiplayer, arbitrary engine rounding or a complete campaign.
