# Uranium native probe

These tools prepare and inspect a **controlled native resource/trade probe**.
They do not launch the game, embed files, change launcher settings or prove the
final nuclear economy. Keep recorded attempts immutable and use a fresh output
directory when source changes.

Preparation against a private exported source with its original receipt:

```powershell
python tools/validation/uranium_resources/build_native_probe.py --source-root "E:/Era of Nations/.local/uranium-resources/native-source/source" --export-receipt "E:/Era of Nations/.local/uranium-resources/native-source/export-receipt.json" --output "E:/Era of Nations/.local/uranium-resources/native-probe-01"
```

`--prototype-definition` adds a private seventh `uranium` definition when the
source still contains six resources. It does not change sprites or the actual
checkout. `--prepare-only` permits an unlaunched preparation against the checkout
but deliberately disqualifies that manifest from native acceptance.

The parent can embed the exact generated `mod/` files into its private export,
then launch a private user profile at `-start_tag=USA`. Record the launch receipt
with the same fields as the existing consultation native receipts: schema, PID,
executable and its SHA, process start time, start-receipt path, source root,
embedded root, manifest SHA, enabled mods, embedded source SHA map, private user
directory, game log and source export receipt SHA.

The fixture queues its own hidden events after `on_startup`; wait for its `END`
marker. It adds 800 raw units to Canadian Saskatchewan in the **private scenario**
and uses the production trade law `globalized_trade_economy` to make an export
source available. It performs a native 8-unit import, repeats 8, then requests16.
The latter two are observations, not guessed assertions about overwrite versus
add behavior. A later24-hour observation records retention without native
equipment demand. This does not establish native AI purchasing.

```powershell
python tools/validation/uranium_resources/analyze_native_probe.py --manifest ".../manifest.json" --launch-receipt ".../launch-receipt.json" --game-log ".../user-data/logs/game.log"
python tools/validation/uranium_resources/test_native_probe.py
```

Acceptance requires all15 unique assertions, all12 ordered country observations,
at least50 native hours, delivered first import and domestic balance increase,
matching source/fixture/documentation hashes and launcher/process/log receipts,
and no selected uranium/resource/import errors. The tool writes no acceptance
file by itself; the caller may preserve stdout in a fresh result path.

The negative controls use synthetic text to validate evidence rejection. They
are never evidence that the game itself passed the fixture.

## Actual source behaviour checks

```powershell
python tools/validation/uranium_resources/run_checks.py
```

`source_model.py` parses and executes the actual uranium effects/triggers, GUI
clicks and predicates, existing mission timeout/cancellation, state decision
callbacks and existing weekly material hook. Unknown visited statements fail
closed. `test_core_source.py` checks conservation, 9:1 feed conversion and tails,
capacity/damage, stock headroom, zero feed, last-deposit depletion, captured
deposits, duplicate settlement, project funds/refunds, GUI routes and AI import
request eligibility. It reports SHA-256 bindings and fails if those files change
during the check.

Country balances, delivered state shares, resource multipliers, ownership and
temporary flag expiry are explicit fixture inputs. The AI import effect is
recorded; native delivery is not simulated. Whole-GDP refresh and the finished
fuel trade daily cleanup are explicitly identified source boundaries. The new
country's first enrichment diplomatic reaction is outside these unit fixtures.
The GUI fixtures already register the representative country as an enricher.

## Source-bound native materials and project probe

```powershell
python tools/validation/uranium_resources/build_core_native_probe.py --source-root ".../private-source" --export-receipt ".../export-receipt.json" --output ".../new-core-fixture" --start-tag NEP
python tools/validation/uranium_resources/analyze_core_native_probe.py --manifest ".../manifest.json" --launch-receipt ".../core-launch-receipt.json" --game-log ".../user-data/logs/game.log"
python tools/validation/uranium_resources/test_core_native_probe.py
```

