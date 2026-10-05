# Energy negotiation source checks

```powershell
python -B tools/validation/diplomacy_package_04/run_checks.py
```

Python 3.10+ and Git with the existing packages' baseline commits are required.
The runner repeats packages 01–03, executes the current energy events' immediate
AI calculations and both option weights, checks GUI quantity limits and direct
dispatch/acceptance capacity, and executes the current bilateral bookkeeping and
weekly payment calculation. It does not edit gameplay files, receipts or saves.
Package 04 also checks the byte boundaries of the existing game files, native
trigger API spellings, bilingual localisation keys and the unchanged nuclear
fuel paths. Current behavior checks contain 87 scenarios and the scoped source
checks contain 27 assertions, in addition to the
unchanged lifecycle scenarios run by packages 01–03.

The package 01 reusable state fixture supplies a generous cached energy balance
of 1000 for pre-existing tests whose subject is bookkeeping rather than energy
capacity. Package 04 always supplies explicit economic inputs for each boundary.
Those numbers, policy ideas, framework and callback timing are test inputs;
they are not values observed in a campaign.

The interpreter reads ordered actual source. Unknown visited statements fail.
Native trigger temporary math, conditional triggers and `all_of` array traversal
are interpreted according to the installed primary trigger documentation.
Country capacity uses the latest supplied cached `energy_balance`; cache refresh
timing and actual production remain engine concerns. AI weights do not prove
which response a running engine delivers. Save/load, fixed-point precision, GUI
presentation and physical interconnector routes are not proven by these checks.
