#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = ROOT
DEFAULT_PACKAGE_ROOT = ROOT / "apps" / "kingdom-rush-battles"
DEFAULT_VENV_ROOT = ROOT / ".venv-krb"
DEFAULT_APK_PATH = DEFAULT_PACKAGE_ROOT / "inputs" / "device" / "apks" / "base.apk"
DEFAULT_CACHE_ROOT = (
    DEFAULT_PACKAGE_ROOT
    / "inputs"
    / "device"
    / "storage"
    / "com.ironhidegames.kingdomrush.mp"
    / "files"
    / "UnityCache"
    / "Shared"
)

FTRUNTIME_CLASSES = {
    "AnimationSettingsAsset",
    "EntityComponentAnimator",
    "FTRuntime.SwfAsset",
    "FTRuntime.SwfClip",
    "FTRuntime.SwfClipAsset",
    "FTRuntime.SwfClipController",
    "FTRuntime.SwfManager",
    "MP.Ingame.SwfAnimator",
    "MP.UI.SwfAnimatorUI",
    "SwfUIAnimation",
    "_MP.Utils.CustomAnimatorEvents",
}

TROOP_KEYWORDS = {
    "hero",
    "tower",
    "unit",
    "creep",
    "boss",
    "barrack",
    "mercenary",
    "reinforcement",
    "musketeer",
    "archer",
    "alleria",
    "ingvar",
}

POINTER_FIELDS = {
    "Atlas",
    "CustomAtlas",
    "Settings",
    "Sprite",
    "_clip",
    "metadataAsset",
    "shaderController",
    "swfAsset",
    "swfClipController",
}


def add_site_packages(venv_root: Path) -> None:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv_root / "lib" / version / "site-packages"
    if site_packages.exists():
        sys.path.insert(0, str(site_packages))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def warn(message: str) -> None:
    print(f"[ftruntime] warning: {message}", file=sys.stderr)


def discover_sources(apk_path: Path, cache_root: Path) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    if apk_path.exists():
        sources.append(("base_apk", apk_path))
    else:
        warn(f"{apk_path} does not exist; base APK skipped")

    if cache_root.exists():
        for data_path in sorted(cache_root.glob("*/*/__data")):
            sources.append((f"cache_{data_path.parent.parent.name}", data_path))
    else:
        warn(f"{cache_root} does not exist; Unity cache skipped")

    return sources


def script_class_name(script: Any) -> str | None:
    namespace = getattr(script, "m_Namespace", "") or ""
    class_name = getattr(script, "m_ClassName", None) or getattr(script, "m_Name", None)
    if not class_name:
        return None
    return f"{namespace}.{class_name}" if namespace else class_name


