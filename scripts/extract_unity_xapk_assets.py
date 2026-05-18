#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VENV_ROOT = ROOT / ".venv-krb"

TEXT_EXTENSIONS = {
    "",
    ".asset",
    ".bytes",
    ".cfg",
    ".csv",
    ".fnt",
    ".htm",
    ".html",
    ".ini",
    ".json",
    ".lua",
    ".md",
    ".properties",
    ".shader",
    ".strings",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga"}
TEXTURE_EXTENSIONS = {".ktx", ".ktx2", ".pvr", ".astc", ".dds"}
AUDIO_EXTENSIONS = {
    ".aac",
    ".acb",
    ".aif",
    ".aiff",
    ".awb",
    ".bank",
    ".bnk",
    ".fsb",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".wem",
}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".ogv", ".webm"}
FONT_EXTENSIONS = {".otf", ".ttc", ".ttf", ".woff", ".woff2"}
MODEL_EXTENSIONS = {".fbx", ".glb", ".gltf", ".obj"}

SKIP_RAW_SUFFIXES = {
    ".apk",
    ".arsc",
    ".dex",
    ".ec",
    ".mf",
    ".prof",
    ".profm",
    ".rsa",
    ".sf",
    ".so",
}
SKIP_RAW_TOP_LEVELS = {"META-INF", "lib"}

GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]+")
REDACTED_GOOGLE_API_KEY = "[REDACTED_GOOGLE_API_KEY]"
PRINTABLE_ASCII_RE = re.compile(rb"[ -~]{6,}")

GENERIC_PATH_PARTS = {
    "android",
    "asset",
    "assets",
    "audio",
    "common",
    "content",
    "data",
    "font",
    "fonts",
    "image",
    "images",
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
    "sprite",
    "sprites",
    "text",
    "texture",
    "textures",
    "unity",
}

BUCKET_PARENT_DEPTH = {
    "animations": 1,
    "animators": 1,
    "atlas_metadata": 1,
    "audio": 1,
    "avatars": 1,
    "cubemaps": 1,
    "fonts": 1,
    "materials": 1,
    "meshes": 1,
    "monobehaviours": 1,
    "prefabs": 1,
    "shaders": 1,
    "sprites": 1,
    "textassets": 1,
    "texture_placeholders": 1,
    "textures": 1,
    "typetrees": 1,
}

OUTPUT_BUCKET_DIRS = {
    "animations": "metadata/animations",
    "animators": "metadata/animators",
    "atlas_metadata": "metadata/atlases",
    "audio": "audio",
    "avatars": "metadata/avatars",
    "cubemaps": "metadata/cubemaps",
    "fonts": "fonts",
    "materials": "materials",
    "meshes": "models",
    "monobehaviours": "metadata/monobehaviours",
    "prefabs": "metadata/prefabs",
    "shaders": "shaders",
    "sprites": "sprites",
    "textassets": "text",
    "texture_placeholders": "metadata/texture_placeholders",
    "textures": "textures",
    "typetrees": "metadata/typetrees",
}

CONTAINER_INDEXED_TYPETREE_BUCKETS = {
    "GameObject": "prefabs",
    "MonoBehaviour": "monobehaviours",
}

GLOBAL_TYPETREE_BUCKETS = {
    "AnimationClip": "animations",
    "AnimatorController": "animators",
    "AnimatorOverrideController": "animators",
    "Avatar": "avatars",
    "AvatarMask": "avatars",
    "ComputeShader": "shaders",
    "Cubemap": "cubemaps",
    "LightingSettings": "typetrees",
    "RenderTexture": "typetrees",
    "ShaderVariantCollection": "shaders",
    "SpriteAtlas": "atlas_metadata",
}


def add_site_packages(venv_root: Path) -> None:
    for path in sorted(venv_root.glob("lib/python*/site-packages")):
        sys.path.insert(0, str(path))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
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


def sanitize_rel_path(path_str: str | Path) -> Path:
    parts = [
        sanitize_part(part)
        for part in str(path_str).replace("\\", "/").split("/")
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


def swap_extension(path: Path, suffix: str) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    if path.suffix:
        return path.with_suffix(suffix)
    return path.with_name(path.name + suffix)


def looks_like_hash_or_number(value: str) -> bool:
    normalized = value.strip().replace("-", "").replace("_", "")
    if len(normalized) < 8:
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]+", normalized) or normalized.isdigit())


def choose_container_path(paths: list[str], fallback_name: str) -> str:
    for candidate in paths:
        stem = Path(candidate).stem
        if looks_like_hash_or_number(stem):
            continue
        if Path(candidate).suffix.lower() in {
            ".anim",
            ".asset",
            ".controller",
            ".mat",
            ".prefab",
        }:
            return candidate
        return candidate
    return fallback_name


def build_shallow_logical_path(
    path_str: str,
    suffix: str,
    parent_depth: int = 1,
) -> Path:
    logical_path = sanitize_rel_path(path_str)
    logical_path = swap_extension(logical_path, suffix)
    if len(logical_path.parts) == 1:
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
        name_group = derive_name_group(filename)
        if name_group is not None:
            return Path(name_group) / filename
        return Path(filename)
    return Path(*parents[-max(parent_depth, 1) :]) / filename


def flatten_rel_filename(path_str: str | Path, prefix: str | None = None) -> str:
    parts = sanitize_rel_path(path_str).parts
    flattened = "__".join(parts) if parts else "unnamed"
    if prefix:
        flattened = f"{sanitize_part(prefix)}__{flattened}"
    return sanitize_part(flattened)


def build_flat_logical_filename(
    path_str: str,
    suffix: str,
    parent_depth: int = 1,
    prefix: str | None = None,
) -> str:
    logical_path = build_shallow_logical_path(path_str, suffix, parent_depth)
    return flatten_rel_filename(logical_path, prefix)


def output_bucket_root(output_root: Path, bucket: str) -> Path:
    return output_root / sanitize_rel_path(OUTPUT_BUCKET_DIRS.get(bucket, bucket))


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


