# Current diplomacy completion checks

Run `python -B tools/validation/diplomacy_completion/run_checks.py` from the
repository root. Each current package runner must exist and succeed; a missing
runner is incomplete work, not a skipped success. The output preserves the
individual proof reports and their source hashes instead of adding old scenario
totals to a claim about the current implementation.

The checks cover investment execution (24), actual electricity delivery (25),
relations/missions (26), metered energy invoices and payments (27), and trade
and investment framework negotiations (28), plus the unchanged cheat hotkey
and Git whitespace. Weekly cash checks separate the displayed energy forecast
from actual settlement, cap debt repayment at the remaining debt, and preserve
reinvested income which cannot fit in the existing portfolio cap. The retained
income claim has a real decision and a guarded weekly collection path.
They also reject syntax which failed the actual HOI4 1.19.3 startup, check
the narrow support compatibility changes against commit c1420b1, and execute
the ordinary alliance model with explicit global world tension. The grammar
guard is deliberately a source guard, not a replacement native compiler.
The original hotkey publication runner rejects any later game file outside its
own scope. It remains unchanged. The current regression runner checks that all
hotkey game files exactly match their published feature commit and executes the
original behavior functions. It does not claim that the old whole-worktree
inventory still passes or that historical cumulative suites were rerun.
They do not prove native compilation, campaign accounting, save/load, speed-5
performance, or multiplayer synchronization. Those require native acceptance.

The full objective and remaining requirements are recorded in
`docs/development/DIPLOMACY_COMPLETION_UK.md`.

Native probe 02 reached the frontend but failed diplomacy parsing (201 matched
error lines, including cascades). Probe 03 exposed 34 further lines in the
legacy aid events, missed by the old eon-only log filter. After their root
comparison was fixed, probe 04 loaded all 58 changed game paths plus explicit
legacy dependencies without diplomacy errors. Its process later ended with
no established exit cause; 26 inherited menu/assets/equipment log lines remain.
This is source loading evidence, not campaign acceptance.
Final probe 05 repeated current source loading and launched a new single-player
campaign with the USA start parameter, completing on_startup initialization
and remaining alive on pause. No contract cycles or native save/load/MP have
been accepted; its 33 inherited non-diplomacy log lines remain recorded.
Probe 06 repeated the f2832b6 source snapshot and new paused campaign startup.
Its requested auto-run marker was absent, so it does not prove console-command
execution or an hourly timer. These historical probes do not compile the later
package 27/28 sources. Every new native probe must record their current hashes
before launch and recheck them against its own logs.
Probe 07 loaded its 82-file source snapshot and started an unpaused campaign.
Probe 08 used the documented `-debug` flag and observed 350 timer callbacks
with an uninterrupted modulo-24 counter sequence. Its arithmetic samples kept
0.0005 and paid 0.001 with divisors of 1600 and 1e9; formatted decimals do not
establish storage precision. No contract invoice/payment cycle was accepted.
The longer run exposed one legacy annex embargo removal error, so its broad
native report is failed. A guarded removal repair now has eight actual-source
post-revoke cleanup cases and a byte comparison preserving every other legacy
statement; its native annex hook order and full revoke helper remain unproven.
The historical package 06 runner also cannot execute
the new delivery reconciliation effect through its old package 01 interpreter;
it was not reported as a passing current regression suite.
