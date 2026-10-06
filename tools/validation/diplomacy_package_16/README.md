# Fixed ammunition transfer validation

Package16 starts from `0e70f281145041d9e707089623ef5ecb610b744f`. It executes current native `Send_ammo` callbacks and current lifecycle helpers through the existing ordered NOR interpreter definitions. Previous scenario loops are not loaded or recounted: the runner executes package15's 6,148 scenarios separately against current game files. Unknown effects and triggers fail closed.

```powershell
python -B tools/validation/diplomacy_package_16/run_checks.py
```

The package has **92 actual-source scenarios in 32 groups**, plus **one separate adapter check** for documented trigger-context rounding with explicit non-tie inputs. Cumulative actual-source scenarios: **6,240**. Source validation adds **125 source/API checks and 17 separate memory-only boundary checks**. Source and behavior receipts bind the same ten gameplay hashes.

Initial PUBLIC REDs, directly observed before gameplay changes:

```powershell
python -B tools/validation/diplomacy_package_16/test_ammo.py --focus send
python -B tools/validation/diplomacy_package_16/test_ammo.py --focus accept
python -B tools/validation/diplomacy_package_16/test_ammo.py --focus reject
```

Original native callbacks debited twice, delivered twice and refunded twice when repeated. Later focused REDs exposed positive noncountry pointers, the unowned legacy AI debounce channel and orphan held escrow; all are retained as current-source regressions. Fixed quantity remains 100,000 ammunition. Original ally/world-tension policy, acceptance AI and every original desire modifier remain unchanged. One additional technical desire modifier subtracts 20,000 when a new send is unsafe; the original legacy debounce modifier still applies independently.

Coverage includes exact donor-stock and fresh supply-node storage boundaries, fresh response policy, replay without a new current reservation, wrong partners, independent donors and recipient outgoing offers, sender-only withdrawal, consumed expired/invalid responses, forced cleanup, partial or full refund claims, dead-country recovery and both native annex hooks. Annex fixtures run the unchanged ordinary subject-inheritance effect exactly once, before or after the new cleanup, and verify queue-only held claims, storage priority and repeated new-hook safety. This is a bounded ordering experiment, not proof of native callback scheduling.

A donor reserves one outgoing shipment; recipients have no shared reservation. Withdrawal returns held ownership while retaining the original response identity until it is consumed. Forced expiry or a known missing recipient permanently retires only that donor-to-recipient pair. An unidentified or partial record preserves positive held assets, quarantines that donor's ammunition channel and does not infer an unknown partner. A full or reduced warehouse keeps uncredited refund claims; ordinary overcapacity stock is not trimmed. Annexed-donor claims transfer to the successor's claim ledger and are physically credited only by later daily cleanup, after ordinary native inheritance.

Only the source-preservation validators use exact prior-byte views for the declared native action range and six existing locale rows. Fourteen frozen literal journals prove the complete old-validator edits and unchanged counter lines. All 41 previous public behavior/executor/runner Python files remain byte-exact; they execute current gameplay. Source01 remains byte-exact. Source02 adds only the exact new withdrawal ID to its existing count; source14/15 compare its original bytes through that narrow journal, with all other checks retained. The package owns three existing gameplay files and seven new files, one new native action and 14 bilingual locale keys. It preserves BOMs, line endings, native IDs and unrelated game trees.

War membership, world tension, supply-node counts, country IDs, flag values, scope frames and timer presence are explicit native fixtures. Timed flags check declarations and supplied expiry facts rather than elapsed native time. Native documentation says variable scopes are always syntactically valid: that fact does not identify a country. The actual helper therefore uses country-only existence tests, distinct identity and exact country ID; the fixture supplies a finite typed country inventory.

Unidentified pre-upgrade callbacks remain inert and receive no inferred migration or refund. A legacy AI debounce flag keeps that donor channel blocked. Human pre-upgrade outstanding responses cannot be reconstructed reliably: finish them before upgrading or use a new campaign. The engine exposes no generation token for these callbacks; the suite does not claim safety for arbitrary replay of an already consumed popup across a later identical offer. Forced unresolved replies are covered through directed pair retirement.

This does not launch HOI4 or prove native scheduling, save/load behavior, AI decisions, delivery logistics or a playable campaign. Saves, Workshop subscriptions and launcher playsets are untouched. Private RED traces, journals and receipts remain in `.local/diplomacy-package-20261006-16/`, outside Git.