This builder prepares a separate Germany/Berlin scenario without launching or
embedding it. Six GUI/mission/decision callback bodies are copied from the
selected source AST with SHA bindings. The private targeted mining decision
keeps native `ROOT` and `FROM` scopes and production callbacks, accelerates its
clock to one day, and disables automatic AI selection. Callback tracing records
upfront payment, ordinary completion and a refund after state ownership changes.
The enrichment mission callbacks are invoked directly; their730/1095-day native
calendar and human clicks are outside this check.

The33 native assertions and9 independent observations cover stock conversion,
tails, repeated projection/settlement, zero feed, finite deposits, captured
deposits, actual GUI/mission accounting and an8-unit import into Germany. An
explicit0.1-unit state addition records the engine's fractional behavior. A zero
delta is reported as unsupported, never accepted as fractional proof. Acceptance
also validates material observations, at least72 native hours, exact source and
callback hashes, embedded fixture hashes and the private launch/process/log
receipts. More than one fixture may share a launch: the core receipt must bind
this manifest SHA, and its embedded SHA map may contain the other fixtures too.

The trade prototype now accepts `--start-tag NEP` for a combined launch and waits
an extra6 hours in its final queue. Earlier frozen attempt manifests and logs
remain unchanged. A useful resource observation does not override a failed
strict acceptance check, such as an insufficient recorded calendar interval.

The source suite also checks a native multiplier fixture, two-country final
reserve conservation, small geological output, geometric mine expansion,
variable AI import demand and annexed stocks/project escrows, including capped
refunds. Native multiplier/delivery values in those source checks remain
explicit oracles. The independently recorded native probe must establish their
actual engine behavior.

`test_core_mutations.py` changes only in-memory copies of the actual AST and
requires rejection of material/accounting/project regressions. It never edits
game files and is not native campaign proof.

## Native resource rights

```powershell
python tools/validation/uranium_resources/build_rights_native_probe.py --source-root ".../private-source" --export-receipt ".../export-receipt.json" --output ".../new-rights-fixture" --start-tag NEP --after-core
python tools/validation/uranium_resources/analyze_rights_native_probe.py --manifest ".../manifest.json" --launch-receipt ".../rights-launch-receipt.json" --game-log ".../user-data/logs/game.log"
```

This family records uranium-only `give_resource_rights` and `remove_resource_rights`
for Berlin, classified through Germany/Nepal native resource counters. The
recipient's actual weekly material effect runs in a separate NEP-root native
event. Its13 assertions and8 observations distinguish native rights registration
from source material credit; both must pass acceptance. `--after-core` starts this
family after the core END flag and keeps the two scenarios sequential.

The source suite checks both controller-first and beneficiary-first settlement,
one shared physical depletion, a saved rights recipient for the last shipment,
duplicate calls, and no claim without uranium rights. Its rights oracle explicitly
returns false when state output is zero, matching the installed native trigger
documentation. Those source cases are not a native simultaneous final-deposit
cache proof.

Current units are100kg natural uranium/week per native unit; geological capacity
is measured in tonnes/week and material stocks in kg uranium. Private resource
updates use integer amounts because the recorded native fractional addition
produced zero delta. This avoids an output ledger recording fractional material
that the native state never received or removed.

The native export counter records trade-law market allocation, as observed when
an8-unit request became16 without changing the supplier counter. These tools do
not claim complete global conservation of unsold market allocation, actual
scripted AI import delivery, full mine/enrichment calendars, save/load or
multiplayer acceptance. Do not substitute synthetic evidence for those checks.

The runner includes twelve groups: source execution and mutation checks, meta
bindings, the original/final rights, staged enrichment, resource/core evidence
validators, and the paired capability, AI dispatch and mission-calendar validators. Counts are
reported by the current run receipt rather than treated as fixed acceptance.

The staged enrichment fixture records the paid flag and native active-mission
predicate separately. Costs75/25 and refund25 are measured within the same native
event; ordinary treasury changes between events are retained as observations.
Its two private mission clones compare `allowed=no` and `allowed=yes` with
automatic activation and AI selection disabled in both. This is an explicit
load-time registration control; neither clone replaces the production mission.

