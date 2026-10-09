# Labour recruitment treaty validation

Run from the repository root:

```powershell
python tools/validation/migration_treaty/test_lifecycle.py
```

The fail-closed interpreter executes the changed diplomatic action, triggers,
and helpers from source. It covers pair reservation, changed conditions at
acceptance, wrong-pair and duplicate callbacks, legacy pending offers, both
cancellation directions, third-country isolation, reciprocal role accounting,
annex/subject-annex callback scopes, dormant and revived tags, old dead-partner
records, cooldown expiry without an answer, and source encoding. It never
changes game files or saves.

The country-scoped `eon_migration_treaty_reconcile_country` also removes legacy
recorded pairs with dead partners. Native annex hooks clean every possible tag,
including dormant countries, before clearing the disappearing owner's scalars
and modifiers. Population and refugee residence never change in these helpers.

These checks do not prove HOI4 native callback behavior, physical population
movement, economic balance, multiplayer synchronization, or playable campaigns.
Native replies do not expose a request nonce; an old duplicate callback cannot
be distinguished from a later proposal to the same partner. Reservations remain
until native responses drain, and pair cooldowns prevent immediate reoffers.
