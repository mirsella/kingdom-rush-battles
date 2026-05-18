#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
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


def safe_name(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("._") or "unnamed"


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


def infer_sheet_grid(
    frame_count: int, width: int, height: int
) -> tuple[int, int] | None:
    if frame_count < 1:
        return None
    if frame_count == 1:
        return (1, 1)

    image_ratio = width / height if height else 1
    pairs = []
    for rows in range(1, int(math.sqrt(frame_count)) + 1):
        if frame_count % rows:
            continue
        columns = frame_count // rows
        cell_w = width / columns
        cell_h = height / rows
        if cell_w < 16 or cell_h < 16:
            continue
        if max(cell_w / cell_h, cell_h / cell_w) > 4:
            continue
        ratio_error = abs((columns / rows) - image_ratio)
        pairs.append((ratio_error, columns, rows))
    if not pairs:
        return None
    _, columns, rows = sorted(pairs)[0]
    return (columns, rows)


def write_preview(
    output_root: Path,
    atlas_path: Path,
    group: str,
    metadata_path: Path,
    animation_name: str,
    frame_count: int,
    fps: int,
    write_frames: bool,
) -> tuple[str | None, list[str], str | None]:
    try:
        from PIL import Image
    except ImportError:
        return (
            None,
            [],
            "Pillow is not installed; install pillow to write GIF/frame previews",
        )

    image = Image.open(atlas_path).convert("RGBA")
    grid = infer_sheet_grid(frame_count, *image.size)
    if grid is None:
        return (
            None,
            [],
            f"could not infer an even sheet grid for {frame_count} frames",
        )

    columns, rows = grid
    cell_w = image.width // columns
    cell_h = image.height // rows
    if cell_w <= 0 or cell_h <= 0:
        return (None, [], f"invalid inferred cell size {cell_w}x{cell_h}")

    frames = []
    frame_paths = []
    stem = safe_name(
        metadata_path.name.replace("_metadata.", "").replace("_metadata.txt", "")
    )
    animation_slug = safe_name(animation_name)

    for index in range(frame_count):
        row = index // columns
        column = index % columns
        if row >= rows:
            break
        frame = image.crop(
            (column * cell_w, row * cell_h, (column + 1) * cell_w, (row + 1) * cell_h)
        )
        frames.append(frame)
        if write_frames:
            frame_path = (
                output_root
                / ANIMATION_ROOT
                / "frames"
                / group
                / stem
                / animation_slug
                / f"frame_{index:03d}.png"
            )
            ensure_parent(frame_path)
            frame.save(frame_path)
            frame_paths.append(
                rel_path(output_root, frame_path) or frame_path.as_posix()
            )

    if not frames:
        return (None, frame_paths, "no frames were produced from inferred sheet grid")

    preview_path = (
        output_root
        / ANIMATION_ROOT
        / "previews"
        / group
        / stem
        / f"{animation_slug}.gif"
    )
    ensure_parent(preview_path)
    duration_ms = max(1, round(1000 / max(1, fps)))
    frames[0].save(
        preview_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    return (rel_path(output_root, preview_path), frame_paths, None)


def build_troop_animation_index(
    output_root: Path,
    groups: tuple[str, ...] = DEFAULT_GROUPS,
    write_previews: bool = False,
    write_frames: bool = False,
    preview_limit: int | None = None,
    fps: int = 12,
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
                message = f"{metadata_path} has no matching atlas PNG in assets/troops/{group}; previews skipped"
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
                        "No explicit frames block was present; timeline/events are indexed, preview not generated."
                    )
                    summary["animations_without_frames"] += 1

                can_preview = atlas_path is not None and bool(frame_indices)
                if write_previews and can_preview:
                    if (
                        preview_limit is not None
                        and summary["previews_written"] >= preview_limit
                    ):
                        animation_record["notes"].append(
                            "Preview skipped because preview limit was reached."
                        )
                        summary["previews_skipped_limit"] += 1
                    else:
                        preview_path, frame_paths, error = write_preview(
                            output_root,
                            atlas_path,
                            group,
                            metadata_path,
                            animation_name,
                            len(frame_indices),
                            fps,
                            write_frames,
                        )
                        if error:
                            animation_record["notes"].append(error)
                            summary["previews_failed"] += 1
                            warnings.append(
                                f"{metadata_path}::{animation_name}: {error}"
                            )
                        else:
                            animation_record["preview_gif"] = preview_path
                            if frame_paths:
                                animation_record["frame_paths"] = frame_paths
                            animation_record["preview_method"] = (
                                "best_effort_even_sheet_slice"
                            )
                            animation_record["notes"].append(
                                "Preview was produced by slicing the matched PNG as an even sprite sheet; this is not a confirmed skeletal reconstruction."
                            )
                            summary["previews_written"] += 1
                elif write_previews and not can_preview:
                    summary["previews_skipped_missing_data"] += 1

                config_record["animations"].append(animation_record)

            if config_record["animations"]:
                records.append(config_record)
                summary["configs_with_animations"] += 1

    payload = {
        "summary": dict(summary),
        "notes": [
            "Hero/tower animation metadata is parsed from assets/troops/configs/*/*_metadata* text assets.",
            "These metadata files expose animation names, frame indices, events, and attachment transforms.",
            "Exact layered or skeletal animation restoration is not possible from the exported PNG atlas plus this metadata alone because per-part draw order and crop/layer binding data is not present in these files.",
            "GIF/frame previews, when requested, are explicitly marked best-effort and use even sheet slicing of the matched PNG atlas.",
        ],
        "warnings": warnings[:200],
        "records": records,
    }
    write_json(output_root / ANIMATION_ROOT / "metadata_index.json", payload)
    write_json(output_root / "reports" / "troop_animation_index.json", payload)
    return {"counts": dict(summary), "record_count": len(records)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index Kingdom Rush Battles hero/tower animation metadata and optionally write best-effort previews."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--groups", nargs="+", default=list(DEFAULT_GROUPS))
    parser.add_argument("--write-previews", action="store_true")
    parser.add_argument("--write-frames", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=None)
    parser.add_argument("--fps", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_troop_animation_index(
        args.output_root,
        groups=tuple(args.groups),
        write_previews=args.write_previews,
        write_frames=args.write_frames,
        preview_limit=args.preview_limit,
        fps=args.fps,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
