# Economic support checks

Run `python -B tools/validation/diplomacy_package_06/run_checks.py` from the checkout.

The runner includes all previous diplomacy scenarios, package06 economic support execution, exact source boundaries and whitespace checks. It reads actual helper, event, trigger, action, GUI and native hook source. Country variables and queued event identities are separate from one shared temporary execution frame. Temporary arithmetic, treasury helper clamps, frozen grant denomination, donor escrow, retained refunds and support asset inheritance are executed in source order.

The behavior checks reproduce four pinned pre-package cash defects before checking funded5/15/35 aid, consent, one political consequence, stale/wrong callbacks, withdrawal, treasury cap overflow, legacy recovery, native cleanup and independent debt relief. Actual aid/debt national policy helpers run with explicit GDP, debt, factories, leader, opinion, war and seven-slot influence inputs. AI tests evaluate sequential option modifiers and their fallback weights; they do not predict game frequency.

Aid cash ownership is treasury plus held donor escrow plus unreleased refund due. Native annex role fixtures check only these support assets; the game's ordinary treasury/debt inheritance is outside the model. A recovered legacy pair is quarantined because old queued modal counts are unknown. Disappearance cleanup retires only the affected callback pair; unrelated partners remain usable.

Pair retirement and legacy quarantine are permanent flags for affected country pairs in that save: they prevent an unconsumed old popup from authorizing a later agreement with a restored historical tag. Other partners remain usable. Tests cover restored donors as well as recipients and both native annex role conventions. The bounded model does not prove whether or when the engine restores a country or delivers its retained popup.

Influence, opinion and party helpers are witnessed at their actual callers, with expected parameters and call counts; their complete calculations are not simulated. Source execution does not prove native scheduling/scopes, GUI rendering, save/load or a playable campaign. Repeated old debits of the same denomination cannot be reconstructed from one surviving boolean flag and are explicitly outside the recovery proof.
