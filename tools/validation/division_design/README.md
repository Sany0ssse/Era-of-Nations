# Division design checks

Run from the checkout with Python 3.11 or later:

```powershell
python tools/validation/division_design/run_checks.py
```

Or run the individual checks:

```powershell
python tools/validation/division_design/test_ai_templates.py
python tools/validation/division_design/test_ai_boundaries.py
python tools/validation/division_design/test_technology_refs.py
python tools/validation/division_design/test_regimental_support.py
python tools/validation/division_design/test_tutorial.py
python tools/validation/division_design/test_native_fixture.py
```

These read the actual unit definitions, AI targets, seeded templates,
technology upgrades and tutorial source. They check declared IDs, line versus
support placement, native group compatibility, existing HQ exceptions,
equipment costs, upgrade completeness, factory thresholds and human-only
one-time help delivery. Broken source variants must fail the checks.

The unit-category registry is checked explicitly. The first native attempt
found that the inherited category file overrides the base game's new
regimental category; the missing category was appended without moving old
IDs. Infantry unlocks are checked against the actual standalone database;
the obsolete vanilla `infantry` reference was removed while keeping the
existing `Special_Forces` ID active and unlockable.

The country tutorial flag persists in the save. It is a country flag, not a
Steam-account flag: a replacement player can use the free help decision.

`build_native_probe.py` prepares an isolated fixture without starting HOI4.
It requires an explicit frozen source tree, a new output directory and the
two support IDs. `analyze_native_probe.py` requires a completed native trace
with every unique assertion, no failures, matching source/fixture hashes and
no script errors referring to this packet. These tools never change a user
save, Workshop file or launcher playset.
The analyzer rejects a missing error log; an incorrect path must not turn
missing diagnostic evidence into a clean run.

The fixture creates matching three-battalion templates for NEP, GER, FRA and
RAJ and deploys their attached companies through engine scripting. It also
checks human tutorial registration and excludes AI countries.
Its probe-only dynamic getters use private synchronized tokens. Native
unit creation runs in the capital state scope; no test fixtures enter the
published mod.

Native status for the current packet is recorded in
[the development status](../../../docs/development/STATUS.md).

Final private probe91 on HOI4 1.19.3 passed all 28 unique assertions for
NEP/GER/FRA/RAJ. Both paid support types were counted in deployed units.
Eight legacy `has_template_containing_unit` observations were negative
despite those positive deployed counters; they are diagnostic observations,
not passed assertions. The production mechanic does not use that getter.
Failed attempts89/90 remain preserved; correcting fixture scope and replacing
invalid assertions did not turn their results into accepted runs.

All six source-check groups passed. The analyzer binds the final trace to
the exact fixture and source hashes. Private receipts are under
`.local/division-design/` and must stay outside Git. The owned test process
was stopped and the original launcher configuration restored.

Scope: source checks and scripted template registration/deployment do not
prove interactive designer restrictions, tooltip rendering, battle outcomes,
full campaign/save reload behavior or multiplayer synchronization. Scripted
OOB/template creation can bypass designer restrictions. Those limits must
remain visible in any results derived from this fixture.

## Interactive acceptance still required

1. Start a Russian-language campaign. Check that the first guide is readable,
   its close/back/page buttons work, and the free help decision reopens it.
2. In the designer, compare a column of two compatible battalions with three.
   Verify the native minimum and that incompatible support is unavailable.
3. Add the light battery: check 3 artillery, 1 command/control equipment,
   40 personnel and zero additional combat width. Check the motorized battery's
   extra 5 vehicles and fuel requirement. Inspect the artillery upgrade bonus.
4. Inspect the three new header tooltips and the guide illustration at the
   actual window size. Repeat for a different country and a loaded campaign.
5. For multiplayer, use identical mod revisions/checksums on both computers;
   verify help delivery to both humans and synchronization after template edits.

These are pending manual checks, not instructions that have already passed.
