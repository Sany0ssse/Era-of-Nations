# Existing foreign financial support validation

Package18 starts from `0a8063bf3bc732fbc7ab453b116ddf61e5c090d4`. It executes current `AB_mobilization.4.c`, recipient assent or rejection, hidden provider execution, native withdrawal, daily cleanup and both annex-hook frames through the existing ordered interpreter definitions. Loading definitions does not execute preceding scenario loops. The cumulative runner separately executes all **6,413** previous scenarios against current gameplay.

```powershell
python -B tools/validation/diplomacy_package_18/run_checks.py
```

New coverage is **126 current-source scenarios in 25 groups**, plus **four separate adapter checks** for explicit defensive-war fixtures. Expected cumulative current-source scenarios: **6,539**. Source validation adds **130 source/API checks and 17 memory-only byte-boundary checks**, for **147** checks. Source and behavior receipts must carry identical gameplay hashes.

The three PUBLIC REDs execute the actual existing cash option, without restoring baseline gameplay:

```powershell
python -B tools/validation/diplomacy_package_18/test_foreign_cash.py --focus legacy_insufficient
python -B tools/validation/diplomacy_package_18/test_foreign_cash.py --focus legacy_replay
python -B tools/validation/diplomacy_package_18/test_foreign_cash.py --focus legacy_credit_loss
```

Before correction, a donor with 1 unit paid 7 and reached −6; repeating the callback transferred another 7; a recipient at 999,999 accepted only 1 of the 7 while the donor lost the full amount. Current choice `.4.c` offers the original one-off 7-billion grant without moving money. Recipient event `.1` marks consent once and queues hidden provider event `.2`. The provider then verifies the same owned pair, consent, reply period, current policy and full treasury capacity before consuming the record and executing the original −7/+7, +3 influence macro and `AB_mobilization.7` sequence.

The separate provider event preserves original native `ROOT = provider` and `FROM = recipient`, because the existing influence macro reads `ROOT` for resource rights. Tests observe its actual call site, context and parameters; they do not claim full native influence or resource-rights calculations. Money, influence calls and confirmation are absent between offer and consented execution. Consent prevents duplicate execution queues, rejection and withdrawal; a failed final check closes the matching proposal unpaid.

Coverage includes exact valid funds/cap boundaries, out-of-range treasury protection, fresh donor and recipient ranks, defensive-war loss, request-marker loss, opinion and direct-war changes at each frame, wrong pair and self callbacks, repeated replies and commit, one provider pending partner, free withdrawal, permanent directed retirement after an unresolved timeout, unknown-partner quarantine, seven malformed records, daily transient policy/funds changes and both annex-hook frames before or after fixture disappearance. Cash, debt, political power, equipment, service fields and unrelated diplomatic records are preserved outside the committed gift. The grant creates no loan, recurring agreement, repayment, escrow or refund.

Only the named `AB_mobilization.4.c` option changes in the inherited war file. All surrounding headers, other options, events, IDs, BOM and line endings remain exact. Its original donor AI block remains raw-byte exact. The original AB action, troop/equipment alternatives, mercenary path, paid service implementation, GUI, budget helper and influence macro remain untouched. The AB action's **nominal 50-PP cost and 360-day request marker** are checked as unchanged source declarations. This packet does not own that original request, prove its native cost/callback ordering or refund its entry cost.

Only historical source-preservation validators use the single-option old-byte view. Sixteen literal whole-validator journals cover source02–17, reject undeclared edits and preserve every original counter line. All **62** prior public validation files outside those journals remain raw-byte exact, including all **45** preceding behavior/helper/runner Python files. Source01 stays unchanged. Source02 recognizes only the one new cash-withdrawal ID; the remaining historical source views exclude exactly the separately validated new paths and action ID. Previous behavior suites execute current gameplay without byte restoration or relaxed cases.

Country identity, ranks, opinion, request-marker presence, direct wars, treasury balances, existence and defensive-war classification are fixtures. Defensive war is modeled independently from a generic war set and checked against the installed primary trigger declaration. Temporary variables resolve by current country, including explicit `PREV` references. Flags validate timer declarations and supplied expiry facts, not native elapsed time.

The engine exposes no popup generation token here. Wrong-partner callbacks and replays without a new matching reservation are covered. Arbitrary replay of an already consumed popup across a later proposal to the **same partner**, or hidden commit replay across a later consented reservation for that same pair, is not proven. The unchanged request marker is nominal eligibility, not a unique request receipt. Unresolved expired pairs are permanently retired; unknown malformed records quarantine only the provider's cash-offer channel. Those restrictions are stated game limitations, not real-world diplomatic rules.

Actual country-ID round trips, hidden-event queue ordering, AI choices, native PP charges, timers, save/load and a playable campaign require an in-game acceptance run. This suite does not launch HOI4 or prove legal authority to support a country. Saves, Workshop subscriptions and launcher playsets remain untouched. Private receipts live in `.local/diplomacy-package-20261006-18/`, outside Git.
