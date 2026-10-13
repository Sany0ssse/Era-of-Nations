# Peace settlement verification

Run `python tools/validation/peace_settlement/run_checks.py` from the mod root.

The ordered actual-source transport interpreter verifies contact, fixed terms,
pending consent, terminal cleanup, AI reachability and stale-response guards.
The execution adapter verifies escrow, refund, exact transfer and consumption
ordering with explicitly supplied native-success/failure and guard facts.
The legacy AST checks cover finite arithmetic, subject preservation, explicit
conference scopes and reciprocal consent at downstream annex callbacks.
The compatibility guard permits only two pinned additions to the old annex
callbacks while keeping the other package-25 byte assertions intact.

These tests are not the game engine or its diplomatic UI. Current native fixture
receipts remain under `.local/peace-validation-20261012/`; they distinguish
source-extracted native callbacks from human choices and actual AI selection.
See `docs/development/PEACE_SETTLEMENT_UK.md` and `docs/development/STATUS.md` for the accepted
runtime evidence and remaining limitations. No saves, launcher playsets or
Workshop content are part of this test suite.

The current runner has 62 tests. The pair-pressure and subject suites read
CURRENT game scripts against pinned pre-change bytes. They cover swapped ROOTs,
third-party occupation, non-core states, recovery, unrelated subject wars,
selected-war subject exclusion and stale response validity. Whole-source inverse
guards reject missing, duplicated, wrong-scope and unrelated byte mutations.
The generic transport state adapter has no implicit occupation facts; fixtures
must supply ownership, controller and core explicitly. These are model tests.
Native R4 separately validated the helper queries and preservation of two
unrelated subject fronts on actual January3; it did not choose or accept a peace
offer for AI or a player. The source catalog contains no approval or runtime
completion assertion.
