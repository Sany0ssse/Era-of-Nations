# Finished reactor-fuel transaction checks

Run from the authoritative checkout:

```powershell
py -3.11 tools\validation\nuclear_fuel_trade\run_checks.py
```

The suite executes the current effects and triggers from the game files. Its
oracle checks ownership and conservation, explicit consent, correct actors and
kind, immutable terms, one settlement, refundable assets, stock/cash shortage,
capacity, expired modal consumption and annex ownership. Nine deliberately
broken AST controls must fail those same behavioural assertions. The adapter
reuses the established package 27 parser/scopes/arithmetic, adding only explicit
native event observations and an optional float32 write boundary.

57 test groups currently pass, including the generated optional waiter AST,
its first-frame counter ordering, and an executable genuine seller-refusal
scenario evaluated through the unchanged `energy.1` AI policy.
Three builder checks preserve the original division strings through repeated
private control emission, native escaped log quotes and nested guarded payloads.
The builder preserves the parser's lexical escapes and checks each generated
control overlay against its intended AST; these checks reject the former JSON
double-escape bug without establishing native campaign behavior.
This is source-level evidence. It does not prove
native event delivery, natural 30-day flags, AI decisions, human GUI operation,
save/load, multiplayer or campaign balance. Three/five decimal truncation and
float32 are adversarial arithmetic modes; a real native probe is still needed.

## Gameplay and accounting rules

- Natural uranium extraction and native resource trade are separate from this
  finished-fuel purchase/sale interface. Finished inventory is kg of uranium in
  reactor-grade material, not ore, fuel-assembly gross weight, or weapons grade.
- Positive editor quantity means the initiator buys; negative means it sells.
  The existing `energy.1` and `energy.10` reply IDs remain.
- The send backend first invokes the shared country initializer for the sender
  and its existing selected counterparty, then computes the quote. This avoids
  mixing old campaign stock units with kilograms. Source trade fixtures declare
  kilogram inventories; their explicit initializer boundary/order test is not
  a second implementation or independent proof of the shared migration itself.
- The editor price is **thousand USD/kg**. Default 0.5 means a game quote of
  $500/kg. The desired cash amount in bn USD is `abs(kg) * price / 1000000`.
  This quote is an explicit game abstraction, not a precise observed spot price
  for all fuel types, enrichments, contracts or campaign dates.
- Currency and inventory are subject to native numeric precision. Quote
  preflight measures simulated debit/credit; both must represent the same
  positive cash delta. A zero delta or unequal debit/credit rejects the offer.
  `eon_nuclear_fuel_trade_quoted_total` is the raw desired quote;
  `eon_nuclear_fuel_trade_total` is the actual frozen cash amount, which the
  response description should show. Representable rounding may change the last
  digits of that amount. No free material is delivered for a zero cash delta.
- The initiator reserves only its own asset: cash for a purchase, material for
  a sale. The invited country can refuse without committing assets. Acceptance
  repeats current counterparty cash, stock, war, capacity and precision checks.
- Both native embargo directions and the actual supplier's
  `eon_nuclear_fuel_exports_blocked` policy apply at quote and reply. A buyer's
  own export restriction does not prevent importing. A later policy change
  prevents delivery; consuming the original refusal/invalid reply returns the
  held asset. Daily cleanup does not cancel an otherwise live offer solely
  because that policy changed.
- Physical delivery and fuel refunds call the read-only
  `eon_uranium_refresh_energy` projection for affected countries. It refreshes
  current power without creating material or settling another week. The source
  suite checks that handoff; native fixtures execute the actual helper.
- The source `energy.10` AI purchase policy measures benefit against a 26-week
  reserve gap, capped at 50 preference points. It declines no-demand purchases
  and lots exceeding that gap by more than one 500kg editor step. A large kg
  figure cannot overwhelm the price penalty by itself. Human choices and the
  consent/accounting backend are unchanged. These buffer/step values are
  transparent game policy, not claims about a universal real procurement rule.
- The offer is live for 30 game days. Expiry/war returns the held asset and
  preserves the original incoming modal identity until its response is consumed.
  Restoring a live flag does not revive phase 4 or spent escrow.
- After a reply, both slots remain reserved until the initiator acknowledges
  the corresponding original result. This protects later offers from an older
  native modal; acknowledgement itself transfers no assets.
- Refunds exceeding the treasury/stock cap, or unrepresentable at the current
  currency magnitude, remain owned deferred claims. Daily cleanup releases
  only a positive amount that can be credited without exceeding the claim.
- Vanished/corrupt partners retire only the affected pair. A native legacy
  offer with no immutable record is refused safely; this pair is retired
  because the number/identity of older legacy popups is unknown. There is no
  automatic retroactive transfer based on its editable GUI fields. An original
  pre-migration result acknowledgement can release identifiable legacy locks
  and retire its pair, without replaying or refunding an already-made transfer.

## Integration islands for existing shared files

The backend owner edits only the three new game files in this package. The main
implementation owner must wire the following exact entries into the existing
GUI/events/on-actions while preserving IDs, BOMs and line endings.

### GUI send

