# Institutional appointment lifecycle validation

Run `python tools/validation/eu_institutions/test_lifecycle.py` from the checkout.

The suite parses and executes the current `eon_eu_institutions_effects.txt` and
`eon_eu_institutions_triggers.txt` AST. Unknown script operations fail closed.
It covers the separate appointment ballot, deadline gates, two-stage Commission
proposal/Parliament confirmation, weighted Parliament votes, reinforced Council
majority, euro-area ECB electorate, exact Frontex two-thirds majority, nominee
generation limits, refusal/retry, live membership changes, vacancies, Council
rotation, AI participation without scripted GUI and exact country token identity.
It also verifies office idea IDs against the actual upstream catalog and verifies
that delayed event popups have no voting effects.

Reinforced institutional QMV requires both 72% of eligible governments and 65%
of their population. The ordinary-QMV blocking-minority exception is not applied.
The single-candidate Parliament presidency round requires a majority of valid
votes cast (weighted yes seats exceed weighted no seats, with at least one yes).
Commission confirmation instead requires a majority of all component seats.
Abstaining or unanswered delegations therefore have different effects in those
two ballots. Stage changes and closed ballots clear prior displayed choices.

Native grammar regressions reject inclusive shorthand and unsupported dynamic
`has_opinion` targets. The model executes documented `var`/`value`/`compare`
comparisons and checks voter-to-nominee opinion through resolved country scopes.
Every timed institutional flag write explicitly declares `value = 1`; an AST
guard rejects an omitted value in effects, decisions or events.
Those guards cover known parser failures; they are not a native compiler.

The model has explicit external boundaries:

- `eon_eu_is_active_member` is a fixture predicate, not execution of the membership
  lifecycle. Membership tests and the integrated native probe validate that chain.
- `eon_eu_recount_council_vote` supplies fixture resident population. It does not
  execute the legislative recount or state population loop; those have their own
  voting suite and must be included in the integrated native probe.
- Timed flags and ideas do not advance an actual clock. Fixtures clear the relevant
  deadline/term flags or remove an expired idea deliberately, then execute real
  source callbacks. This does not establish scheduler or save/load correctness.
- Upstream idea `on_add`/`on_remove`, localization rendering, event delivery,
  political-power charging, GUI clicks and human choices are outside this model.
  The explicit holder writes in the tested source are executed; engine callbacks
  require the integrated native run.
- Country-delegation votes in the Parliament and Frontex Board are stated game
  abstractions. They are not claims about individual MEP or Board member behavior.

These checks are bounded source evidence, not a playable campaign, multiplayer,
historical-officeholder chronology, long-run AI balance or performance acceptance.
Native results belong in `docs/development/STATUS.md` and must name their scope.

`python tools/validation/eu_institutions/test_finance.py` separately executes the
actual two money eligibility limits, actual budget ratio/net bookkeeping, and
actual role-cache clearing and administrative allocation. Zero/nonpositive
expenditure cannot divide or retain a stale ratio. Current holders replace
former role allocations; two administrative offices preserve their combined
shares even when both candidates originate from the same country. The actual
legacy foreign-policy fallback trigger is included. Four relevant office
callbacks must mark the budget dirty.

Economic and agricultural allocation are explicit external boundaries in these
role-cache fixtures. Treasury, weekly cash settlement, native idea callbacks and
the world scheduler are not simulated by this finance suite.
