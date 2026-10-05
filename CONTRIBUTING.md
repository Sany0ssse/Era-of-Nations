# Contributing to Era of Nations

Work from the [development repository](https://github.com/Sany0ssse/Era-of-Nations). The initial build preserves an inherited gameplay baseline; record each later gameplay change in `Changelog.txt` and describe its validation.

## File conventions

- Preserve existing script identifiers, country tags, event IDs, localisation keys, sprite names, and asset references when changing visible text.
- Preserve existing file encoding. Hearts of Iron IV localisation uses UTF-8 with BOM and the appropriate language header.
- Follow nearby formatting: scripts generally use tabs; localisation entries use one leading space.
- Keep source attribution, authors, music credits, and any asset notices intact.
- Avoid committing saves, game logs, launcher databases, tokens, or other local files.

## Validation

Check the edited content against its references, run relevant existing validation tools when applicable, and launch a separate test game before claiming gameplay acceptance. Static checks and a successful game menu load do not prove a campaign works.

See [setup](docs/development/SETUP.md), [source attribution](docs/development/SOURCE.md), and [validation status](docs/development/STATUS.md).