Replace only the existing finished-fuel confirm trigger/effect bodies:

```text
confirm_nuclear_fuel_sell_click_enabled = {
    custom_trigger_tooltip = {
        tooltip = eon_nuclear_fuel_trade_unavailable_tt
        eon_nuclear_fuel_trade_send_ready = yes
    }
}
confirm_nuclear_fuel_sell_click = { eon_nuclear_fuel_trade_send = yes }
```

The send effect revalidates independently of that rendered enabled state.
While reserved, lock edits/partner switching for clarity; even forced changes
cannot affect immutable terms. Offer selection should include eligible finished
fuel sellers that have stock even if they have no domestic power reactor.

### Original receiver replies

`energy.1` is a purchase initiated by FROM (`response_kind = 1`). `energy.10`
is a sale initiated by FROM (`response_kind = 2`). Replace each accept effect:

```text
set_temp_variable = { eon_nuclear_fuel_trade_response_kind = 1 }
eon_nuclear_fuel_trade_accept = yes
```

and its refusal effect:

```text
set_temp_variable = { eon_nuclear_fuel_trade_response_kind = 1 }
eon_nuclear_fuel_trade_refuse = yes
```

Use kind 2 in `energy.10`. Acceptance `trigger` and an AI zero-factor invalid
modifier must initialize the same kind and call
`eon_nuclear_fuel_trade_response_ready = yes`. Keep a closing/refusal option
available for expired or legacy windows. Do not add an accept fallback that
calls the old mutable transfer. Native AI replies use the same backend; no
hardcoded 500/.25 settlement branch remains.

Descriptions and AI policy operands should read **frozen** local fields
`eon_nuclear_fuel_trade_quantity`, `price`, `total`, `phase`, and partner.
Quantity is positive in both records; where an old sale AI expression expects
a negative signed quantity, explicitly invert a temporary for that expression.
The inherited baseline price 0.05/old scaling is incompatible with the new
price units; compare AI price to the declared 0.5 game quote instead.

### Original sender result acknowledgement

Replace old broad flag/GUI-variable clearing with these exact temporary inputs
and `eon_nuclear_fuel_trade_acknowledge = yes`:

| Event | response_kind | result_kind |
|---|---:|---:|
| energy.2 | 1 | 2 |
| energy.3 | 1 | 3 |
| energy.11 | 2 | 2 |
| energy.12 | 2 | 3 |

```text
set_temp_variable = { eon_nuclear_fuel_trade_response_kind = 1 }
set_temp_variable = { eon_nuclear_fuel_trade_result_kind = 2 }
eon_nuclear_fuel_trade_acknowledge = yes
```

Wrong partner, role, direction, result type or an unconsumed expired response
cannot release another record. Result descriptions should explain that an
invalid/expired offer transferred nothing, or that a refused reservation was
returned. Do not promise a future shipment: this package models spot delivery
atomically when the explicit reply accepts.

### Daily and annex hooks

Call `eon_nuclear_fuel_trade_daily_cleanup = yes` in each current country's
daily effects. A hidden scheduled observer is also queued for day 31; it checks
the current live window, so a previous observer cannot expire a fresh offer.

Before normal annex inheritance, in the annexed country's scope:

```text
set_temp_variable = { eon_nuclear_fuel_trade_successor = ROOT.id }
eon_nuclear_fuel_trade_transfer_annexed_assets = yes
```

Here ROOT must be the actual annexing country supplied by the native hook. This
transfers only held trade escrow/deferred claims, never ordinary treasury or
ordinary reactor inventory already inherited elsewhere. For surviving parties:

```text
set_temp_variable = { eon_nuclear_fuel_trade_annexed_partner = FROM.id }
eon_nuclear_fuel_trade_cleanup_annexed_pair = yes
```

Here FROM must be the actual annexed country, not a nested event sender. The
original hook's frame and order must be verified natively.

### New Russian/English localisation keys

| Key | Suggested Russian meaning |
|---|---|
| eon_nuclear_fuel_trade_unavailable_tt | Для сделки нужны свободный дипломатический канал, положительная цена, достаточные запасы и средства. Сумма должна одинаково учитываться обеими казнами; при слишком малой сумме увеличьте объём. |
| eon_nuclear_fuel_trade_settled_tt | Согласованный объём реакторного топлива и оплата переданы один раз. |
| eon_nuclear_fuel_trade_expired_tt | Предложение истекло или условия изменились. Топливо и оплата не переданы; собственный резерв возвращён либо сохранён как требование возврата. |

These strings describe outcomes, not script internals. Display kg, thousand
USD/kg and the actual total cash amount explicitly in the existing offer UI.

## Private native preparation and recorded acceptance

The builder only prepares files from an immutable source export; it never
embeds, launches the game, changes the normal profile or publishes anything:

```powershell
py -3.11 tools\validation\nuclear_fuel_trade\build_native_probe.py --source-root <private-export-source> --out <new-private-fixture>
```

