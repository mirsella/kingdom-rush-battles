#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKAGE_ROOT = ROOT / "apps" / "kingdom-rush-battles"
DEFAULT_OUTPUT_ROOT = DEFAULT_PACKAGE_ROOT / "work" / "public"
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
DEFAULT_CATALOG_PATH = (
    DEFAULT_PACKAGE_ROOT
    / "inputs"
    / "device"
    / "storage"
    / "com.ironhidegames.kingdomrush.mp"
    / "files"
    / "com.unity.addressables"
    / "catalog_2026.03.31.15.57.22.json"
)

TEXT_EXTENSIONS = {
    "",
    ".asset",
    ".bytes",
    ".cfg",
    ".csv",
    ".fnt",
    ".htm",
    ".html",
    ".json",
    ".lua",
    ".md",
    ".shader",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]+")
REDACTED_GOOGLE_API_KEY = "[REDACTED_GOOGLE_API_KEY]"

GENERIC_PATH_PARTS = {
    "android",
    "asset",
    "assets",
    "audio",
    "common",
    "commonlocal",
    "content",
    "font",
    "fonts",
    "material",
    "materials",
    "mesh",
    "meshes",
    "resources",
    "shader",
    "shaders",
    "shared",
    "sound",
    "sounds",
    "special",
    "sprite",
    "sprites",
    "text",
    "textassets",
    "texture",
    "textures",
}

BUCKET_PARENT_DEPTH = {
    "audio": 1,
    "materials": 1,
    "sprites": 1,
    "textassets": 1,
    "textures": 1,
}

NAME_GROUP_BUCKETS = {"audio", "sprites", "textassets", "textures"}

TROOP_KEYWORDS = {
    "hero",
    "creep",
    "tower",
    "mercenary",
    "reinforcement",
    "troop",
    "boss",
    "enemy",
    "barrack",
}

TROOP_UI_MARKERS = {
    "asst_",
    "avatar",
    "background",
    "bk_",
    "button",
    "boosters",
    "build",
    "cardinfo",
    "container",
    "deck",
    "emote",
    "frame",
    "front",
    "glow",
    "hud",
    "icon",
    "mask",
    "metagame",
    "playerprofile",
    "player_profile",
    "popupwindow",
    "portrait",
    "quickmenu",
    "shop",
    "skill",
    "slot",
    "stat",
    "swfatlas",
    "trophyroad",
    "towers-quickmenu",
    "towerskills-quickmenu",
}

TROOP_PRIMARY_GROUPS = [
    ("boss", "bosses"),
    ("reinforcement", "reinforcements"),
    ("mercenary", "mercenaries"),
    ("creep", "creeps"),
    ("enemy", "creeps"),
    ("tower", "towers"),
    ("barrack", "towers"),
    ("hero", "heroes"),
]


def add_site_packages(venv_root: Path) -> None:
    for path in sorted(venv_root.glob("lib/python*/site-packages")):
        sys.path.insert(0, str(path))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sanitize_part(value: str) -> str:
    cleaned = []
    for char in value.strip().replace("\\", "/"):
        if char.isalnum() or char in {
            "-",
            "_",
            ".",
            " ",
            "@",
            "+",
            "=",
            ",",
            "(",
            ")",
            "[",
            "]",
        }:
            cleaned.append(char)
        else:
            cleaned.append("_")
    text = "".join(cleaned).strip(" .")
    if not text:
        return "unnamed"
    if text in {".", ".."}:
        return text.replace(".", "dot")
    return text


def sanitize_rel_path(path_str: str) -> Path:
    parts = [
        sanitize_part(part)
        for part in path_str.replace("\\", "/").split("/")
        if part and part != "."
    ]
    if not parts:
        return Path("unnamed")
    return Path(*parts)


def slugify(value: str) -> str:
    return sanitize_part(value).replace(" ", "_")


