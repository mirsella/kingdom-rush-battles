#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = ROOT
DEFAULT_GROUPS = ("heroes", "towers")
ANIMATION_ROOT = Path("assets/troops/animations")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def warn(message: str) -> None:
    print(f"[troop-animations] warning: {message}", file=sys.stderr)


def rel_path(output_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return path.as_posix()


def load_jsonish(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(
            f"skipping {path}: could not parse animation metadata ({type(exc).__name__}: {exc})"
        )
        return None
    if not isinstance(data, dict):
        warn(
            f"skipping {path}: metadata root is {type(data).__name__}, expected object"
        )
        return None
    return data


def atlas_stems(output_root: Path, group: str) -> dict[str, Path]:
    root = output_root / "assets" / "troops" / group
    return {path.stem.lower(): path for path in sorted(root.glob("*.png"))}


def match_atlas(metadata_path: Path, candidates: dict[str, Path]) -> Path | None:
    stem = metadata_path.name
    if stem.endswith("_metadata."):
        stem = stem[: -len("_metadata.")]
    elif stem.endswith("_metadata.txt"):
        stem = stem[: -len("_metadata.txt")]
    else:
        stem = metadata_path.stem
    stem_lower = stem.lower()

    matches = []
    for candidate_stem, candidate_path in candidates.items():
        if stem_lower == candidate_stem or stem_lower.startswith(candidate_stem + "_"):
            matches.append((len(candidate_stem), candidate_path))
    if not matches:
        return None
    return sorted(matches, reverse=True)[0][1]


def sorted_frame_indices(animation: dict[str, Any]) -> list[int]:
    frames = animation.get("frames")
    if not isinstance(frames, dict):
        return []
    indices = []
    for key in frames:
        try:
            indices.append(int(key))
        except (TypeError, ValueError):
            continue
    return sorted(indices)


def event_map(animation: dict[str, Any]) -> dict[str, int]:
    events = animation.get("events")
    if not isinstance(events, dict):
        return {}
    result = {}
    for name, value in events.items():
        try:
            result[str(name).strip()] = int(value)
        except (TypeError, ValueError):
            warn(f"skipping non-integer event frame for {name!r}: {value!r}")
    return result


def attachment_keys(animation: dict[str, Any]) -> list[str]:
    keys = set()
    attachs = animation.get("attachs")
    if isinstance(attachs, dict):
        keys.update(str(key) for key in attachs)
    frames = animation.get("frames")
    if isinstance(frames, dict):
        for frame in frames.values():
            if isinstance(frame, dict) and isinstance(frame.get("attachs"), dict):
                keys.update(str(key) for key in frame["attachs"])
    return sorted(keys)


def build_troop_animation_index(
    output_root: Path,
    groups: tuple[str, ...] = DEFAULT_GROUPS,
) -> dict[str, Any]:
    configs_root = output_root / "assets" / "troops" / "configs"
    records = []
    summary = Counter()
    warnings: list[str] = []

    if not configs_root.exists():
        message = (
            f"{configs_root} does not exist; no troop animation metadata was indexed"
        )
        warn(message)
        warnings.append(message)

    for group in groups:
        group_root = configs_root / group
        if not group_root.exists():
            message = f"{group_root} does not exist; skipping group"
            warn(message)
            warnings.append(message)
            continue

        candidates = atlas_stems(output_root, group)
        for metadata_path in sorted(group_root.glob("*metadata*")):
            summary["configs_scanned"] += 1
            data = load_jsonish(metadata_path)
            if data is None:
                summary["configs_skipped"] += 1
                continue

            atlas_path = match_atlas(metadata_path, candidates)
            if atlas_path is None:
                summary["configs_without_atlas"] += 1
                message = f"{metadata_path} has no matching atlas PNG in assets/troops/{group}"
                warn(message)
                warnings.append(message)
            else:
                summary["configs_with_atlas"] += 1

            config_record = {
                "group": group,
                "config_path": rel_path(output_root, metadata_path),
                "atlas_path": rel_path(output_root, atlas_path),
                "animations": [],
            }

            for animation_name, animation in sorted(data.items()):
                if not isinstance(animation, dict):
                    continue
                frame_indices = sorted_frame_indices(animation)
                events = event_map(animation)
                animation_record: dict[str, Any] = {
                    "name": animation_name,
                    "frame_indices": frame_indices,
                    "frame_count": len(frame_indices),
                    "events": events,
                    "attachment_keys": attachment_keys(animation),
                    "notes": [],
                }
                summary["animations"] += 1
                summary["events"] += len(events)
                if frame_indices:
                    summary["animations_with_frames"] += 1
                else:
                    animation_record["notes"].append(
                        "No explicit frames block was present; timeline/events are indexed."
                    )
                    summary["animations_without_frames"] += 1

                config_record["animations"].append(animation_record)

            if config_record["animations"]:
                records.append(config_record)
                summary["configs_with_animations"] += 1

    payload = {
        "summary": dict(summary),
        "notes": [
            "Hero/tower animation metadata is parsed from assets/troops/configs/*/*_metadata* text assets.",
            "These metadata files expose animation names, frame indices, events, and attachment transforms.",
            "These files are not simple Spine atlases or regular frame sheets; the PNG atlas must be combined with FTRuntime/SWF runtime data for real playback.",
            "No GIF/frame previews are generated because even-sheet atlas slicing produces incorrect flying-spritesheet previews.",
        ],
        "warnings": warnings[:200],
        "records": records,
    }
    write_json(output_root / ANIMATION_ROOT / "metadata_index.json", payload)
    write_json(output_root / "reports" / "troop_animation_index.json", payload)
    return {"counts": dict(summary), "record_count": len(records)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index Kingdom Rush Battles hero/tower animation metadata."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--groups", nargs="+", default=list(DEFAULT_GROUPS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_troop_animation_index(
        args.output_root,
        groups=tuple(args.groups),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
