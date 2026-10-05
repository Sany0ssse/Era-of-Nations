# Energy counteroffers and withdrawal source checks

```powershell
python -B tools/validation/diplomacy_package_05/run_checks.py
```

Python 3.10+ and Git with packages 01-04 baseline commits are required. The
runner repeats the previous packages, then executes current negotiation event
options, their trigger guards, the counteroffer editor/dispatch, withdrawal,
native-source AI evaluation and actual weekly energy payment loops. Unknown
visited statements fail. Tests do not edit gameplay files, saves or receipts.

The package adds 110 bounded behavioral scenarios (4620 cumulative) and 86
source preservation/reference/API checks. Both proposal directions,
three human rounds, a single automatic AI counter, discarded editors, pending
withdrawal, changed production/framework/records, stale temporary capacity
inputs, invalidation after AI preview, consumed stale-rendered human options
and effect-free notices are covered. Literal payment expectations use
the old eight-GW pair at 0.04 (`0.32` weekly) and accepted twelve-GW counter at
0.05 (`0.60` weekly), with a third country's delivery/payment preserved.

Country production, money, ideas and event delivery order are supplied fixture
inputs. Source tests prove bounded bookkeeping and effect guards, not native
event consumption, fixed-point precision, GUI presentation or save/load. The
cancelled original proposal keeps its reservation until its pending response
is consumed; source tests must not infer immutable callback payloads from a
mutable country variable. Synthetic replays of a consumed event across future
same-pair negotiations are outside the modeled native lifecycle.

Old active delivery and payment remain authoritative until final agreement.
The source checks separately protect exact byte boundaries, unrelated gameplay,
identifiers, localisation keys, UTF-8 BOMs and existing line endings.
