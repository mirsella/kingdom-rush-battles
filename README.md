# Kingdom Rush Battles local asset dump

This dump was extracted from the installed Android package and its on-disk Unity cache.

## Scope

- Source APK: `inputs/device/apks/base.apk`
- Cached Unity bundles: `inputs/device/storage/com.ironhidegames.kingdomrush.mp/files/UnityCache/Shared/*/*/__data`
- Addressables catalog summary: `reports/summary.json`

## Exported assets

- `3609` sprites
- `1838` audio clips
- `1244` text assets
- `451` materials
- `228` shaders
- `21` meshes
- `7` fonts

## Troop-preserving exports

- `5` troop atlases
- `5` troop atlas pages
- `609` troop sprite metadata files
- `609` troop sprites
- `926` troop config text assets

These exports keep troop-related atlas pages, cropped sprites, sprite metadata, and config text assets under `assets/troops/` without exporting animation clips or controllers.
Actual unit art is organized first under `assets/troops/heroes`, `assets/troops/towers`, `assets/troops/creeps`, `assets/troops/bosses`, `assets/troops/reinforcements`, and `assets/troops/mercenaries`, while portraits, quickmenu art, cardinfo art, and shop/deck assets live under `assets/troops/ui`.

## Important limitation

The installed catalog references `125` remote CloudFront bundles that were not anonymously downloadable from the captured install. The app strings strongly suggest those bundle requests use authenticated cookies or API-mediated session state.

This means this dump is a strong local-first extraction, not yet a fully exhaustive remote-complete mirror.

## Reports

- `reports/summary.json`: extraction counts, per-source stats, and catalog summary
- `reports/errors.json`: the `4` decode/export failures that remained after extraction

## Extraction script

- Script: `scripts/extract_kingdom_rush_battles_assets.py`
- Runtime: `.venv-krb`