The original state activation control observes whether
`activate_targeted_decision` invokes a non-mission's callbacks. Version5 of
`build_state_activation_native_probe.py` instead exposes an armed private copy
to actual native AI selection, with a critical private AI score1000 and a
one-day `days_remove`. Production AI weight and callback bodies stay unchanged.
Each native callback measures its own0.25 start charge or zero completion charge.
The32-hour completion observation is queued by the actual AI start callback,
so delayed AI selection cannot make the observation premature. A96-hour deadline
rejects missing AI selection. A separate one-day target mission invokes the exact
source mine callbacks in a native `FROM` state44 frame. Begin and completion are
contiguous in that control, so it establishes native scope/accounting only.
`--after-enrichment` prevents its GER treasury fixture from overlapping enrichment.
The new analyzer rejects callbacks before initialization and before the correct
country/state stage arm; previously frozen evidence uses its frozen analyzer.
Version4 keeps the ordinary callback-relative32-hour wait and observes the
separate one-day target mission after64 queued hours, requiring at least60
actual native hours. Version3 keeps its original32-hour target-mission contract.
Version5 additionally binds the production `state_target = any_owned_state`
enumeration to both private decisions and checks their exact declared metadata.
The14 assertions and Version4 callback/calendar criteria stay unchanged.

`build_mission_calendar_native_probe.py` explicitly compares allowed yes/no
against literal730 and dynamic `ROOT.private_timer` country missions, setting
the timer before activation. It independently observes the production mission's
remaining days, triple365-day extension and actual accelerated native timeout
callbacks for triple and single construction. Cancellation uses the exact source
callback body and explicit native mission removal; this does not claim a human
selected the mission. Its strict analyzer validates the matrix, event waits,
callback-local costs and completed project counts. Version3 accepts a running
mission only from its positive native remaining-days counter and observes
`has_active_mission` diagnostically: that predicate can be false while the timer
runs. Cancellation must clear the actual counter before a fresh730-day start.
Preparing the fixture or passing its synthetic negative controls is not native
game proof. Earlier frozen manifests retain their original strict criteria.
Version3 observes the restarted single mission after64 queued hours, requiring
at least60 native hours after the accelerated timer is set to one day. This
allows the timer to reach zero and its actual native completion callback to run.
Version2 retains its original32-hour wait and30-hour minimum.
Version4 retains all26 earlier assertions and adds direct cancellation through
the exact executable `energy.5.a` option, in a native foreign CAN `FROM` frame.
It checks cleared legacy time and single/triple flags, the native timer and the
source-bound production visibility predicate. The replacement project starts
before the actual queued three-day `energy.6` acknowledgement. A later checkpoint
requires that acknowledgement to clear the pending partner while the new project
remains paid and running. `effect_tooltip` displays text and never executes its
listed effects. Only after this checkpoint does the fixture accelerate the
recorded integer remaining days to one day, then wait64 queued hours/minimum60
actual hours for the native callback. The total minimum remains152 native hours;
the additive ACK wait makes the new scenario longer. No human event-option or
GUI selection is claimed, and older evidence contracts stay unchanged.

`build_rights_connectivity_native_probe.py` pairs oil and uranium rights to a
coastal ENG/CAN beneficiary, adds convoys and records native counters before and
after the cache wait. Recorded zero delivery is a diagnostic result; legal
rights alone never establish delivery. `analyze_ai_import_native_trace.py`
verifies bound literal exporter commands and return traces against the production
daily AST after removing only declared logs/debug. That proves dispatch, while
native delivery and retention require their own observations. In recorded55,
an8-unit `create_import` parameter produced native imported80 with uranium
`cic=.0125`; requested amounts must not be assumed to equal delivered counters.
The current source binds `factories`, as shown by installed native Germany
history. Its quoted capacity is80 native uranium units per civilian factory;
the source suite bounds importer factories and exporter allocation and subtracts
existing domestic flow from the requested shortfall. Generated requests do not
credit stocks in the source interpreter. Native retention must be observed
independently, even when the generated command returns successfully.
