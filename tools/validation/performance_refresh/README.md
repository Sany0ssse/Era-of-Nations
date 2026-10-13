# Economic refresh and monthly migration regressions

Run from the repository root:

    python -B tools/validation/performance_refresh/run_checks.py

The economic model executes the current combined damage/state helper and compares
it with immutable original helper islands in 300 differential worlds. It checks
fresh state/control/population/damage inputs, preserved fuel recovery and daily
cadence, and the reduction from two state walks to one. GDP and deep finance are
explicit native boundaries in these models, not simulated economic outcomes.

The migration model executes the current monthly pipeline in 64 worlds and
compares it with the original two helper islands. It checks dead-partner queues,
live agreements, scratch cleanup, population/return/labour settlement and order.
The temporary dead-country list is created and cleared within one monthly pulse;
no persistent cache or delayed country-existence refresh is introduced.

Compatibility tests certify the entire current combined helper and dependency
closure before reversing only its exact two call sites for older whole-file
guards. Historical financial and delivery hashes remain unchanged. Unknown
commands, scope substitutions, extra references and unrelated bytes remain
visible and fail closed. Actual-source tests never regenerate the candidate.

These checks prove bounded source/model properties. They do not prove native
campaign behavior, full financial settlement, CPU-time gain or FPS improvement.
Native tests, raw logs, backups and timing receipts remain private under .local/.

The runner also executes all 22 migration treaty lifecycle regressions. Fourteen
existing tests retain their original bodies; eight additional controls exercise
ready, empty and fallback scope lists, exact queues and foreign temporary state,
actual snapshot prefix/suffix, country order and unknown primitive rejection.
