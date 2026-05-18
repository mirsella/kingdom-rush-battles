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
- `418` Unity animation clips
- `126` Unity animator controllers
- `5134` Unity animator components
- `54` legacy Unity animation components

## Troop-preserving exports

- `5` troop atlases
- `5` troop atlas pages
- `609` troop sprite metadata files
- `609` troop sprites
- `926` troop config text assets

These exports keep troop-related atlas pages, cropped sprites, sprite metadata, and config text assets under `assets/troops/`.
Actual unit art is organized first under `assets/troops/heroes`, `assets/troops/towers`, `assets/troops/creeps`, `assets/troops/bosses`, `assets/troops/reinforcements`, and `assets/troops/mercenaries`, while portraits, quickmenu art, cardinfo art, and shop/deck assets live under `assets/troops/ui`.

## Animation exports

- `418` AnimationClip typetrees
- `126` AnimatorController typetrees
- `5134` Animator component typetrees
- `54` legacy Animation component typetrees

Animation data lives under `assets/animations/`. Each JSON file includes the full Unity typetree plus resolved asset references where available.
Use `assets/animations/index.json` or `reports/animation_index.json` to see which controllers, clips, animators, GameObjects, and container paths are linked together.

## Hero/tower animation metadata

- `384` hero/tower metadata configs indexed
- `1033` named animation timelines indexed
- `569` timelines include explicit frame indices
- `339` animation events indexed

Timeline metadata lives under `assets/troops/animations/metadata_index.json` and `reports/troop_animation_index.json`.
The config metadata is not enough to render correct playback from the PNG atlas by itself.
Atlas-sliced GIF previews are intentionally not generated because they produce incorrect flying-spritesheet results.

## FTRuntime/SWF animation runtime index

- `9393` FTRuntime/SWF runtime objects indexed
- `1649` troop-related FTRuntime/SWF runtime objects indexed

Runtime animation data lives under `assets/animations/ftruntime_index.json` and `reports/ftruntime_animation_index.json`.
This game uses FTRuntime/SWF-style Unity animation data for the hero/tower playback path, not a plain Spine atlas or simple sprite sheet.

## Important limitation

The installed catalog references `125` remote CloudFront bundles that were not anonymously downloadable from the captured install. The app strings strongly suggest those bundle requests use authenticated cookies or API-mediated session state.

This means this dump is a strong local-first extraction, not yet a fully exhaustive remote-complete mirror.

## Reports

- `reports/summary.json`: extraction counts, per-source stats, and catalog summary
- `reports/errors.json`: the `4` decode/export failures that remained after extraction
- `reports/animation_index.json`: Unity animation clips/controllers/animators index
- `reports/troop_animation_index.json`: hero/tower config animation timeline index
- `reports/ftruntime_animation_index.json`: FTRuntime/SWF runtime animation object index

## Included scripts

- `scripts/extract_kingdom_rush_battles_assets.py`: main Kingdom Rush Battles extractor used for this dump; reads `base.apk` plus cached Unity bundles and exports the organized asset tree, troop-preserving assets, Unity animation typetrees, FTRuntime/SWF runtime index, and reports.
- `scripts/restore_troop_animations.py`: indexes hero/tower troop metadata timelines from `assets/troops/configs/` and writes `assets/troops/animations/metadata_index.json` plus `reports/troop_animation_index.json`.
- `scripts/index_ftruntime_animations.py`: indexes FTRuntime/SWF Unity MonoBehaviour runtime animation objects needed for real hero/tower playback reconstruction.
- `scripts/extract_unity_xapk_assets.py`: generic Unity APK/XAPK extraction helper kept with the dump for future Android Unity extraction runs and comparison work.
- Runtime: `.venv-krb`
