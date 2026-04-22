# Kingdom Rush Battles

Extracted assets from the installed Android build for `com.ironhidegames.kingdomrush.mp`.

## Version

- Source dump: installed phone extract + on-disk Unity cache
- Package name: `com.ironhidegames.kingdomrush.mp`
- Public repo layout: flattened asset-first export

## Contents

- `assets/audio/`: exported audio clips
- `assets/fonts/`: extracted TTF and OTF fonts
- `assets/materials/`: Unity material metadata JSON
- `assets/meshes/`: exported OBJ meshes
- `assets/shaders/`: exported shader text
- `assets/sprites/`: exported sprite PNGs
- `assets/textassets/`: extracted text and JSON assets
- `assets/textures/`: exported texture PNGs
- `reports/`: extraction summary and remaining decode failures
- `scripts/`: helper script used to build the dump

## Export Summary

- `3213` sprites
- `437` textures
- `1016` audio clips
- `758` text assets
- `372` materials
- `165` shaders
- `21` meshes
- `7` fonts

## Extraction Notes

1. Loaded the installed `base.apk` as a Unity data source with UnityPy.
2. Loaded the locally cached UnityFS bundles from `UnityCache/Shared/*/*/__data`.
3. Exported browse-friendly decoded assets into top-level type buckets under `assets/`.
4. Flattened the public layout while keeping one shallow grouping level for large buckets such as sprites, textures, audio, and text assets.
5. Excluded user save/config data from the public dump.

## Notes

- This repo intentionally keeps decoded extraction outputs suitable for public release, not the original APK or raw Unity bundle containers.
- The installed catalog references `125` remote CloudFront bundles that were not anonymously downloadable from the captured install. App strings strongly suggest those requests use authenticated cookies or API-mediated session state.
- This means the repo is a strong local-first extraction, not yet a fully exhaustive remote-complete mirror.
- `reports/summary.json` is the authoritative summary for counts, per-source stats, and catalog findings.
- `reports/errors.json` records the `11` remaining malformed shader or empty streamed-texture export failures.

## Included Script

- `scripts/extract_kingdom_rush_battles_assets.py`: main package-specific Unity extractor and organizer