def decode_text(data: bytes) -> str | None:
    if b"\x00" in data[:4096]:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return repr(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes_from_value(value)
        text = decode_text(raw)
        if text is not None and len(text) <= 4096:
            return redact_public_text(text)
        return {"byte_length": len(raw)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        if len(value) > 256:
            return {
                "item_count": len(value),
                "preview": [jsonable(item, depth + 1) for item in list(value)[:16]],
            }
        return [jsonable(item, depth + 1) for item in value]
    path_id = getattr(value, "path_id", None) or getattr(value, "m_PathID", None)
    file_id = getattr(value, "file_id", None) or getattr(value, "m_FileID", None)
    if path_id is not None or file_id is not None:
        return {"file_id": file_id, "path_id": path_id}
    if hasattr(value, "__dict__"):
        result = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            result[key] = jsonable(item, depth + 1)
        if result:
            return result
    return repr(value)


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


def safe_zip_target(output_root: Path, member_name: str) -> Path:
    pure = PurePosixPath(member_name)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe zip member path: {member_name}")
    return output_root / sanitize_rel_path(member_name)


def extract_zip(zip_path: Path, output_root: Path) -> int:
    count = 0
    with ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            target = safe_zip_target(output_root, info.filename)
            ensure_parent(target)
            target.write_bytes(archive.read(info))
            count += 1
    return count


def copy_original_package(xapk_path: Path, package_root: Path) -> Path:
    target = package_root / "inputs" / "packages" / xapk_path.name
    ensure_parent(target)
    if not target.exists() or target.stat().st_size != xapk_path.stat().st_size:
        shutil.copy2(xapk_path, target)
    return target


def prepare_inputs(
    xapk_path: Path, package_root: Path, keep_extracted: bool
) -> dict[str, Any]:
    copied_package = copy_original_package(xapk_path, package_root)
    extracted_root = package_root / "work" / "extracted"
    xapk_root = extracted_root / "xapk"
    apks_root = extracted_root / "apks"
    if extracted_root.exists() and not keep_extracted:
        shutil.rmtree(extracted_root)
    xapk_root.mkdir(parents=True, exist_ok=True)
    apks_root.mkdir(parents=True, exist_ok=True)

    if copied_package.suffix.lower() == ".apk":
        manifest = {
            "name": copied_package.stem,
            "package_name": None,
            "version_name": None,
            "version_code": None,
            "source_format": "apk",
        }
        target_apk = xapk_root / copied_package.name
        if (
            not target_apk.exists()
            or target_apk.stat().st_size != copied_package.stat().st_size
        ):
            shutil.copy2(copied_package, target_apk)
        xapk_entry_count = 1
    else:
        with ZipFile(copied_package) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        xapk_entry_count = extract_zip(copied_package, xapk_root)
    apk_summaries = []
    for apk_path in sorted(xapk_root.glob("*.apk")):
        target_dir = apks_root / apk_path.stem
        if target_dir.exists() and not keep_extracted:
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_count = extract_zip(apk_path, target_dir)
        apk_summaries.append(
            {
                "apk": str(apk_path.relative_to(package_root)),
                "extracted_to": str(target_dir.relative_to(package_root)),
                "file_count": file_count,
                "size": apk_path.stat().st_size,
            }
        )

    write_json(package_root / "inputs" / "packages" / "manifest.json", manifest)
    return {
        "copied_package": str(copied_package),
        "xapk_root": xapk_root,
        "apks_root": apks_root,
        "xapk_entry_count": xapk_entry_count,
        "apks": apk_summaries,
        "xapk_manifest": manifest,
    }


def discover_unity_sources(xapk_root: Path) -> list[tuple[str, Path]]:
    sources = []
    for apk_path in sorted(xapk_root.glob("*.apk")):
        sources.append((f"apk_{slugify(apk_path.stem)}", apk_path))
    return sources


def source_slug(label: str) -> str:
    return slugify(label.removeprefix("apk_"))


def ptr_assets_file_name(pointer: Any) -> str | None:
    assets_file = (
        getattr(pointer, "assets_file", None)
        or getattr(pointer, "assetsfile", None)
        or getattr(getattr(pointer, "asset", None), "assets_file", None)
        or getattr(getattr(pointer, "asset", None), "assetsfile", None)
    )
    return getattr(assets_file, "name", None)


def ptr_path_id(pointer: Any) -> int | None:
    return (
        getattr(pointer, "path_id", None)
        or getattr(pointer, "m_PathID", None)
        or getattr(getattr(pointer, "asset", None), "path_id", None)
        or getattr(getattr(pointer, "asset", None), "m_PathID", None)
    )


class Exporter:
    def __init__(self, output_root: Path, unitypy_module: Any) -> None:
        self.output_root = output_root
        self.UnityPy = unitypy_module
        self.errors: list[dict[str, Any]] = []
        self.global_exports = Counter()
        self.global_recovered = Counter()
        self.global_types = Counter()
        self.path_index: list[dict[str, Any]] = []

    def claim_target(self, target: Path, path_id: int) -> Path:
        if not target.exists():
            return target
        candidate = target.with_name(f"{target.stem}__{path_id}{target.suffix}")
        if not candidate.exists():
            return candidate
        counter = 2
        while True:
            numbered = target.with_name(
                f"{target.stem}__{path_id}__{counter}{target.suffix}"
            )
            if not numbered.exists():
                return numbered
            counter += 1

    def build_container_index(self, env: Any) -> dict[tuple[str, int], list[str]]:
        index: dict[tuple[str, int], list[str]] = defaultdict(list)
        for container_path, pointer in env.container.items():
            path_id = ptr_path_id(pointer)
            assets_name = ptr_assets_file_name(pointer)
            if path_id is None or assets_name is None:
                continue
            index[(assets_name, path_id)].append(str(container_path))
        return index

    def object_container_paths(
        self, obj: Any, container_index: dict[tuple[str, int], list[str]]
    ) -> list[str]:
        return container_index.get((obj.assets_file.name, obj.path_id), [])

    def target_from_container(
        self,
        label: str,
        bucket: str,
        container_paths: list[str],
        fallback_name: str,
        suffix: str,
    ) -> Path:
        filename = build_flat_logical_filename(
            choose_container_path(container_paths, fallback_name),
            suffix,
            BUCKET_PARENT_DEPTH.get(bucket, 1),
            prefix=source_slug(label),
        )
        return output_bucket_root(self.output_root, bucket) / filename

    def record_export(
        self,
        label: str,
        bucket: str,
        target: Path,
        obj: Any,
        container_paths: list[str],
    ) -> None:
        try:
            object_name = obj.peek_name()
        except Exception:
            object_name = None
        self.path_index.append(
            {
                "path": str(target.relative_to(self.output_root)),
                "category": "unity",
                "bucket": bucket,
                "source": source_slug(label),
                "source_label": label,
                "object_type": obj.type.name,
                "name": object_name,
                "asset_file": getattr(obj.assets_file, "name", None),
                "path_id": obj.path_id,
                "container_paths": container_paths,
            }
        )

    def export_bytes(self, target: Path, data: bytes) -> None:
        ensure_parent(target)
        target.write_bytes(data)

    def export_text(self, target: Path, text: str) -> None:
        ensure_parent(target)
        target.write_text(
            redact_public_text(text), encoding="utf-8", errors="surrogatepass"
        )

    def export_script_value(self, target: Path, value: Any) -> None:
        if isinstance(value, str):
            self.export_text(target, value)
            return
        raw = bytes_from_value(value)
        text = decode_text(raw)
        if text is not None and target.suffix.lower() in TEXT_EXTENSIONS:
            self.export_text(target, text)
        else:
            self.export_bytes(target, raw)

    def export_material(self, target: Path, data: Any) -> None:
        payload = {
            "name": getattr(data, "m_Name", None),
            "shader": jsonable(getattr(data, "m_Shader", None)),
            "saved_properties": jsonable(getattr(data, "m_SavedProperties", None)),
            "shader_keywords": getattr(data, "m_ShaderKeywords", None),
            "valid_keywords": jsonable(getattr(data, "m_ValidKeywords", None)),
            "invalid_keywords": jsonable(getattr(data, "m_InvalidKeywords", None)),
        }
        write_json(target, payload)

    def export_typetree(
        self,
        obj: Any,
        target: Path,
        object_type: str,
        object_name: str,
        container_paths: list[str],
    ) -> None:
        try:
            tree = obj.read_typetree()
        except Exception:
            tree = None
        payload = {
            "object_type": object_type,
            "name": object_name,
            "path_id": obj.path_id,
            "asset_file": obj.assets_file.name,
            "container_paths": container_paths,
            "typetree": jsonable(tree),
        }
        write_json(target, payload)

    def export_texture_placeholder(
        self,
        obj: Any,
        target: Path,
        object_name: str,
        container_paths: list[str],
        data: Any,
    ) -> None:
        try:
            tree = obj.read_typetree()
        except Exception:
            tree = None
        payload = {
            "object_type": "Texture2D",
            "name": object_name,
            "path_id": obj.path_id,
            "asset_file": obj.assets_file.name,
            "container_paths": container_paths,
            "placeholder_reason": "zero_dimension_texture",
            "width": getattr(data, "m_Width", None),
            "height": getattr(data, "m_Height", None),
            "texture_format": str(getattr(data, "m_TextureFormat", None)),
            "stream_data": jsonable(getattr(data, "m_StreamData", None)),
            "typetree": jsonable(tree),
        }
        write_json(target, payload)

    def decode_rg_float_texture(self, data: Any) -> Any:
        texture_format = int(getattr(data, "m_TextureFormat", 0))
        width = int(getattr(data, "m_Width", 0) or 0)
        height = int(getattr(data, "m_Height", 0) or 0)
        raw = bytes_from_value(data.get_image_data())
        if texture_format == 16:
            pair_format = "<ee"
            bytes_per_pixel = 4
        elif texture_format == 19:
            pair_format = "<ff"
            bytes_per_pixel = 8
        else:
            raise ValueError(f"unsupported RG float texture format: {texture_format}")
        expected_size = width * height * bytes_per_pixel
        if not width or not height:
            raise ValueError("cannot decode zero-dimension RG float texture")
        if len(raw) < expected_size:
            raise ValueError(
                f"RG float texture data too small: {len(raw)} < {expected_size}"
            )

        from PIL import Image

        def channel_byte(value: float) -> int:
            if value <= 0:
                return 0
            if value >= 1:
                return 255
            return int(value * 255 + 0.5)

        pixels = bytearray(width * height * 4)
        for index, (red, green) in enumerate(
            struct.iter_unpack(pair_format, raw[:expected_size])
        ):
            offset = index * 4
            pixels[offset] = channel_byte(float(red))
            pixels[offset + 1] = channel_byte(float(green))
            pixels[offset + 2] = 0
            pixels[offset + 3] = 255
        image = Image.frombytes("RGBA", (width, height), bytes(pixels), "raw", "RGBA")
        return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    def save_texture_image(self, data: Any, target: Path) -> None:
        try:
            data.image.save(target)
            return
        except KeyError as exc:
            texture_format = int(getattr(data, "m_TextureFormat", 0))
            if exc.args != ("raw",) or texture_format not in {16, 19}:
                raise
        # UnityPy's RG float path currently asks Pillow for a raw RG/RGF mode it
        # does not support. Preserve the channels in an RGBA preview instead.
        self.decode_rg_float_texture(data).save(target)

    def object_identity_name(
        self,
        object_type: str,
        object_name: str | None,
        asset_file_name: str,
        path_id: int,
    ) -> str:
        name = object_name or object_type.lower()
        if name == object_type.lower():
            name = f"{object_type}_{asset_file_name}_{path_id}"
        return sanitize_part(name)

    def recovery_base_target(
        self,
        label: str,
        bucket: str,
        object_type: str,
        object_name: str | None,
        asset_file_name: str,
        path_id: int,
        container_paths: list[str],
    ) -> Path:
        fallback = self.object_identity_name(
            object_type, object_name, asset_file_name, path_id
        )
        logical_path = build_shallow_logical_path(
            choose_container_path(container_paths, fallback),
            ".recovered",
            BUCKET_PARENT_DEPTH.get(bucket, 1),
        )
        if logical_path.name == "recovered":
            logical_path = logical_path.with_name(f"{fallback}.recovered")
        stem = logical_path.with_suffix("")
        flat_stem = flatten_rel_filename(stem, prefix=source_slug(label))
        unique = sanitize_part(f"{asset_file_name}_{path_id}")
        return (
            self.output_root / "recovered" / bucket / f"{flat_stem}__{unique}.recovered"
        )

    def write_strings_from_chunks(self, target: Path, chunks: list[bytes]) -> int:
        ensure_parent(target)
        seen: set[str] = set()
        count = 0
        with target.open("w", encoding="utf-8", errors="surrogatepass") as handle:
            for chunk in chunks:
                for match in PRINTABLE_ASCII_RE.finditer(chunk):
                    text = redact_public_text(match.group(0).decode("ascii", "ignore"))
                    if text in seen:
                        continue
                    seen.add(text)
                    handle.write(text)
                    handle.write("\n")
                    count += 1
        return count

    def export_raw_failure_common(
        self,
        obj: Any,
        base_target: Path,
        object_type: str,
        object_name: str | None,
        container_paths: list[str],
        original_error: Exception,
        write_raw: bool = True,
    ) -> dict[str, Any]:
        raw_target = base_target.with_suffix(".raw.bin")
        typetree_target = base_target.with_suffix(".typetree.json")
        raw = obj.get_raw_data()
        self.export_typetree(
            obj,
            typetree_target,
            object_type,
            object_name or object_type.lower(),
            container_paths,
        )
        strings_target = base_target.with_suffix(".strings.txt")
        string_count = self.write_strings_from_chunks(strings_target, [raw])
        payload = {
            "typetree": str(typetree_target.relative_to(self.output_root)),
            "strings": str(strings_target.relative_to(self.output_root)),
            "string_count": string_count,
            "raw_size": len(raw),
            "original_error": f"{type(original_error).__name__}: {original_error}",
        }
        if write_raw:
            self.export_bytes(raw_target, raw)
            payload["raw"] = str(raw_target.relative_to(self.output_root))
        else:
            payload["raw_omitted"] = True
            payload["raw_omission_reason"] = (
                "shader binary payload omitted from public dump"
            )
        return payload

    def nested_shader_entries(
        self,
        data: Any,
    ) -> list[tuple[int, int, int, int, int, int]]:
        platforms = list(getattr(data, "platforms", []) or [])
        offsets = list(getattr(data, "offsets", []) or [])
        compressed_lengths = list(getattr(data, "compressedLengths", []) or [])
        decompressed_lengths = list(getattr(data, "decompressedLengths", []) or [])
        entries = []
        for platform_index, platform in enumerate(platforms):
            platform_offsets = (
                offsets[platform_index] if platform_index < len(offsets) else []
            )
            platform_compressed = (
                compressed_lengths[platform_index]
                if platform_index < len(compressed_lengths)
                else []
            )
            platform_decompressed = (
                decompressed_lengths[platform_index]
                if platform_index < len(decompressed_lengths)
                else []
            )
            if not isinstance(platform_offsets, list):
                platform_offsets = [platform_offsets]
            if not isinstance(platform_compressed, list):
                platform_compressed = [platform_compressed]
            if not isinstance(platform_decompressed, list):
                platform_decompressed = [platform_decompressed]
            for chunk_index, (offset, compressed_size, decompressed_size) in enumerate(
                zip(platform_offsets, platform_compressed, platform_decompressed)
            ):
                entries.append(
                    (
                        platform_index,
                        int(platform),
                        chunk_index,
                        int(offset),
                        int(compressed_size),
                        int(decompressed_size),
                    )
                )
        return entries

    def shader_platform_label(self, platform: int) -> str:
        try:
            from UnityPy.enums import ShaderCompilerPlatform  # type: ignore[import-not-found]
            from UnityPy.export.ShaderConverter import GetPlatformString  # type: ignore[import-not-found]

            return sanitize_part(GetPlatformString(ShaderCompilerPlatform(platform)))
        except Exception:
            return f"platform_{platform}"

    def parse_shader_program_text(
        self,
        obj: Any,
        decompressed: bytes,
    ) -> tuple[str | None, int | None, str | None, int]:
        from UnityPy.export.ShaderConverter import ShaderProgram  # type: ignore[import-not-found]
        from UnityPy.streams import EndianBinaryReader  # type: ignore[import-not-found]

        last_error = None
        for padding in (0, 4, 8, 16, 64, 256):
            try:
                program = ShaderProgram(
                    EndianBinaryReader(decompressed + (b"\0" * padding), endian="<"),
                    obj.version,
                )
                lines = []
                parsed_count = 0
                for index, subprogram in enumerate(program.m_SubPrograms):
                    if subprogram is None:
                        continue
                    try:
                        exported = subprogram.Export()
                    except Exception as exc:
                        exported = f"// subprogram {index} export failed: {type(exc).__name__}: {exc}"
                    lines.append(f"// SubProgram {index}\n{exported}\n")
                    parsed_count += 1
                return "\n".join(lines), padding, None, parsed_count
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        return None, None, last_error, 0

    def recover_shader_failure(
        self,
        obj: Any,
        data: Any,
        base_target: Path,
        common: dict[str, Any],
    ) -> dict[str, Any]:
        from UnityPy.helpers import CompressionHelper  # type: ignore[import-not-found]

        blob = bytes_from_value(getattr(data, "compressedBlob", b"") or b"")
        entries = self.nested_shader_entries(data)
        chunk_root = base_target.parent / f"{base_target.name}_chunks"
        chunks_for_strings = []
        chunk_reports = []
        decompressed_total = 0
        program_text_count = 0

        for (
            platform_index,
            platform,
            chunk_index,
            offset,
            compressed_size,
            decompressed_size,
        ) in entries:
            compressed = blob[offset : offset + compressed_size]
            platform_label = self.shader_platform_label(platform)
            chunk_name = (
                f"platform{platform_index}_{platform_label}_chunk{chunk_index:04d}"
            )
            chunk_report = {
                "platform_index": platform_index,
                "platform": platform,
                "platform_label": platform_label,
                "chunk_index": chunk_index,
                "offset": offset,
                "compressed_size": compressed_size,
                "decompressed_size": decompressed_size,
                "actual_compressed_size": len(compressed),
            }
            try:
                decompressed = CompressionHelper.decompress_lz4(
                    compressed, decompressed_size
                )
            except Exception as exc:
                chunk_report.update(
                    {
                        "decompress_error": f"{type(exc).__name__}: {exc}",
                        "compressed_binary_omitted": True,
                    }
                )
                chunk_reports.append(chunk_report)
                continue

            chunks_for_strings.append(decompressed)
            decompressed_total += len(decompressed)
            chunk_report["decompressed_binary_omitted"] = True
            chunk_report["actual_decompressed_size"] = len(decompressed)

            program_text, padding, parse_error, parsed_count = (
                self.parse_shader_program_text(obj, decompressed)
            )
            if program_text is not None:
                program_target = chunk_root / f"{chunk_name}.programs.txt"
                self.export_text(program_target, program_text)
                chunk_report.update(
                    {
                        "program_text": str(
                            program_target.relative_to(self.output_root)
                        ),
                        "program_parser_padding_bytes": padding,
                        "parsed_subprogram_count": parsed_count,
                    }
                )
                program_text_count += 1
            else:
                chunk_report["program_parse_error"] = parse_error
            chunk_reports.append(chunk_report)

        decoded_strings_target = base_target.with_suffix(".decoded-strings.txt")
        decoded_string_count = self.write_strings_from_chunks(
            decoded_strings_target, chunks_for_strings
        )
        shader_report_target = base_target.with_suffix(".shader-recovery.json")
        write_json(
            shader_report_target,
            {
                **common,
                "shader_binary_omitted": True,
                "shader_binary_omission_reason": "raw and decompressed compiled shader binaries are intentionally omitted from the public dump",
                "compressed_blob_size": len(blob),
                "chunk_count": len(entries),
                "decompressed_total_size": decompressed_total,
                "decoded_strings": str(
                    decoded_strings_target.relative_to(self.output_root)
                ),
                "decoded_string_count": decoded_string_count,
                "program_text_chunk_count": program_text_count,
                "chunks": chunk_reports,
            },
        )
        return {
            **common,
            "shader_recovery": str(shader_report_target.relative_to(self.output_root)),
            "decoded_strings": str(
                decoded_strings_target.relative_to(self.output_root)
            ),
            "shader_binary_omitted": True,
            "chunk_count": len(entries),
            "decompressed_total_size": decompressed_total,
            "program_text_chunk_count": program_text_count,
        }

    def recover_texture_failure(
        self,
        data: Any | None,
        base_target: Path,
        common: dict[str, Any],
    ) -> dict[str, Any]:
        image_data = (
            bytes_from_value(getattr(data, "image_data", b"") or b"") if data else b""
        )
        stream_data = getattr(data, "m_StreamData", None) if data else None
        image_target = None
        if image_data:
            image_target_path = base_target.with_suffix(".image-data.bin")
            self.export_bytes(image_target_path, image_data)
            image_target = str(image_target_path.relative_to(self.output_root))
        metadata_target = base_target.with_suffix(".texture-recovery.json")
        payload = {
            **common,
            "name": getattr(data, "m_Name", None) if data else None,
            "width": getattr(data, "m_Width", None) if data else None,
            "height": getattr(data, "m_Height", None) if data else None,
            "texture_format": str(getattr(data, "m_TextureFormat", None))
            if data
            else None,
            "image_data_size": len(image_data),
            "image_data": image_target,
            "stream_data": jsonable(stream_data),
        }
        write_json(metadata_target, payload)
        return {
            **common,
            "texture_recovery": str(metadata_target.relative_to(self.output_root)),
            "image_data_size": len(image_data),
            "zero_dimension_placeholder": bool(
                data
                and getattr(data, "m_Width", 0) == 0
                and getattr(data, "m_Height", 0) == 0
            ),
        }

    def recover_failed_object(
        self,
        label: str,
        obj: Any,
        container_index: dict[tuple[str, int], list[str]],
        original_error: Exception,
    ) -> dict[str, Any]:
        object_type = obj.type.name
        container_paths = self.object_container_paths(obj, container_index)
        data = None
        object_name = None
        try:
            data = obj.read()
            object_name = getattr(data, "m_Name", None)
        except Exception:
            try:
                object_name = obj.peek_name()
            except Exception:
                object_name = None

        asset_file_name = sanitize_part(getattr(obj.assets_file, "name", "unknown"))
        bucket = object_type.lower()
        base_target = self.recovery_base_target(
            label,
            bucket,
            object_type,
            object_name,
            asset_file_name,
            obj.path_id,
            container_paths,
        )
        base_target = self.claim_target(base_target, obj.path_id)
        common = self.export_raw_failure_common(
            obj,
            base_target,
            object_type,
            object_name,
            container_paths,
            original_error,
            write_raw=object_type != "Shader",
        )

        if object_type == "Shader" and data is not None:
            return {
                "bucket": bucket,
                **self.recover_shader_failure(obj, data, base_target, common),
            }
        if object_type in {"Texture2D", "Sprite"}:
            return {
                "bucket": bucket,
                **self.recover_texture_failure(data, base_target, common),
            }
        recovery_target = base_target.with_suffix(".recovery.json")
        write_json(recovery_target, common)
        return {
            "bucket": bucket,
            **common,
            "recovery": str(recovery_target.relative_to(self.output_root)),
        }

    def export_object(
        self,
        label: str,
        obj: Any,
        container_index: dict[tuple[str, int], list[str]],
    ) -> tuple[str | None, Path | None]:
        object_type = obj.type.name
        container_paths = self.object_container_paths(obj, container_index)

        if object_type in CONTAINER_INDEXED_TYPETREE_BUCKETS and not container_paths:
            return None, None

        supported_types = {
            "AudioClip",
            "Font",
            "Material",
            "Mesh",
            "Shader",
            "Sprite",
            "TextAsset",
            "Texture2D",
            *CONTAINER_INDEXED_TYPETREE_BUCKETS,
            *GLOBAL_TYPETREE_BUCKETS,
        }
        if object_type not in supported_types:
            return None, None

        data = obj.read()
        object_name = (
            getattr(data, "m_Name", None) or obj.peek_name() or object_type.lower()
        )

        if object_type == "Sprite":
            target = self.target_from_container(
                label, "sprites", container_paths, object_name, ".png"
            )
            target = self.claim_target(target, obj.path_id)
            ensure_parent(target)
            self.save_texture_image(data, target)
            return "sprites", target

        if object_type == "Texture2D":
            if not getattr(data, "m_Width", 0) or not getattr(data, "m_Height", 0):
                target = self.target_from_container(
                    label,
                    "texture_placeholders",
                    container_paths,
                    object_name,
                    ".json",
                )
                target = self.claim_target(target, obj.path_id)
                self.export_texture_placeholder(
                    obj, target, object_name, container_paths, data
                )
                return "texture_placeholders", target
            target = self.target_from_container(
                label, "textures", container_paths, object_name, ".png"
            )
            target = self.claim_target(target, obj.path_id)
            ensure_parent(target)
            self.save_texture_image(data, target)
            return "textures", target

        if object_type == "AudioClip":
            samples = getattr(data, "samples", {}) or {}
            if not samples:
                return None, None
            last_target = None
            for sample_name, sample_bytes in samples.items():
                suffix = Path(sample_name).suffix or ".bin"
                fallback = sample_name or object_name
                target = self.target_from_container(
                    label, "audio", container_paths, fallback, suffix
                )
                target = self.claim_target(target, obj.path_id)
                self.export_bytes(target, bytes_from_value(sample_bytes))
                last_target = target
            return "audio", last_target

        if object_type == "TextAsset":
            script = getattr(data, "m_Script", None)
            if script is None:
                script = getattr(data, "script", None)
            if script is None:
                return None, None
            container_choice = choose_container_path(container_paths, object_name)
            suffix = Path(container_choice).suffix.lower()
            if suffix not in TEXT_EXTENSIONS:
                suffix = ".txt" if isinstance(script, str) else ".bin"
            target = self.target_from_container(
                label, "textassets", container_paths, container_choice, suffix or ".txt"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_script_value(target, script)
            return "textassets", target

        if object_type == "Font":
            font_data = bytes_from_value(getattr(data, "m_FontData", b""))
            if not font_data:
                return None, None
            target = self.target_from_container(
                label,
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
                label, "meshes", container_paths, object_name, ".obj"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_text(target, exported)
            return "meshes", target

        if object_type == "Shader":
            exported = data.export()
            if not exported:
                return None, None
            target = self.target_from_container(
                label, "shaders", container_paths, object_name, ".shader"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_text(target, exported)
            return "shaders", target

        if object_type == "Material":
            target = self.target_from_container(
                label, "materials", container_paths, object_name, ".json"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_material(target, data)
            return "materials", target

        bucket = CONTAINER_INDEXED_TYPETREE_BUCKETS.get(
            object_type
        ) or GLOBAL_TYPETREE_BUCKETS.get(object_type)
        if bucket is not None:
            target = self.target_from_container(
                label, bucket, container_paths, object_name, ".json"
            )
            target = self.claim_target(target, obj.path_id)
            self.export_typetree(obj, target, object_type, object_name, container_paths)
            return bucket, target

        return None, None

    def export_source(self, label: str, path: Path) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "label": label,
            "path": str(path),
            "exported": {},
            "object_types": {},
            "error_count": 0,
            "bundle_names": [],
            "container_count": 0,
            "object_count": 0,
        }

        env = self.UnityPy.load(str(path))
        container_index = self.build_container_index(env)
        summary["container_count"] = len(env.container)
        summary["object_count"] = len(env.objects)

        exported = Counter()
        recovered = Counter()
        object_types = Counter(obj.type.name for obj in env.objects)
        summary["object_types"] = dict(object_types)
        self.global_types.update(object_types)
        error_start = len(self.errors)

        for obj in env.objects:
            if obj.type.name == "AssetBundle":
                try:
                    bundle_name = getattr(obj.read(), "m_Name", None)
                except Exception:
                    bundle_name = None
                if bundle_name:
                    summary["bundle_names"].append(bundle_name)
                continue

            try:
                bucket, written_path = self.export_object(label, obj, container_index)
            except Exception as exc:
                recovery: dict[str, Any] | None = None
                try:
                    recovery = self.recover_failed_object(
                        label, obj, container_index, exc
                    )
                    recovery_bucket = recovery.get("bucket")
                    if recovery_bucket:
                        recovered[recovery_bucket] += 1
                        self.global_recovered[recovery_bucket] += 1
                except Exception as recovery_exc:
                    recovery = {
                        "error": f"{type(recovery_exc).__name__}: {recovery_exc}"
                    }
                self.errors.append(
                    {
                        "source": label,
                        "path": str(path),
                        "asset_file": getattr(obj.assets_file, "name", None),
                        "object_type": obj.type.name,
                        "path_id": obj.path_id,
                        "error": f"{type(exc).__name__}: {exc}",
                        "recovery": recovery,
                    }
                )
                continue

            if bucket is None or written_path is None:
                continue
            self.record_export(
                label,
                bucket,
                written_path,
                obj,
                self.object_container_paths(obj, container_index),
            )
            exported[bucket] += 1
            self.global_exports[bucket] += 1

        summary["bundle_names"] = summary["bundle_names"][:200]
        summary["exported"] = dict(exported)
        summary["recovered"] = dict(recovered)
        summary["error_count"] = len(self.errors) - error_start
        return summary


def is_unity_container_path(rel: Path) -> bool:
    parts = tuple(part.lower() for part in rel.parts)
    if len(parts) >= 3 and parts[:3] == ("assets", "bin", "data"):
        return True
    if len(parts) >= 2 and parts[:2] == ("assets", "bundles"):
        return True
    if (
        len(parts) >= 2
        and parts[:2] == ("assets", "assetpack")
        and rel.suffix.lower() == ".bundle"
    ):
        return True
    if (
        len(parts) >= 3
        and parts[:3] == ("assets", "aa", "android")
        and rel.suffix.lower() == ".bundle"
    ):
        return True
    return False


def raw_asset_bucket(rel: Path) -> str | None:
    suffix = rel.suffix.lower()
    lower = "/".join(part.lower() for part in rel.parts)
    if suffix in IMAGE_EXTENSIONS:
        return "images"
    if suffix in TEXTURE_EXTENSIONS:
        return "textures"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in FONT_EXTENSIONS:
        return "fonts"
    if suffix in MODEL_EXTENSIONS:
        return "models"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if "generatedsoundbanks" in lower or "/audio/" in lower:
        return "audio"
    if "/video" in lower or "/videos/" in lower:
        return "video"
    if lower.startswith("assets/configs/"):
        return "configs"
    if lower.startswith("assets/aa/") and (
        suffix in {".bin", ".hash"}
        or rel.name.lower() in {"settings.json", "catalog.bin"}
    ):
        return "configs"
    if lower.startswith("res/raw/"):
        return "raw"
    if suffix == ".bin" and any(
        token in lower for token in {"catalog", "config", "index", "settings"}
    ):
        return "configs"
    return None


def copy_raw_asset(src: Path, target: Path) -> None:
    ensure_parent(target)
    raw = src.read_bytes()
    text = decode_text(raw)
    if text is not None and src.suffix.lower() in TEXT_EXTENSIONS:
        target.write_text(
            redact_public_text(text), encoding="utf-8", errors="surrogatepass"
        )
    else:
        target.write_bytes(raw)


def copy_useful_raw_assets(
    package_root: Path, output_root: Path, apks_root: Path
) -> dict[str, Any]:
    copied = Counter()
    skipped = Counter()
    errors = []
    path_index = []
    for apk_dir in sorted(path for path in apks_root.iterdir() if path.is_dir()):
        apk_slug = slugify(apk_dir.name)
        for src in sorted(path for path in apk_dir.rglob("*") if path.is_file()):
            rel = src.relative_to(apk_dir)
            if rel.parts and rel.parts[0] in SKIP_RAW_TOP_LEVELS:
                skipped["top_level"] += 1
                continue
            if src.suffix.lower() in SKIP_RAW_SUFFIXES:
                skipped["suffix"] += 1
                continue
            if is_unity_container_path(rel):
                skipped["unity_container"] += 1
                continue
            bucket = raw_asset_bucket(rel)
            if bucket is None:
                skipped["not_asset"] += 1
                continue
            target = output_root / "raw" / bucket / flatten_rel_filename(rel, apk_slug)
            try:
                copy_raw_asset(src, target)
            except Exception as exc:
                errors.append(
                    {
                        "source": str(src.relative_to(package_root)),
                        "target": str(target.relative_to(output_root)),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            path_index.append(
                {
                    "path": str(target.relative_to(output_root)),
                    "category": "raw_android",
                    "bucket": bucket,
                    "source_apk": apk_slug,
                    "source": str(src.relative_to(package_root)),
                }
            )
            copied[bucket] += 1
    return {
        "copied": dict(copied),
        "skipped": dict(skipped),
        "errors": errors,
        "path_index": path_index,
    }


def copy_xapk_top_level_assets(
    package_root: Path, output_root: Path, xapk_root: Path
) -> dict[str, Any]:
    copied = Counter()
    path_index = []
    for src in sorted(path for path in xapk_root.iterdir() if path.is_file()):
        if src.suffix.lower() == ".apk":
            continue
        if src.name == "manifest.json":
            target = output_root / "metadata" / "xapk_manifest.json"
            write_json(target, json.loads(src.read_text(encoding="utf-8")))
            copied["metadata"] += 1
            continue
        bucket = raw_asset_bucket(Path(src.name))
        if bucket is None:
            continue
        target = output_root / "raw" / bucket / flatten_rel_filename(src.name, "xapk")
        copy_raw_asset(src, target)
        path_index.append(
            {
                "path": str(target.relative_to(output_root)),
                "category": "raw_xapk",
                "bucket": bucket,
                "source": str(src.relative_to(package_root)),
            }
        )
        copied[bucket] += 1
    return {"copied": dict(copied), "path_index": path_index}


def render_model_previews(
    output_root: Path, args: argparse.Namespace
) -> dict[str, Any]:
    models_root = output_bucket_root(output_root, "meshes")
    previews_root = output_root / "previews" / "models"
    if not models_root.exists():
        return {
            "enabled": True,
            "model_root": str(models_root.relative_to(output_root)),
            "preview_root": str(previews_root.relative_to(output_root)),
            "discovered": 0,
            "rendered": 0,
            "skipped": 0,
            "failures": 0,
        }

    script_root = Path(__file__).resolve().parent
    batch_script = script_root / "render_model_preview_batch.py"
    renderer_script = script_root / "render_model_preview_blender.py"
    if not batch_script.exists() or not renderer_script.exists():
        return {
            "enabled": True,
            "error": "model preview renderer scripts are missing",
            "batch_script": str(batch_script),
            "renderer_script": str(renderer_script),
        }

    command = [
        sys.executable,
        str(batch_script),
        str(models_root),
        str(previews_root),
        "--recursive",
        "--blender",
        args.blender,
        "--renderer-script",
        str(renderer_script),
        "--fps",
        str(args.preview_fps),
        "--resolution-x",
        str(args.preview_resolution),
        "--resolution-y",
        str(args.preview_resolution),
        "--orbit-turns",
        str(args.preview_orbit_turns),
        "--min-frames",
        str(args.preview_min_frames),
    ]
    if args.preview_skip_existing:
        command.append("--skip-existing")
    if args.preview_limit is not None:
        command.extend(["--limit", str(args.preview_limit)])

    print(f"[preview] rendering model videos from {models_root}")
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    report_path = previews_root / "render_report.json"
    summary: dict[str, Any] = {
        "enabled": True,
        "command": command,
        "returncode": result.returncode,
        "output_tail": result.stdout[-4000:],
        "report": str(report_path.relative_to(output_root)),
    }
    if report_path.exists():
        try:
            summary.update(json.loads(report_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            summary["report_parse_error"] = f"{type(exc).__name__}: {exc}"
    else:
        summary["error"] = "preview renderer did not write a report"
    return summary


def build_public_file_index(output_root: Path) -> list[dict[str, Any]]:
    files = []
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        rel = path.relative_to(output_root).as_posix()
        if rel == "reports/path_index.json":
            continue
        top_level = rel.split("/", 1)[0]
        files.append(
            {
                "path": rel,
                "top_level": top_level,
                "size": path.stat().st_size,
            }
        )
    return files


def render_readme(manifest: dict[str, Any]) -> str:
    package = manifest.get("xapk_manifest", {})
    exports = manifest.get("global_exports", {})
    recovered_exports = manifest.get("global_recovered", {})
    raw_exports = manifest.get("raw_assets", {}).get("copied", {})
    previews = manifest.get("model_previews", {}) or {}
    error_count = len((manifest.get("errors") or [])) + len(
        manifest.get("raw_assets", {}).get("errors", [])
    )

    export_lines = []
    for key, label in [
        ("sprites", "Unity sprites"),
        ("textures", "Unity textures"),
        ("audio", "Unity audio samples"),
        ("textassets", "Unity text assets"),
        ("materials", "Unity material JSON files"),
        ("shaders", "Unity shader/metadata files"),
        ("meshes", "Unity mesh OBJ files"),
        ("fonts", "Unity fonts"),
        ("animations", "Unity animation metadata files"),
        ("animators", "Unity animator metadata files"),
        ("atlas_metadata", "Unity sprite atlas metadata files"),
        ("prefabs", "container-indexed prefab metadata files"),
        ("monobehaviours", "container-indexed MonoBehaviour metadata files"),
    ]:
        count = exports.get(key, 0)
        if count:
            export_lines.append(f"- `{count}` {label}")

    raw_lines = []
    for key, count in sorted(raw_exports.items()):
        raw_lines.append(f"- `{count}` raw `{key}` files")

    recovered_lines = []
    for key, count in sorted(recovered_exports.items()):
        recovered_lines.append(f"- `{count}` recovered failed `{key}` objects")

    return "\n".join(
        [
            f"# {package.get('name') or manifest.get('app_slug')} local asset dump",
            "",
            "This dump was extracted from an APKPure XAPK bundle and its nested Android split APKs.",
            "",
            "## Scope",
            "",
            f"- Package: `{package.get('package_name', 'unknown')}`",
            f"- Version: `{package.get('version_name', 'unknown')}`",
            f"- Source XAPK: `{Path(manifest.get('xapk_path', 'unknown')).name}`",
            "- Nested APKs: `work/extracted/xapk/*.apk`",
            "- Decoded Unity exports: flat top-level folders in this dump",
            "",
            "## Browse layout",
            "",
            "- `models/`: flat OBJ mesh exports",
            "- `previews/models/`: MP4 turntable previews for mesh exports",
            "- `sprites/`, `textures/`, `audio/`, `text/`, `materials/`, `fonts/`, `shaders/`: decoded Unity assets",
            "- `metadata/`: animation, animator, atlas, prefab, MonoBehaviour, avatar, cubemap, and typetree JSON",
            "- `raw/`: useful non-Unity Android media/config assets copied from split APKs",
            "- `recovered/`: second-pass exports for objects UnityPy could not normally decode",
            "- `reports/path_index.json`: flat filename index with source paths and categories",
            "",
            "## Decoded Unity assets",
            "",
            *(export_lines or ["- No Unity assets were decoded."]),
            "",
            "## Raw Android assets copied",
            "",
            *(raw_lines or ["- No raw Android media/config assets were copied."]),
            "",
            "## Second-pass failure recovery",
            "",
            *(
                recovered_lines
                or ["- No failed Unity objects needed recovery exports."]
            ),
            "",
            "## Model previews",
            "",
            f"- Discovered models: `{previews.get('discovered', 0)}`",
            f"- Rendered previews: `{previews.get('rendered', 0)}`",
            f"- Skipped existing previews: `{previews.get('skipped', 0)}`",
            f"- Render failures: `{previews.get('failures', 0)}`",
            "- Preview report: `previews/models/render_report.json`",
            "",
            "## Reports",
            "",
            "- `reports/summary.json`: extraction counts, source stats, package metadata, and notes",
            f"- `reports/errors.json`: `{error_count}` remaining decode/copy failures",
            "- `reports/path_index.json`: all public files plus detailed Unity/raw/preview provenance",
            "",
            "## Extraction script",
            "",
            "- Script: `scripts/extract_unity_xapk_assets.py`",
            "- Runtime: `.venv-krb` with UnityPy",
            "",
            "## Notes",
            "",
            "- Native libraries, dex bytecode, signatures, and raw Unity container bundles are intentionally excluded from the public dump.",
            "- Text outputs redact Google API-key-shaped strings before writing.",
            "- Filenames are flattened by joining useful source path segments with `__`; this trades nested folders for longer but easier-to-scan names.",
            "- Container-indexed `GameObject` and `MonoBehaviour` exports preserve useful prefab/config metadata without dumping every scene component.",
            "- Failed Unity objects get a second-pass recovery under `recovered/`, including typetrees, extracted strings, and shader chunk analysis where possible; raw/decompressed shader binaries are omitted from the public dump.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract decoded assets from a Unity Android XAPK bundle."
    )
    parser.add_argument("--xapk", type=Path, required=True)
    parser.add_argument("--app-slug", required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--venv-root", type=Path, default=DEFAULT_VENV_ROOT)
    parser.add_argument("--limit-sources", type=int, default=None)
    parser.add_argument("--keep-output", action="store_true")
    parser.add_argument("--keep-extracted", action="store_true")
    parser.add_argument("--render-model-previews", action="store_true")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--preview-fps", type=int, default=24)
    parser.add_argument("--preview-resolution", type=int, default=512)
    parser.add_argument("--preview-orbit-turns", type=float, default=1.0)
    parser.add_argument("--preview-min-frames", type=int, default=48)
    parser.add_argument("--preview-limit", type=int, default=None)
    parser.add_argument("--preview-skip-existing", action="store_true")
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

    xapk_path = args.xapk.expanduser().resolve()
    if not xapk_path.exists():
        raise SystemExit(f"XAPK does not exist: {xapk_path}")

    package_root = args.package_root or ROOT / "apps" / args.app_slug
    output_root = args.output_root or package_root / "work" / "public"

    if output_root.exists() and not args.keep_output:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    input_summary = prepare_inputs(xapk_path, package_root, args.keep_extracted)
    copy_top_summary = copy_xapk_top_level_assets(
        package_root, output_root, input_summary["xapk_root"]
    )
    raw_summary = copy_useful_raw_assets(
        package_root, output_root, input_summary["apks_root"]
    )
    raw_path_index = []
    raw_path_index.extend(copy_top_summary.pop("path_index", []))
    raw_path_index.extend(raw_summary.pop("path_index", []))

    sources = discover_unity_sources(input_summary["xapk_root"])
    if args.limit_sources is not None:
        sources = sources[: args.limit_sources]

    exporter = Exporter(output_root, UnityPy)
    source_summaries = []
    for label, path in sources:
        print(f"[extract] {label}: {path}")
        source_summaries.append(exporter.export_source(label, path))

    model_previews = {"enabled": False}
    if args.render_model_previews:
        model_previews = render_model_previews(output_root, args)

    manifest = {
        "app_slug": args.app_slug,
        "package_root": str(package_root),
        "output_root": str(output_root),
        "xapk_path": str(xapk_path),
        "xapk_manifest": input_summary["xapk_manifest"],
        "xapk_entry_count": input_summary["xapk_entry_count"],
        "nested_apks": input_summary["apks"],
        "unitypy_version": getattr(UnityPy, "__version__", None),
        "source_count": len(source_summaries),
        "sources": source_summaries,
        "global_exports": dict(exporter.global_exports),
        "global_recovered": dict(exporter.global_recovered),
        "global_object_types": dict(exporter.global_types),
        "raw_assets": raw_summary,
        "xapk_top_level_assets": copy_top_summary,
        "model_previews": model_previews,
        "layout": {
            "style": "flat browse-first",
            "model_previews": "previews/models",
            "models": "models",
            "path_index": "reports/path_index.json",
        },
        "notes": [
            "This dump includes decoded Unity object exports from nested split APKs and useful raw Android media/config files.",
            "Decoded assets are written to flat top-level browse folders instead of assets/<bucket>/<apk>/<nested-path>.",
            "Native libraries, dex bytecode, Android signatures, and raw Unity container bundles are intentionally excluded from the public dump.",
            "Text exports redact Google API-key-shaped strings before writing.",
            "Container-indexed GameObject and MonoBehaviour typetrees are exported, but unreferenced scene components are skipped to avoid low-value dumps.",
            "Failed Unity object exports are recovered in a second pass under recovered/ with typetrees, printable strings, and shader chunk analysis where available; raw/decompressed shader binaries are omitted from the public dump.",
        ],
        "errors": exporter.errors,
    }

    write_json(output_root / "reports" / "summary.json", manifest)
    write_json(
        output_root / "reports" / "errors.json",
        {"unity_errors": exporter.errors, "raw_errors": raw_summary.get("errors", [])},
    )
    script_target = output_root / "scripts" / Path(__file__).name
    ensure_parent(script_target)
    shutil.copy2(Path(__file__).resolve(), script_target)
    for helper_name in (
        "render_model_preview_blender.py",
        "render_model_preview_batch.py",
    ):
        helper = Path(__file__).resolve().parent / helper_name
        if helper.exists():
            shutil.copy2(helper, script_target.parent / helper_name)
    (output_root / "README.md").write_text(render_readme(manifest), encoding="utf-8")
    write_json(
        output_root / "reports" / "path_index.json",
        {
            "layout": manifest["layout"],
            "files": build_public_file_index(output_root),
            "unity_exports": exporter.path_index,
            "raw_assets": raw_path_index,
            "model_previews": model_previews.get("items", []),
        },
    )

    print(
        json.dumps(
            {
                "app_slug": args.app_slug,
                "sources": len(source_summaries),
                "exports": dict(exporter.global_exports),
                "recovered": dict(exporter.global_recovered),
                "raw_assets": raw_summary.get("copied", {}),
                "model_previews": {
                    "rendered": model_previews.get("rendered", 0),
                    "failures": model_previews.get("failures", 0),
                },
                "errors": len(exporter.errors) + len(raw_summary.get("errors", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
