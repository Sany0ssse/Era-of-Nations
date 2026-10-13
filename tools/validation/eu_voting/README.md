# EU Council vote regression suite

Run `python tools/validation/eu_voting/test_voting.py`.

The bounded interpreter executes actual production helpers and the shared legacy
result trigger. It separates country scope tokens from resident STATE population.
Unsupported primitives fail closed. Native selection is deterministic in this
model; engine float precision, GUI operation, campaign AI and synchronization
require separate native evidence.

The regressions cover inclusive double-majority boundaries, all eligible members
as the denominator, suspension and extinction, explicit abstention, treaty
unanimity, four-member blocking minorities, canonical duplicate cleanup, reentry,
and idempotent yes/no switching. Current Council voting is a declared temporal
abstraction for the whole campaign, including the start in 2000.

Run `python tools/validation/eu_voting/test_integration.py` for the cross-file
entry points: membership-gated GUI, candidate information screen, actual office
and Council callbacks, neutral AI response, world clock and legacy result hooks.
The current-byte check compares existing BOM and EOL styles to HEAD; new EN/RU
localisation uses UTF-8 BOM. These checks do not click the native interface.
