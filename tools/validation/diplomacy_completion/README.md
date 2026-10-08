# Current diplomacy completion checks

Run `python -B tools/validation/diplomacy_completion/run_checks.py` from the
repository root. Each current package runner must exist and succeed; a missing
runner is incomplete work, not a skipped success. The output preserves the
individual proof reports and their source hashes instead of adding old scenario
totals to a claim about the current implementation.

The checks cover investment execution (24), actual electricity delivery (25),
and relations/missions (26), plus the unchanged cheat hotkey and Git whitespace.
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
The historical package 06 runner also cannot execute
the new delivery reconciliation effect through its old package 01 interpreter;
it was not reported as a passing current regression suite.