def pointer_ref(value: Any, names: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if "m_PathID" not in value:
        return None
    ref: dict[str, Any] = {
        "file_id": value.get("m_FileID", 0),
        "path_id": value.get("m_PathID"),
    }
    target = names.get(ref["path_id"])
    if target:
        ref.update(target)
    return ref


def pointer_path_id(value: Any) -> int | None:
    if isinstance(value, dict) and isinstance(value.get("m_PathID"), int):
        return value["m_PathID"]
    return None


def object_name_index(env: Any) -> dict[int, dict[str, Any]]:
    names: dict[int, dict[str, Any]] = {}
    for obj in env.objects:
        obj_type = obj.type.name
        if obj_type not in {
            "AudioClip",
            "GameObject",
            "Material",
            "MonoBehaviour",
            "MonoScript",
            "Sprite",
            "TextAsset",
            "Texture2D",
        }:
            continue
        try:
            data = obj.read_typetree() if obj_type == "MonoBehaviour" else obj.read()
        except Exception:
            continue
        name = getattr(data, "m_Name", None)
        if name is None and isinstance(data, dict):
            name = data.get("m_Name") or data.get("Name")
        names[obj.path_id] = {"target_type": obj_type, "target_name": name}
    return names


def script_index(env: Any) -> dict[int, str]:
    scripts: dict[int, str] = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            name = script_class_name(obj.read())
        except Exception:
            continue
        if name:
            scripts[obj.path_id] = name
    return scripts


def container_index(env: Any) -> dict[int, list[str]]:
    containers: dict[int, list[str]] = defaultdict(list)
    for container_path, pointer in env.container.items():
        asset = getattr(pointer, "asset", pointer)
        path_id = getattr(asset, "path_id", None)
        if path_id is not None:
            containers[path_id].append(str(container_path))
    return {path_id: sorted(paths) for path_id, paths in containers.items()}


def sequence_summaries(sequences: Any) -> list[dict[str, Any]]:
    if not isinstance(sequences, list):
        return []
    summaries = []
    for sequence in sequences:
        if not isinstance(sequence, dict):
            continue
        frames = sequence.get("Frames")
        frame_count = len(frames) if isinstance(frames, list) else 0
        labels = set()
        material_path_ids = set()
        vertex_counts = []
        if isinstance(frames, list):
            for frame in frames:
                if not isinstance(frame, dict):
                    continue
                for label in frame.get("Labels") or []:
                    labels.add(str(label))
                mesh = frame.get("MeshData")
                if isinstance(mesh, dict):
                    vertices = mesh.get("Vertices")
                    if isinstance(vertices, list):
                        vertex_counts.append(len(vertices))
                for material in frame.get("Materials") or []:
                    path_id = pointer_path_id(material)
                    if path_id is not None:
                        material_path_ids.add(path_id)
        summaries.append(
            {
                "name": sequence.get("Name"),
                "frame_count": frame_count,
                "labels": sorted(labels),
                "material_path_ids": sorted(material_path_ids),
                "min_vertex_count": min(vertex_counts) if vertex_counts else None,
                "max_vertex_count": max(vertex_counts) if vertex_counts else None,
            }
        )
    return summaries


def field_summary(
    data: dict[str, Any], names: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in sorted(POINTER_FIELDS):
        ref = pointer_ref(data.get(key), names)
        if ref:
            fields[key] = ref

    for key in [
        "AssetGUID",
        "FrameRate",
        "Hash",
        "Name",
        "Type",
        "_autoPlay",
        "_currentFrame",
        "_groupName",
        "_loopMode",
        "_playMode",
        "_rateScale",
        "_sequence",
        "sortingLayer",
        "sortingLayerOrder",
        "useCustomDuration",
    ]:
        value = data.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            fields[key] = value

    if isinstance(data.get("Data"), (str, bytes, list, dict)):
        value = data["Data"]
        fields["Data_summary"] = {
            "type": type(value).__name__,
            "length": len(value) if hasattr(value, "__len__") else None,
        }
    if isinstance(data.get("Settings"), (list, dict)) and "Settings" not in fields:
        value = data["Settings"]
        fields["Settings_summary"] = {
            "type": type(value).__name__,
            "length": len(value),
        }
    if "Sequences" in data:
        sequences = sequence_summaries(data.get("Sequences"))
        fields["sequence_count"] = len(sequences)
        fields["sequences"] = sequences
    return fields


def is_troop_related(record: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(value)
        for value in [
            record.get("class_name"),
            record.get("name"),
            record.get("game_object", {}).get("target_name"),
            " ".join(record.get("container_paths", [])),
            json.dumps(record.get("fields", {}), sort_keys=True),
        ]
    ).lower()
    return any(keyword in haystack for keyword in TROOP_KEYWORDS)


def build_ftruntime_index(
    output_root: Path,
    sources: list[tuple[str, Path]],
    unitypy_module: Any,
) -> dict[str, Any]:
    records = []
    summary = Counter()
    warnings: list[str] = []

    for source_label, source_path in sources:
        try:
            env = unitypy_module.load(str(source_path))
        except Exception as exc:
            message = (
                f"{source_path}: could not load source ({type(exc).__name__}: {exc})"
            )
            warn(message)
            warnings.append(message)
            continue

        scripts = script_index(env)
        names = object_name_index(env)
        containers = container_index(env)

        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                data = obj.read_typetree()
            except Exception as exc:
                message = f"{source_path}::{obj.path_id}: could not read MonoBehaviour ({type(exc).__name__}: {exc})"
                warn(message)
                warnings.append(message)
                continue
            if not isinstance(data, dict):
                continue

            script_ref = data.get("m_Script")
            script_path_id = pointer_path_id(script_ref)
            class_name = (
                scripts.get(script_path_id) if script_path_id is not None else None
            )
            if class_name not in FTRUNTIME_CLASSES:
                continue

            game_object = pointer_ref(data.get("m_GameObject"), names)
            record = {
                "source_label": source_label,
                "source_path": source_path.as_posix(),
                "asset_file": obj.assets_file.name,
                "path_id": obj.path_id,
                "class_name": class_name,
                "name": data.get("m_Name") or data.get("Name"),
                "game_object": game_object,
                "container_paths": containers.get(obj.path_id, []),
                "fields": field_summary(data, names),
            }
            record["troop_related"] = is_troop_related(record)
            records.append(record)
            summary["records"] += 1
            summary[f"class:{class_name}"] += 1
            if record["troop_related"]:
                summary["troop_related_records"] += 1
                summary[f"troop_class:{class_name}"] += 1

    class_counts = {
        key.removeprefix("class:"): count
        for key, count in summary.items()
        if key.startswith("class:")
    }
    troop_class_counts = {
        key.removeprefix("troop_class:"): count
        for key, count in summary.items()
        if key.startswith("troop_class:")
    }
    payload = {
        "summary": {
            "records": summary.get("records", 0),
            "troop_related_records": summary.get("troop_related_records", 0),
            "class_counts": dict(sorted(class_counts.items())),
            "troop_class_counts": dict(sorted(troop_class_counts.items())),
        },
        "notes": [
            "Kingdom Rush Battles hero/tower runtime animation data is FTRuntime/SWF-style Unity MonoBehaviour data, not a plain Spine atlas or regular sprite-sheet GIF source.",
            "FTRuntime.SwfClipAsset records include sequence names, frame counts, labels, material references, mesh vertex count ranges, and sprite references needed for a real decoder.",
            "This index does not render animations; it records the runtime objects that must be decoded to reconstruct correct playback.",
        ],
        "warnings": warnings[:200],
        "records": records,
    }
    write_json(output_root / "assets" / "animations" / "ftruntime_index.json", payload)
    write_json(output_root / "reports" / "ftruntime_animation_index.json", payload)
    return {
        "counts": payload["summary"],
        "record_count": len(records),
    }


def update_summary_report(output_root: Path, result: dict[str, Any]) -> None:
    summary_path = output_root / "reports" / "summary.json"
    if not summary_path.exists():
        warn(f"{summary_path} does not exist; summary report not updated")
        return
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"could not update {summary_path}: {type(exc).__name__}: {exc}")
        return
    if not isinstance(summary, dict):
        warn(f"could not update {summary_path}: expected object root")
        return
    summary["ftruntime_animation_index"] = result
    notes = [
        note
        for note in summary.get("notes", [])
        if "best-effort atlas-sliced previews" not in note
    ]
    notes.append(
        "Hero/tower playback uses FTRuntime/SWF runtime animation data; atlas-sliced GIF previews were removed because they are incorrect. See reports/ftruntime_animation_index.json."
    )
    summary["notes"] = notes
    write_json(summary_path, summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index Kingdom Rush Battles FTRuntime/SWF animation runtime objects."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--venv-root", type=Path, default=DEFAULT_VENV_ROOT)
    parser.add_argument("--apk-path", type=Path, default=DEFAULT_APK_PATH)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--update-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    add_site_packages(args.venv_root)
    try:
        import UnityPy  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            f"UnityPy is not available. Install it into {args.venv_root} before running this script."
        ) from exc

    sources = discover_sources(args.apk_path, args.cache_root)
    result = build_ftruntime_index(args.output_root, sources, UnityPy)
    if args.update_summary:
        update_summary_report(args.output_root, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
