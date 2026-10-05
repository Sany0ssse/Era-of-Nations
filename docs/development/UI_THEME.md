# Era of Nations UI theme

Updated on 2026-10-05 against Hearts of Iron IV 1.19.3.0.c01a.

## Appearance and scope

The interface now uses graphite/navy surfaces and muted steel-blue borders in
place of the inherited saturated purple and pale lavender skin. White lettering,
neutral pixels, red warnings, green status and gold accents are protected by
the palette. Source texture geometry and alpha are retained.

109 reviewed sprite declarations, using 94 declared texture paths, opt into
the theme across 34 `.gfx` files. This includes the main menu and pause-menu
button, generic buttons, faction buttons, topbar and toolbar, political/state
panels, equipment statistics, research, generic decision rows, missile controls,
energy controls and selected lobby panels. Eleven previously inherited `.gfx`
files are shadowed with their installed 1.19.3 declarations; unrelated entries
remain byte-identical. Existing sprite/localisation/gameplay IDs are preserved.

Texture declarations ending in `.tga` may resolve to an existing `.dds` through
the engine. The active `button_123x34.tga` and `country_selection_bg.tga` aliases
are included. Superseded/unused textures are not substituted for active assets.
The newer division-designer background is already neutral and is preserved.

Photos, portraits, flags, national-focus and idea art, terrain/map fields,
organization emblems, resource/ideology icons and color-coded doctrine mastery
tiers do not opt in. Blue/purple content inside a selected composite skin can
still change; the selection was reviewed visually, rather than made from a
global color threshold. This is a UI theme, not a screen-wide color filter.

## Implementation

`gfx/FX/eon_ui_palette.fxh` changes only source RGB. Deep purple button bodies
such as `(4,0,51)` become about `(18,24,33)`; a bright indigo border `(0,8,152)`
becomes `(53,71,97)`. Pale lavender `(159,160,200)` becomes `(70,94,128)`.
Near-white protection preserves lettering. Sampling, UVs, texture masks,
animations, alpha blending and explicit native button-state operations remain
in their original variants.

The active opt-in effects are `eon_ui_buttonstate`,
`eon_ui_buttonstate_nodowneffect`, `eon_ui_buttonstate_onlydisable`, and
`eon_ui_passthrough`. The other native variants are supplied for compatible
future opt-ins but have no current sprite mappings. Native `.lua` effect
references resolve to the correspondingly named `.shader` in the running game.
No global `buttonstate` shader is overridden.

For previously implicit panel effects, passthrough preserves baked frame
selection without adding new hover/down/disabled operations. A single-frame
generic button can use the native restrained hover/down effect. The engine's
undocumented implicit default is not claimed to be reproduced exactly.

## Verification

- Reversing only the effect substitutions/added lines reconstructs all 34
  source `.gfx` files exactly, including BOMs, line endings, IDs and original
  whitespace. 109 mappings resolve to an existing shader and texture or DDS
  alias. No gameplay/localisation source changed.
- Removing the helper include and RGB calls reconstructs all nine corresponding
  installed native shader templates exactly. Numeric checks covered 23 actual
  purple/lavender samples and 15 protected color samples. These are scoped
  checks, not exhaustive GPU rendering evidence.
- Staged whitespace checking accounts for preserved CRLF (`cr-at-eol`). Its
  remaining warnings in copied native GFX/shaders match the installed templates,
  including original trailing tabs and blank EOFs; opt-in insertions add none.
- First runtime attempt exposed invalid outer `//` comments in the shared
  `.fxh`; they were corrected to Paradox `#` comments. HLSL comments inside
  `Code [[...]]` retain their ordinary syntax.
- The final DirectX 11 startup at 21:35:37 local time completed in **38,398 ms**.
  Fresh logs report one active mod, **Era of Nations**, and the same 10 DLC.
  No fresh palette or shader compilation error appears. The process remained
  responsive. This verifies startup with the active effect mappings.
- The previous generated `gfx/main_menu/main_menu.dds` fallback is removed;
  `frontendmainviewbg.gfx` directly references existing `load_1.dds`. The former
  missing-path message is absent, but startup still logs two binary-token parse
  errors for that DDS and missing background-selector GUI controls. The old
  frontend lacks the current game's root background and manager types; the
  exact internal parser call is unverified. This compatibility issue remains.
- An unobstructed game screenshot and normal/hover/pressed/disabled campaign
  controls remain visually unaccepted: another foreground window covered the
  game during capture, and a direct window capture produced an empty frame.
  The user explicitly deferred visual inspection until later. No campaign or
  existing save was opened by this work.
  This limitation must not be presented as an in-game visual pass.

Receipts, original mapping backups, color/contact-sheet audits and the three
runtime attempts are private under `.local/ui-palette/`. The published
`UI_THEME_SPRITES.json` records exact opt-ins and original effect values.
Inherited background-selector, doctrine, mesh and other startup errors remain
separate issues; a successful theme startup does not establish campaign stability.

## Continuing and rollback

Inspect the main menu, pause menu and the mapped campaign panels at the user's
windowed settings before adding further skin opt-ins. Keep white text and
semantic status contrast. Do not recolor icons merely because they contain blue.

Revert the theme commit to return the effect mappings and shared shaders to the
previous revision. This theme does not change save data, DLC selection, Workshop
files or launcher membership. Gameplay diplomacy research is discussion-only
and has no implementation in this revision.
