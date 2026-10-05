# Era of Nations visual identity

Initial identity prepared on 2026-10-05 using the built-in image generation tool. The title is **ERA OF NATIONS**. The visual system uses silver lettering, a champagne-gold globe and orbital emblem, and dark navy geopolitical artwork.

## Game assets

| Asset | Dimensions | Native format | Purpose |
| --- | --- | --- | --- |
| `gfx/interface/logo_game.dds` | 560 × 407 | Uncompressed RGBA DDS | Transparent main-menu title |
| `gfx/event_pictures/global/era_of_nations_start_logo.dds` | 217 × 163 | DXT5 / BC3 DDS | Opening-event illustration |
| `thumbnail.png` | 500 × 500 | RGBA PNG | Launcher / project thumbnail |
| `docs/uploads/logo.png` | 500 × 500 | RGBA PNG | Documentation cover |
| `gfx/interface/topbar/musicplayer/era_of_nations_album_art.dds` | 304 × 120 | Uncompressed RGBA DDS | Two music-player states, each 152 × 120 |
| `gfx/era_of_nations_radio_station_cover.dds` | 304 × 120 | Uncompressed RGBA DDS | Two radio-station states |
| `gfx/HOI4_icon.bmp` | 48 × 48 | 32-bit BMP, V5 header and alpha masks | Compact mod icon |
| `gfx/interface/era_of_nations_project_icon.dds` | 55 × 55 | Uncompressed RGBA DDS | Project-link button icon |

The second music/radio tile has a gold selection border and a checked-square indicator. Both states preserve the original sheet dimensions and split position.

## Editable source images

The generated PNG masters are kept in `docs/branding/` so future work can reuse the same identity without deriving a new image from a compressed game texture:

- `era_of_nations_logo_master.png` — 1471 × 1069, transparent title and emblem.
- `era_of_nations_cover_master.png` — 1254 × 1254, opaque cover artwork.
- `era_of_nations_radio_master.png` — 1994 × 789, opaque two-state radio sheet.
- `era_of_nations_icon_master.png` — 1254 × 1254, transparent emblem without lettering.

Original replaced images are preserved locally under `.local/branding-originals/` with their original relative paths. `.local/` is excluded from Git. Source provenance and retained third-party credits are recorded separately in `SOURCE.md` and the relevant credit files.

## Generation prompts

All four images used the built-in image generation tool. No paid API or CLI fallback was used. Generated outputs were copied into this repository before native resizing and format conversion. Pillow handled deterministic downscaling and conversion only; it did not create or creatively edit the artwork.

### Title logo

> Use case: logo-brand. Asset type: polished title-screen logo for a modern geopolitical grand strategy Hearts of Iron IV submod. Create a brand-new distinctive standalone logo wordmark for "ERA OF NATIONS". Exact text (verbatim): "ERA OF NATIONS", set across two strong balanced lines: "ERA OF" above "NATIONS". All letters spelled correctly, sophisticated monumental uppercase typography, highly legible at small game-menu sizes. One restrained abstract globe-orbit emblem behind or above the title suggests world diplomacy and shifting power. Beautiful refined brushed silver typography with warm champagne-gold accent lines, clean confident shapes and restrained depth, credible premium strategy game identity. Composition: landscape roughly 560:407 proportions, centered compact emblem and title filling most of canvas, generous edge padding, no clipping. Truly transparent alpha background outside the logo, no solid rectangle, no background scene, no checkerboard baked into pixels. No additional text, subtitles, author credit, signatures, watermark, real national flags, prior mod names, or prior logos. The entire artwork must be original.

Tool setting: transparent background enabled; no reference image.

### Cover artwork