def derive_name_group(filename: str) -> str | None:
    stem = Path(filename).stem.strip()
    if not stem:
        return None

    token = re.split(r"[^A-Za-z0-9]+", stem, maxsplit=1)[0]
    if not token:
        return None

    if token == stem:
        camel = re.match(r"[A-Z][a-z]+", stem)
        if camel is not None and camel.group(0) != stem:
            token = camel.group(0)
        else:
            letters = re.match(r"[A-Za-z]+", stem)
            if letters is not None and letters.group(0) != stem:
                token = letters.group(0)

    token = sanitize_part(token)
    if not token or token.lower() == sanitize_part(stem).lower():
        return None
    return token


def guess_font_extension(font_data: bytes) -> str:
    if font_data.startswith(b"OTTO"):
        return ".otf"
    if font_data.startswith(b"ttcf"):
        return ".ttc"
    if font_data[:4] in {b"\x00\x01\x00\x00", b"true"}:
        return ".ttf"
    if font_data.startswith(b"wOFF"):
        return ".woff"
    if font_data.startswith(b"wOF2"):
        return ".woff2"
    return ".bin"


def bytes_from_value(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, list):
        return bytes(value)
    raise TypeError(f"unsupported byte value {type(value).__name__}")


def redact_public_text(text: str) -> str:
    return GOOGLE_API_KEY_RE.sub(REDACTED_GOOGLE_API_KEY, text)


def jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return repr(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes_from_value(value)
        return {"byte_length": len(raw)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        if len(value) > 64:
            return {
                "item_count": len(value),
                "preview": [jsonable(item, depth + 1) for item in list(value)[:8]],
            }
        return [jsonable(item, depth + 1) for item in value]
    if hasattr(value, "__dict__"):
        result = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            result[key] = jsonable(item, depth + 1)
        if result:
            return result
    return repr(value)


def is_troop_related(*values: Any) -> bool:
    haystack = " ".join(str(value) for value in values if value).lower()
    if not haystack:
        return False
    return any(keyword in haystack for keyword in TROOP_KEYWORDS)


def troop_group(*values: Any, for_config: bool = False) -> str:
    haystack = " ".join(str(value) for value in values if value).lower()
    if not haystack:
        return "other"

    if for_config and any(token in haystack for token in {"mg_", "/mg/", "metagame"}):
        return "meta"

    if any(marker in haystack for marker in TROOP_UI_MARKERS):
        return "ui"

    for keyword, group in TROOP_PRIMARY_GROUPS:
        if keyword in haystack:
            return group

    return "other"


def rect_to_json(rect: Any) -> dict[str, float] | None:
    if rect is None:
        return None
    payload = {}
    for key in ("x", "y", "width", "height"):
        value = getattr(rect, key, None)
        if value is None and isinstance(rect, dict):
            value = rect.get(key)
        if value is None:
            return None
        payload[key] = float(value)
    return payload


def vector_to_json(vec: Any, fields: tuple[str, ...]) -> dict[str, float] | None:
    if vec is None:
        return None
    payload = {}
    for key in fields:
        value = getattr(vec, key, None)
        if value is None and isinstance(vec, dict):
            value = vec.get(key)
        if value is None:
            return None
        payload[key] = float(value)
    return payload


def choose_container_path(paths: list[str], fallback_name: str) -> str:
    if not paths:
        return fallback_name
    for candidate in paths:
        if Path(candidate).suffix.lower() not in {
            ".prefab",
            ".controller",
            ".anim",
            ".mat",
            ".asset",
        }:
            return candidate
    return paths[0]


def build_shallow_logical_path(
    path_str: str,
    suffix: str,
    parent_depth: int = 1,
    bucket: str | None = None,
) -> Path:
    logical_path = sanitize_rel_path(path_str)
    logical_path = swap_extension(logical_path, suffix)
    if len(logical_path.parts) == 1:
        if bucket in NAME_GROUP_BUCKETS:
            name_group = derive_name_group(logical_path.name)
            if name_group is not None:
                return Path(name_group) / logical_path.name
        return logical_path

    filename = logical_path.name
    parents = [
        part
        for part in logical_path.parts[:-1]
        if part.lower() not in GENERIC_PATH_PARTS
    ]
    if not parents:
        if bucket in NAME_GROUP_BUCKETS:
            name_group = derive_name_group(filename)
            if name_group is not None:
                return Path(name_group) / filename
        return Path(filename)
    kept_parents = parents[-max(parent_depth, 1) :]
    return Path(*kept_parents) / filename


def troop_export_name(
    container_paths: list[str], fallback_name: str, suffix: str
) -> str:
    return build_shallow_logical_path(
        choose_container_path(container_paths, fallback_name),
        suffix,
        parent_depth=1,
    ).name


def swap_extension(path: Path, suffix: str) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    if path.suffix:
        return path.with_suffix(suffix)
    return path.with_name(path.name + suffix)


def discover_sources(apk_path: Path, cache_root: Path) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    if apk_path.exists():
        sources.append(("base_apk", apk_path))
    for path in sorted(cache_root.glob("**/__data")):
        bundle_key = path.parent.parent.name
        sources.append((f"cache_{bundle_key}", path))
    return sources


def summarize_catalog(catalog_path: Path) -> dict[str, Any] | None:
    if not catalog_path.exists():
        return None
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    internal_ids = data.get("m_InternalIds", [])
    classes = Counter()
    for item in internal_ids:
        if isinstance(item, str) and item.startswith("https://"):
            classes["https"] += 1
        elif isinstance(item, str) and item.startswith("http://"):
            classes["http"] += 1
        elif isinstance(item, str) and item.startswith(
            "{UnityEngine.AddressableAssets.Addressables.RuntimePath}"
        ):
            classes["runtimepath"] += 1
        elif isinstance(item, str) and item.startswith("Assets/"):
            classes["assets_path"] += 1
        else:
            classes["other"] += 1
    return {
        "catalog_path": str(catalog_path),
        "locator_id": data.get("m_LocatorId"),
        "build_result_hash": data.get("m_BuildResultHash"),
        "internal_id_count": len(internal_ids),
        "internal_id_classes": dict(classes),
        "provider_id_count": len(data.get("m_ProviderIds", [])),
        "resource_type_count": len(data.get("m_resourceTypes", [])),
        "entry_data_length": len(data.get("m_EntryDataString", "")),
        "sample_remote_ids": [
            item
            for item in internal_ids
            if isinstance(item, str) and item.startswith("https://")
        ][:10],
        "sample_runtime_ids": [
            item
            for item in internal_ids
            if isinstance(item, str)
            and item.startswith(
                "{UnityEngine.AddressableAssets.Addressables.RuntimePath}"
            )
        ][:10],
    }


def render_readme(manifest: dict[str, Any]) -> str:
    exports = manifest.get("global_exports", {})
    troop_exports = manifest.get("troop_exports", {})
    catalog_summary = manifest.get("catalog_summary") or {}
    error_count = len((manifest.get("errors") or []))
    export_lines = []
    for key, label in [
        ("sprites", "sprites"),
        ("audio", "audio clips"),
        ("textassets", "text assets"),
        ("materials", "materials"),
        ("shaders", "shaders"),
        ("meshes", "meshes"),
        ("fonts", "fonts"),
    ]:
        count = exports.get(key, 0)
        if count:
            export_lines.append(f"- `{count}` {label}")
    troop_lines = []
    for key, label in [
        ("atlases", "troop atlases"),
        ("atlas_pages", "troop atlas pages"),
        ("sprite_metadata", "troop sprite metadata files"),
        ("sprites", "troop sprites"),
        ("textassets", "troop config text assets"),
    ]:
        count = troop_exports.get(key, 0)
        if count:
            troop_lines.append(f"- `{count}` {label}")
    return "\n".join(
        [
            "# Kingdom Rush Battles local asset dump",
            "",
            "This dump was extracted from the installed Android package and its on-disk Unity cache.",
            "",
            "## Scope",
            "",
            "- Source APK: `inputs/device/apks/base.apk`",
            "- Cached Unity bundles: `inputs/device/storage/com.ironhidegames.kingdomrush.mp/files/UnityCache/Shared/*/*/__data`",
            "- Addressables catalog summary: `reports/summary.json`",
            "",
            "## Exported assets",
            "",
            *export_lines,
            "",
            "## Troop-preserving exports",
            "",
            *troop_lines,
            "",
            "These exports keep troop-related atlas pages, cropped sprites, sprite metadata, and config text assets under `assets/troops/` without exporting animation clips or controllers.",
            "Actual unit art is organized first under `assets/troops/heroes`, `assets/troops/towers`, `assets/troops/creeps`, `assets/troops/bosses`, `assets/troops/reinforcements`, and `assets/troops/mercenaries`, while portraits, quickmenu art, cardinfo art, and shop/deck assets live under `assets/troops/ui`.",
            "",
            "## Important limitation",
            "",
            f"The installed catalog references `{catalog_summary.get('internal_id_classes', {}).get('https', 0)}` remote CloudFront bundles that were not anonymously downloadable from the captured install. The app strings strongly suggest those bundle requests use authenticated cookies or API-mediated session state.",
            "",
            "This means this dump is a strong local-first extraction, not yet a fully exhaustive remote-complete mirror.",
            "",
            "## Reports",
            "",
            "- `reports/summary.json`: extraction counts, per-source stats, and catalog summary",
            f"- `reports/errors.json`: the `{error_count}` decode/export failures that remained after extraction",
            "",
            "## Extraction script",
            "",
            "- Script: `scripts/extract_kingdom_rush_battles_assets.py`",
            "- Runtime: `.venv-krb`",
            "",
        ]
    )


class Exporter:
    def __init__(self, output_root: Path, unitypy_module: Any) -> None:
        self.output_root = output_root
        self.UnityPy = unitypy_module
        self.errors: list[dict[str, Any]] = []
        self.global_exports = Counter()
        self.global_types = Counter()
        self.troop_exports = Counter()

    def claim_target(self, target: Path, path_id: int) -> Path:
        if not target.exists():
            return target
        return target.with_name(f"{target.stem}__{path_id}{target.suffix}")

    def build_container_index(self, env: Any) -> dict[tuple[str, int], list[str]]:
        index: dict[tuple[str, int], list[str]] = defaultdict(list)
        for container_path, pointer in env.container.items():
            asset = getattr(pointer, "asset", pointer)
            path_id = getattr(asset, "path_id", None)
            assets_file = getattr(asset, "assets_file", None)
            assets_name = getattr(assets_file, "name", None)
            if path_id is None or assets_name is None:
                continue
            index[(assets_name, path_id)].append(container_path)
        return index

    def target_from_container(
        self, bucket: str, container_paths: list[str], fallback_name: str, suffix: str
    ) -> Path:
        logical_path = build_shallow_logical_path(
            choose_container_path(container_paths, fallback_name),
            suffix,
            BUCKET_PARENT_DEPTH.get(bucket, 1),
            bucket,
        )
        return self.output_root / "assets" / bucket / logical_path

    def export_bytes(self, target: Path, data: bytes) -> None:
        ensure_parent(target)
        target.write_bytes(data)

    def export_text(self, target: Path, text: str) -> None:
        ensure_parent(target)
        text = redact_public_text(text)
        target.write_bytes(text.encode("utf-8", errors="surrogatepass"))

    def note_troop_export(self, bucket: str) -> None:
        self.troop_exports[bucket] += 1

    def troop_sprite_target(
        self, object_name: str, container_paths: list[str], suffix: str
    ) -> Path:
        group = troop_group(object_name, *container_paths)
        filename = troop_export_name(container_paths, object_name, suffix)
        return self.output_root / "assets" / "troops" / group / filename

    def troop_metadata_target(
        self, object_name: str, container_paths: list[str], suffix: str
    ) -> Path:
        group = troop_group(object_name, *container_paths)
        filename = troop_export_name(container_paths, object_name, suffix)
        return self.output_root / "assets" / "troops" / "metadata" / group / filename

    def troop_config_target(
        self, container_choice: str, container_paths: list[str], suffix: str
    ) -> Path:
        group = troop_group(container_choice, *container_paths, for_config=True)
        filename = troop_export_name(container_paths, container_choice, suffix)
        return self.output_root / "assets" / "troops" / "configs" / group / filename

    def export_troop_sprite(
        self, obj: Any, data: Any, container_paths: list[str], object_name: str
    ) -> None:
        search_values = [object_name, *container_paths]
        if not is_troop_related(*search_values):
            return

        sprite_target = self.troop_sprite_target(object_name, container_paths, ".png")
        sprite_target = self.claim_target(sprite_target, obj.path_id)
        ensure_parent(sprite_target)
        data.image.save(sprite_target)
        self.note_troop_export("sprites")

        texture_name = None
        texture_path_id = None
        texture_ptr = getattr(getattr(data, "m_RD", None), "texture", None)
        if texture_ptr is not None and getattr(texture_ptr, "path_id", 0):
            texture_path_id = getattr(texture_ptr, "path_id", None)
            try:
                texture_name = getattr(texture_ptr.read(), "m_Name", None)
            except Exception:
                texture_name = None

        metadata = {
            "name": object_name,
            "texture_name": texture_name,
            "texture_path_id": texture_path_id,
            "rect": rect_to_json(getattr(data, "m_Rect", None)),
            "texture_rect": rect_to_json(
                getattr(getattr(data, "m_RD", None), "textureRect", None)
            ),
            "pivot": vector_to_json(getattr(data, "m_Pivot", None), ("x", "y")),
            "border": vector_to_json(
                getattr(data, "m_Border", None), ("x", "y", "z", "w")
            ),
            "pixels_to_units": getattr(data, "m_PixelsToUnits", None),
        }
        metadata_target = self.troop_metadata_target(
            object_name, container_paths, ".json"
        )
        metadata_target = self.claim_target(metadata_target, obj.path_id)
        write_json(metadata_target, metadata)
        self.note_troop_export("sprite_metadata")

    def export_troop_textasset(
        self, obj: Any, script: Any, container_paths: list[str], container_choice: str
    ) -> None:
        search_values = [container_choice, *container_paths]
        if not is_troop_related(*search_values):
            return

        suffix = Path(container_choice).suffix.lower()
        if suffix not in TEXT_EXTENSIONS:
            suffix = ".txt"
        target = self.troop_config_target(container_choice, container_paths, suffix)
        target = self.claim_target(target, obj.path_id)
        if isinstance(script, str):
            self.export_text(target, script)
        else:
            self.export_bytes(target, bytes_from_value(script))
        self.note_troop_export("textassets")

    def export_troop_atlas(self, obj: Any, object_name: str) -> None:
        tree = obj.read_typetree()
        packed_names = tree.get("m_PackedSpriteNamesToIndex", []) or []
        troop_names = [name for name in packed_names if is_troop_related(name)]
        if not troop_names:
            return

        atlas_slug = slugify(object_name)
        troops_root = self.output_root / "assets" / "troops"
        atlas_manifest_path = troops_root / "atlases" / f"{atlas_slug}.json"
        pages_root = troops_root / "atlas_pages"
        render_map = tree.get("m_RenderDataMap", []) or []
        page_paths: dict[int, str] = {}
        entries = []

        for index, sprite_name in enumerate(packed_names):
            if not is_troop_related(sprite_name):
                continue
            render_entry = render_map[index][1] if index < len(render_map) else None
            if not isinstance(render_entry, dict):
                continue

            texture_ref = render_entry.get("texture") or {}
            texture_path_id = texture_ref.get("m_PathID")
            page_path = None
            texture_name = None
            if texture_path_id:
                if texture_path_id not in page_paths:
                    texture_obj = obj.assets_file.objects.get(texture_path_id)
                    if texture_obj is not None:
                        texture_name = getattr(texture_obj.read(), "m_Name", None)
                        page_target = (
                            pages_root
                            / f"{atlas_slug}__{slugify(texture_name or sprite_name)}.png"
                        )
                        page_target = self.claim_target(
                            page_target, texture_obj.path_id
                        )
                        ensure_parent(page_target)
                        texture_obj.read().image.save(page_target)
                        page_paths[texture_path_id] = str(
                            page_target.relative_to(troops_root)
                        )
                        self.note_troop_export("atlas_pages")
                page_path = page_paths.get(texture_path_id)
                if texture_name is None:
                    texture_obj = obj.assets_file.objects.get(texture_path_id)
                    if texture_obj is not None:
                        texture_name = getattr(texture_obj.read(), "m_Name", None)

            entries.append(
                {
                    "name": sprite_name,
                    "texture_name": texture_name,
                    "texture_path": page_path,
                    "texture_rect": render_entry.get("textureRect"),
                    "texture_rect_offset": render_entry.get("textureRectOffset"),
                    "atlas_rect_offset": render_entry.get("atlasRectOffset"),
                    "uv_transform": render_entry.get("uvTransform"),
                    "downscale_multiplier": render_entry.get("downscaleMultiplier"),
                    "settings_raw": render_entry.get("settingsRaw"),
                }
            )

        manifest = {
            "atlas_name": object_name,
            "packed_sprite_count": len(packed_names),
            "troop_sprite_count": len(entries),
            "troop_sprite_names": troop_names,
            "entries": entries,
        }
        write_json(atlas_manifest_path, manifest)
        self.note_troop_export("atlases")

    def export_object(
        self,
        obj: Any,
        container_index: dict[tuple[str, int], list[str]],
    ) -> tuple[str | None, Path | None]:
        object_type = obj.type.name
        if object_type not in {
            "AudioClip",
            "Font",
            "Material",
            "Mesh",
            "Shader",
            "Sprite",
            "SpriteAtlas",
            "TextAsset",
            "Texture2D",
        }:
            return None, None

        data = obj.read()
        asset_key = (obj.assets_file.name, obj.path_id)
        container_paths = container_index.get(asset_key, [])
        object_name = getattr(data, "m_Name", None) or object_type.lower()

        if object_type == "Sprite":
            target = self.target_from_container(
                "sprites", container_paths, object_name, ".png"
            )
            target = self.claim_target(target, obj.path_id)
            ensure_parent(target)
            data.image.save(target)
            self.export_troop_sprite(obj, data, container_paths, object_name)
            return "sprites", target

        if object_type == "Texture2D":
            return None, None

        if object_type == "AudioClip":
            samples = getattr(data, "samples", {}) or {}
            if not samples:
                return None, None
            first_name, first_bytes = next(iter(samples.items()))
            candidate = choose_container_path(container_paths, first_name)
            target = self.target_from_container(
                "audio",
                container_paths,
                candidate,
                Path(first_name).suffix or ".bin",
            )
            target = self.claim_target(target, obj.path_id)
            self.export_bytes(target, bytes_from_value(first_bytes))
            return "audio", target

        if object_type == "TextAsset":
            script = getattr(data, "m_Script", None)
            if script is None:
                script = getattr(data, "script", None)
            if script is None:
                return None, None
            container_choice = choose_container_path(container_paths, object_name)
            suffix = Path(container_choice).suffix.lower()
            if suffix not in TEXT_EXTENSIONS:
                suffix = ".txt"
            if isinstance(script, str):
                target = self.target_from_container(
                    "textassets",
                    container_paths,
                    container_choice,
                    suffix or ".txt",
                )
                target = self.claim_target(target, obj.path_id)
                self.export_text(target, script)
            else:
                target = self.target_from_container(
                    "textassets",
                    container_paths,
                    container_choice,
                    suffix or ".bin",
                )
                target = self.claim_target(target, obj.path_id)
                self.export_bytes(target, bytes_from_value(script))
            self.export_troop_textasset(obj, script, container_paths, container_choice)
            return "textassets", target

        if object_type == "Font":
            font_data = bytes_from_value(getattr(data, "m_FontData", b""))
            if not font_data:
                return None, None
            target = self.target_from_container(
                "fonts",
                container_paths,
                object_name,
                guess_font_extension(font_data),
            )
            target = self.claim_target(target, obj.path_id)
            self.export_bytes(target, font_data)
            return "fonts", target

        if object_type == "Mesh":
            exported = data.export()
            if not exported:
                return None, None
            target = self.target_from_container(
                "meshes", container_paths, object_name, ".obj"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_text(target, exported)
            return "meshes", target

        if object_type == "Shader":
            exported = data.export()
            if not exported:
                return None, None
            target = self.target_from_container(
                "shaders", container_paths, object_name or "shader", ".txt"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_text(target, exported)
            return "shaders", target

        if object_type == "Material":
            payload = {
                "name": getattr(data, "m_Name", None),
                "shader": repr(getattr(data, "m_Shader", None)),
                "saved_properties": jsonable(getattr(data, "m_SavedProperties", None)),
                "shader_keywords": getattr(data, "m_ShaderKeywords", None),
                "valid_keywords": jsonable(getattr(data, "m_ValidKeywords", None)),
                "invalid_keywords": jsonable(getattr(data, "m_InvalidKeywords", None)),
            }
            target = self.target_from_container(
                "materials", container_paths, object_name, ".json"
            )
            target = self.claim_target(target, obj.path_id)
            write_json(target, payload)
            return "materials", target

        if object_type == "SpriteAtlas":
            self.export_troop_atlas(obj, object_name)
            return None, None

        return None, None

    def export_source(self, label: str, path: Path) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "label": label,
            "path": str(path),
            "exported": {},
            "object_types": {},
            "error_count": 0,
            "bundle_name": None,
            "container_count": 0,
            "object_count": 0,
        }

        env = self.UnityPy.load(str(path))
        container_index = self.build_container_index(env)
        summary["container_count"] = len(env.container)
        summary["object_count"] = len(env.objects)

        exported = Counter()
        object_types = Counter(obj.type.name for obj in env.objects)
        summary["object_types"] = dict(object_types)
        self.global_types.update(object_types)
        error_start = len(self.errors)

        for obj in env.objects:
            if obj.type.name == "AssetBundle" and summary["bundle_name"] is None:
                try:
                    summary["bundle_name"] = getattr(obj.read(), "m_Name", None)
                except Exception:
                    summary["bundle_name"] = None
                continue

            try:
                bucket, written_path = self.export_object(obj, container_index)
            except Exception as exc:
                self.errors.append(
                    {
                        "source": label,
                        "path": str(path),
                        "object_type": obj.type.name,
                        "path_id": obj.path_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            if bucket is None or written_path is None:
                continue
            exported[bucket] += 1
            self.global_exports[bucket] += 1

        summary["exported"] = dict(exported)
        summary["error_count"] = len(self.errors) - error_start
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--venv-root", type=Path, default=DEFAULT_VENV_ROOT)
    parser.add_argument("--apk-path", type=Path, default=DEFAULT_APK_PATH)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--catalog-path", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--limit-sources", type=int, default=None)
    parser.add_argument("--keep-output", action="store_true")
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

    if args.output_root.exists() and not args.keep_output:
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(args.apk_path, args.cache_root)
    if args.limit_sources is not None:
        sources = sources[: args.limit_sources]

    exporter = Exporter(args.output_root, UnityPy)
    source_summaries = []

    for label, path in sources:
        print(f"[extract] {label}: {path}")
        source_summaries.append(exporter.export_source(label, path))

    catalog_summary = summarize_catalog(args.catalog_path)
    manifest = {
        "package_root": str(args.package_root),
        "output_root": str(args.output_root),
        "unitypy_version": getattr(UnityPy, "__version__", None),
        "source_count": len(source_summaries),
        "sources": source_summaries,
        "global_exports": dict(exporter.global_exports),
        "troop_exports": dict(exporter.troop_exports),
        "global_object_types": dict(exporter.global_types),
        "catalog_summary": catalog_summary,
        "notes": [
            "This dump is local-first: it includes base.apk content and cached UnityFS bundles present on disk.",
            "Remote Addressables bundles advertised by the catalog were not anonymously downloadable from the captured install and likely require authenticated cookies or API-mediated access.",
            "User save/config files were intentionally not exported into the public dump.",
            "Troop-focused exports preserve Unity sprite crops, source textures, and SpriteAtlas metadata under assets/troops without exporting animation clips.",
            "Standalone Texture2D PNG exports are intentionally omitted to reduce duplication with Sprite PNG exports; troop atlas pages remain under assets/troops/atlas_pages.",
        ],
        "errors": exporter.errors,
    }
    write_json(args.output_root / "reports" / "summary.json", manifest)
    write_json(
        args.output_root / "reports" / "errors.json", {"errors": exporter.errors}
    )
    (args.output_root / "README.md").write_text(
        render_readme(manifest), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "sources": len(source_summaries),
                "exports": dict(exporter.global_exports),
                "troop_exports": dict(exporter.troop_exports),
                "errors": len(exporter.errors),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
