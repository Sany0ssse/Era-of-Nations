# EU weekly cash source checks

Run `python -B -m unittest discover -s tools/validation/eu_weekly_cash -v`.

The suite executes the actual four annual grant calculation, participant and
suspension gates, annual contribution conversion, selected intact display/cash
statements and weekly treasury/debt settlement. Declared rates isolate the EU
component from unrelated national economic calculations. Fifty-two repeated
settlements check nominal annual consistency; the inherited 0.019 mutation
demonstrates the original 1.2% shortfall. Refresh does not transfer cash.

Tests cover current members, Council voting suspension, subsidy suspension,
stale former-member/subject/dormant records, access cleanup, other income,
separately settled energy forecasts, bounded debt repayment and replay.

`byte_compat.py` projects exactly one reviewed calculation back to historical
bytes solely for older source guards. Its tests reject missing/duplicate/changed
calculation bytes, preserve adjacent foreign mutations, and retain all seven
explicit migration money islands and their fourteen negative controls. It does
not alter behavior fixtures or normalize unrelated source.

This is bounded source/AST evidence. It does not prove native weekly scheduling,
fixed-point rounding, budget adoption, GUI behavior, a playable campaign,
save/load or multiplayer. Native cash acceptance requires a separate real run.