> Use case: compositing. Asset type: square game mod cover artwork, 1024×1024, for launcher thumbnail and project cover. Input image 1 is the original ERA OF NATIONS logo to preserve and insert exactly, including precise text and globe-and-orbit symbol. Create a beautiful premium modern geopolitical strategy-game cover around this identity. Scene: a dark midnight-blue world atlas with subtle illuminated city networks, a sophisticated skyline and distant modern naval silhouettes along the lower edge, warm golden dawn at the horizon, restrained diplomatic and strategic atmosphere. Balanced cinematic composition with clear central focal point. Large logo from reference centered in the upper-middle and occupying about 85% of the square width, fully readable, no clipping. Keep silver and champagne-gold lettering, retain exact text "ERA OF NATIONS". Preserve its logo design faithfully. High contrast against the dark navy background, polished realistic illustration, refined and serious, attractive at 500×500 and at small 152×120 radio-tile scale. No photographs of recognizable people, no existing mod logos, no previous mod names, no byline, author credits, no additional words, no watermark or promotional labels.

Tool setting: opaque background; reference was the generated title-logo master. The tool returned a 1254 × 1254 image.

### Radio sheet

> Use case: precise-object-edit. Asset type: radio music-player sprite sheet for Hearts of Iron IV, exact composition aspect 304:120. Input image 1 is edit target: a horizontal sheet containing two adjacent equal 152×120 music album tiles, the first normal and the second selected. Input image 2 is supporting replacement cover art for ERA OF NATIONS. Change only the artwork/content of the two album tiles to the Era of Nations artwork from image 2. Remove all prior mod names and the previous author byline from the tile faces. Each tile must display the same complete ERA OF NATIONS cover and its exact correctly spelled text; preserve tasteful fine frame edges in their original positions. First tile has restrained neutral silver border; second tile has gold selection border and a small gold checked-square icon in the top-right corner. Preserve the original two-tile geometry, keep both states, no gap or third tile, no missing frame, do not merge into one wide image. Background imagery remains dark navy modern map/city/horizon; title large and centered within each individual tile. Entire canvas completely filled by exactly these two equal adjacent tiles. No extra labels, authors, slogans, watermark. Output landscape 304:120 aspect ratio suitable for deterministic resize to304×120.

Tool setting: opaque background; references were the inspected original two-state album sheet and the generated Era of Nations cover. This record paraphrases the original-byline removal instruction; the replacement does not alter separate music-credit records.

### Compact icon

> Use case: logo-brand. Asset type: tiny 48×48 game-mod icon, generated as square image for native downscale. Supporting reference image: the ERA OF NATIONS logo and its globe-and-orbit emblem. Extract and redraw only its globe-and-orbit emblem as a compact clean icon with simplified bold shapes that remain readable at48 pixels. Keep original champagne-gold orbital ring and a dark navy globe with golden continents, but reduce fine texture and intricate detail. Centered globe and one diagonal elliptical orbit, compact silhouette filling 80% of square, polished but simple. Genuine transparent alpha background, no background rectangle. No title lettering, no words, no watermark, no national flags. This is an original companion icon consistent with the source logo identity.

Tool setting: transparent background enabled; reference was the generated title-logo master.

## Validation and scope

- Inspected the generated images and the final native-size main-menu logo, opening-event image, two-state album sheet, 48-pixel BMP and 55-pixel DDS.
- Reopened every written game image and checked its dimensions and RGBA decode.
- PNG, uncompressed DDS and BMP conversions round-trip their resized pixels exactly.
- Transparent title and icon assets retain alpha values from 0 to 255. The cover and radio sheets are opaque.
- DXT5 event-image payload matches the expected rounded-up 4 × 4 block count; its DDS linear-size field records the complete BC3 payload size.
- The BMP retains the original alpha-capable BITMAPV5HEADER and channel masks.
- Inspected all 13 existing loading-screen photographs. No upstream mod logo was visible in that set, so those textures were preserved.
- Reconstructed and inspected animation frames 0, 86, 172, 259, 345 and 431 from the frontend background. Its 60 horizontal DDS sheets each contain 432 strips of 32 × 1080 pixels; the strips reconstruct a 1920 × 1080 frame. No upstream mod logo was visible in those sampled frames. The animation was preserved. This is a sampled visual audit, not proof about every animation frame.

These checks confirm image files and visual previews. They do not confirm final in-game positioning, launcher behavior, rendering, or performance; those require a real launch and inspection in the same game build.
