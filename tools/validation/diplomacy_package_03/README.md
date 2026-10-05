# Ordinary defensive alliance source checks

```powershell
python tools/validation/diplomacy_package_03/run_checks.py
```

Python 3.10+ and Git are required, with the three packages' baseline commits
available locally. No third-party Python libraries or HOI4 process are needed.
The runner repeats packages 01/02, executes current package 03 source branches,
checks preserved source boundaries, localisation, IDs, and staged/unstaged
whitespace. It does not alter game files or saves.

Package 03 uses baseline `5fa82c4bd9df099fc92c110983191fe8d4fdc47e`. The
interpreter reads ordered current AST and fails on unknown visited statements.
Country rights, effective modifiers, tension, DLC, native creation/admission
outcomes and callback delivery are explicit inputs, not independently proven
engine behaviour. AI arithmetic checks do not establish actual AI consent.

See [the package documentation](../../../docs/development/DIPLOMACY_PACKAGE_03_UK.md)
for implementation scope, known legacy/native limits and campaign acceptance.
