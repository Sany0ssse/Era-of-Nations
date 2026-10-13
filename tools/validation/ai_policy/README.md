# Native AI policy regressions

Run `python -B tools/validation/ai_policy/run_checks.py` from the repository root.
The tests execute the actual strategy predicates, energy AI weights/draft
preparation, and ordinary-alliance initiative/lifecycle ASTs with explicit
country, geography, threat, rounding, and native-effect fixture inputs. Unknown
visited statements fail closed. The report binds results to current source hashes.

These tests cover directed threats in nested callbacks with a neutral bystander;
reachable industrial/SADC/scientist strategies; energy shortage and recovery;
bounded contract quantities, export revenue, and draft ownership; consensual AI
alliance proposals, national restrictions, mutual trust, hostile-partner veto,
180-day retry guard, and preservation of player control.

They do not implement the HOI4 engine or prove its autonomous selection, a long
campaign, save/load, multiplayer synchronization, or speed-5 performance. Private
native runs and preserved logs live under `.local/ai-audit-20261012/` and are
reported separately in `docs/development/AI_POLICY_UK.md`.
