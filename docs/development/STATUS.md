# Era of Nations 0.1.0 — initial development baseline

Verified on 2026-10-05.

The graphite/navy UI update is now installed. Its 109 sprite opt-ins and final
DirectX 11 startup passed mapping and compilation checks; visual acceptance of
the unobstructed menu and campaign controls remains pending. See
[UI_THEME.md](UI_THEME.md) for scope, receipts and exact limitations.
The existing diplomacy audit is complete. Two narrow organization-membership
fixes have been applied: SCO rejection now blocks the entire admission result
and resets on a new application; Arctic observer expulsion removes the observer
idea. Source checks and independent review passed. New-campaign acceptance is
pending; broader diplomacy changes remain proposals. See
[DIPLOMACY_AUDIT_UK.md](DIPLOMACY_AUDIT_UK.md) for findings, priorities and limits.

## Completed setup

- Imported all 74,465 source files directly into `E:\Era of Nations`; the archive
  wrapper directory was removed and ZIP CRC checks passed during extraction.
- Renamed both mod descriptors, removed the inherited Workshop ID, and retained
  all source `replace_path` directives and HOI4 `1.19.*` compatibility metadata.
- Registered a private local **Era of Nations** playset and enabled only this
  mod. Existing playset memberships and all 10 DLC selections were preserved.
- Updated 104 visible localisation values across 36 files. Keys, UTF-8 BOMs and
  line counts match the imported source. No full upstream brand remains in
  quoted localisation values.
- Installed the new logo, cover, music/radio sheets and icons. Native image
  sizes, alpha and file formats passed validation; see [BRANDING.md](BRANDING.md).
- Retained original authors and all four music credit files byte-for-byte;
  moved visible upstream notices into the attributed source archive documents.
- Connected `origin` to `Sany0ssse/Era-of-Nations`, branch `main`. Initial GitHub
  publication uses five successive asset batches without Git LFS. The final
  publication receipt is local in `.local/publication-result.json`.

## Actual game startup

HOI4 **1.19.3.0.c01a** was launched with the local descriptor. Its fresh
`system.log` reports **Active Mod Count: 1** and **Active Mod: Era of Nations**.
`setup.log` records a completed frontend startup at game date 2000.01.01.
The game process remained responsive after startup.

This confirms startup and mod selection. An unobstructed screenshot of the game
menu, starting a country, and campaign simulation have not been accepted yet.
Existing saves were not opened or changed. Local log receipts are in
`.local/runtime-check/` and launcher backups are in `.local/launcher-backups/`.

## Inherited issues to investigate next

The startup log contains inherited errors. Targeted checks confirmed that the
affected gameplay files match the supplied ZIP; the frontend differs only in
project promotional controls and links.

- The inherited frontend omits the `change_background` GUI type and background
  selection controls expected by the current game. The engine explicitly warns
  that opening that feature may crash. Do not use the background selection
  feature until its compatibility is repaired.
- `common/doctrines/subdoctrines/land/land_equipment.txt` contains a rejected
  `sub_unit_bonus` token; unit/Special_Forces references also report errors.
- Some mesh/entity, landmark, radio-song and particle references are missing or
  duplicated in the source.
- The earlier generated `gfx/main_menu/main_menu.dds` fallback has been removed;
  the static sprite directly references existing `gfx/loadingscreens/load_1.dds`.
  The final restart has no former missing-path message, but still reports two
  binary-token parse errors for that DDS. The inherited frontend lacks the
  current game's root background and selector types; the exact internal parser
  call is unverified. This compatibility issue remains unresolved.

No observed startup error names the replaced Era of Nations textures or changed
localisation syntax. This is a development baseline for further work; campaign
stability and Steam Workshop readiness remain unverified. Workshop publication
is deferred by the user.
