# Raid planning key

Run `python -B tools/validation/ai_raid_planning/run_checks.py -v`.

The fork intended `RAIDS_CREATE_FREQUENCY_DAYS = 30` but assigned the
misspelled `RAIDS_CREATE_FREQUENCEY_DAYS`. The installed HOI4 1.19 source
defines the correctly spelled key with a default of 7 days. This correction
applies the existing monthly creation policy. Raid scoring, launch requirements,
cancellation, target avoidance, and scripted nuclear raid actions are preserved.

The tests verify a whole-file inverse and a unique 30-day override, and do not
require the game or private `.local` files. They do not prove the engine's
actual scheduling, a campaign speed increase, or FPS.