The native player is NEP, leaving USA and HOL as AI. A parent fixture embeds
the prepared `mod/` files into that private export and queues
`USA = { country_event = { id = eon_private_fuel_probe.1 hours = 1 } }` after
any other fixture using USA has finished. `--startup` is optional; shared actors
must still be serialized. The private weekly/monthly and fuel GUI AI overlays
are explicitly listed and hash-bound. They freeze unrelated accounting and
autonomous offers during the experiment; production `energy.1/10` response
policies, options and separately queued result events remain unchanged.
Native money-GUI AI weights and the mine-expansion decision AI receive a
private zero-weight guard only for USA/HOL while this fixture is active.
Their click/project effects stay original. This prevents ordinary debt
repayment or new mine spending from obscuring the measured fuel cash transfer;
these controlled cases do not prove combined ordinary economy behavior.

Five required cases cover both accepted directions, both refused directions,
and original expiry response consumption. Editor noise, a source-bound stale
observer, a real third-country FROM frame, and duplicate callbacks are separate
controls. Each case waits 68 native hours and requires at least 62 observed
hours before checking that the original AI result released both record slots.
At 900000 bn treasury, the sixth case accepts either an inert rejected quote
or a genuine queued settlement with equal positive measured debit and credit.
The native arithmetic representation is measured rather than presumed.
Scaled cash logs use **thousand USD**, so a small representable payment is
visible even when the normal bn display rounds to zero.

Record the fuel manifest hash as `fuel_fixture_manifest_sha256` in the parent's
process/export-bound launch receipt, then analyze recorded output:

```powershell
py -3.11 tools\validation\nuclear_fuel_trade\analyze_native_probe.py --manifest <fixture-manifest.json> --game-log <private-user-dir\logs\game.log> --launch-receipt <parent-launch-receipt.json> --out <new-result.json>
```

Strict acceptance requires all labels, original option selections within their
own native intervals, exact actor frames, source/fixture AST/hash identity and
the bound process/profile/launch receipt. `--diagnostic` never reports native
acceptance. `check_recorded_reader.py --manifest <embedded-fixture-manifest>`
uses synthetic diagnostic logs to verify six corrupted controls are rejected;
those synthetic logs are reader tests, never game evidence.

Add `--result-aware` to prepare an optional faster private fixture. It schedules
polls with a nominal two-hour delay, with a separate 68-hour deadline and a
persistent 72-attempt cap. Native one-hour queued callbacks have fired in the
current displayed hour; recurring one-hour polling can therefore starve the
clock and original AI replies. Two hours allow a later tick; the attempt cap
also stops a loop safely if the scheduler fails to advance. The source test
repeats the actual pending poll AST without clock progress and requires bounded
termination without asset changes. It does not emulate the native scheduler.
Readiness requires
both original partner/phase records cleared, both escrow balances zero and
each country's cash and fuel equal the frozen expected outcome. It then
queues the usual observer exactly once. The reader also requires the one
original production AI option before readiness and the observer, validates
the recorded outcome and re-resolves each private predicate/effect AST.
The original production callbacks and AI policy are unchanged. A short
callback delay does not substitute for either consent or accounting proof.
An optional-mode observer may appear within four native hours of readiness;
it still performs the original business assertions. Deadline termination
does not fabricate a reply, release a business record or transfer assets.
The reader's optional-mode self-check rejects 17 corrupted controls; the
default mode continues to reject its original six controls. Neither these
synthetic logs nor the AST queue adapter are native game acceptance.

This fixture does not prove rendered human controls, natural 30/31-day expiry,
save/load, multiplayer, annex-hook dispatch or full campaign balance.

Use --state-trace with --result-aware to record the exact native variables, flags
and frames before/after the original reply and result options, and at each
bounded poll/deadline. The declared islands only read state and write logs;
removing them restores the original event file bytes and executable AST. Five
focused controls reject mutating, undeclared, missing or duplicated islands.
Cash differences in trace receipts are calculated at the printed native log
precision; the existing exact business assertions and 68-hour deadline remain
unchanged. This optional instrumentation does not establish successful delivery.

The original common/on_actions/00_partisans.txt,
common/on_actions/99_EGY_on_actions.txt and common/on_actions/99_PER_on_actions.txt
files receive no private overlay and remain exact production bytes. This narrows the private
control environment compared with older fixtures such as native67; a later
traced run is therefore not a trace-only comparison with native67.

The fixture also guards the ordinary modify_treasury_effect API only for its
current recipient (THIS USA/HOL), while the private active flag is set. Other
recipients execute the exact original body; every other budget helper remains
unchanged. Each blocked change logs its actual recipient, ROOT, FROM and amount.
This isolates ordinary AI decision costs from the fuel accounting experiment;
the eight original fuel options and their reachable helpers do not call this
API. Fuel payments remain their original direct treasury arithmetic, and the
83 accepted-branch outcomes, exact expected balances and 68-hour deadline stay
unchanged. Native72 showed exact fuel settlement and acknowledgement followed
by unrelated HOL cash changes; its log does not identify the exact ordinary
caller. A matching unlogged military-order decision is a candidate, not proof.
This private isolation is a further environment change from native72 and does
not establish ordinary economy/campaign correctness.
