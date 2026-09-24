#!/usr/bin/env python3
"""
set_cycles_performance.py

Headless-safe configurator for the Cycles Render Properties -> Performance
settings used by Blender 5.2, with limited compatibility for older Blender
versions where the corresponding properties still exist.

The script writes directly to Blender RNA objects:
    scene.render
    scene.cycles

It deliberately does not require a Properties editor or UI context.

Examples:
    blender -b scene.blend --python set_cycles_performance.py -- \\
        --threads-mode FIXED --threads 8 --tile-size 512 \\
        --persistent-data true

    blender -b scene.blend --python set_cycles_performance.py -- \\
        --preset FASTER_RENDER

    blender -b scene.blend --python set_cycles_performance.py -- \\
        --preset LOWER_MEMORY --tile-size 512

Notes:
    * DEFAULT is retained as a compatibility alias for BALANCED.
    * Blender 5.2 uses render.use_auto_generate_texture_cache for the
      Texture Cache "Auto Generate" control. It is NOT a Cycles property.
    * Blender 5.2 uses compositor_denoise_* (not compositor_denoising_*).
    * argparse is wrapped so normal script completion never calls
      SystemExit; this avoids the accidental Blender shutdown caused by the
      earlier experimental script.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    import bpy  # type: ignore
    BLENDER_VERSION = tuple(bpy.app.version)
except ImportError:
    # Allows the validation/application layer to be unit-tested outside
    # Blender with simple mock scene objects.
    bpy = None  # type: ignore
    BLENDER_VERSION = (0, 0, 0)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

PERFORMANCE_SCHEMA: dict[str, dict[str, Any]] = {
    # Final Render ----------------------------------------------------------
    "persistent_data": {
        "target": "render",
        "attr": "use_persistent_data",
        "type": bool,
        "default": False,
    },

    # Memory / Tiling -------------------------------------------------------
    "tile_size": {
        "target": "cycles",
        "attr": "tile_size",
        "type": int,
        "min": 1,
        "default": 2048,
    },
    # Blender <= 3.x legacy UI property. Tiling is always enabled in newer
    # Cycles versions and this property is no longer part of the 5.2 UI.
    "use_auto_tile": {
        "target": "cycles",
        "attr": "use_auto_tile",
        "type": bool,
        "max_version": (4, 0, 0),
        "legacy": True,
    },

    # Texture Cache ---------------------------------------------------------
    # Blender 5.2 exposes these on RenderSettings (scene.render), not
    # CyclesRenderSettings (scene.cycles).
    "use_texture_cache": {
        "target": "render",
        "attr": "use_texture_cache",
        "type": bool,
        "min_version": (5, 2, 0),
        "default": True,
    },
    "texture_cache_auto_generate": {
        "target": "render",
        "attr": "use_auto_generate_texture_cache",
        "type": bool,
        "min_version": (5, 2, 0),
        "default": False,
    },

    # Acceleration Structure -----------------------------------------------
    "spatial_splits": {
        "target": "cycles",
        "attr": "debug_use_spatial_splits",
        "type": bool,
    },
    "compact_bvh": {
        "target": "cycles",
        "attr": "debug_use_compact_bvh",
        "type": bool,
    },
    "curves_bvh": {
        "target": "cycles",
        "attr": "debug_use_hair_bvh",
        "type": bool,
    },
    "bvh_time_steps": {
        "target": "cycles",
        "attr": "debug_bvh_time_steps",
        "type": int,
        "min": 0,
        "max": 16,
    },

    # Compositor ------------------------------------------------------------
    "compositor_device": {
        "target": "render",
        "attr": "compositor_device",
        "type": str,
        "choices": ("CPU", "GPU"),
        "min_version": (4, 0, 0),
    },
    "compositor_precision": {
        "target": "render",
        "attr": "compositor_precision",
        "type": str,
        "choices": ("AUTO", "FULL"),
        "min_version": (4, 0, 0),
    },
    "compositor_denoise_device": {
        "target": "render",
        "attr": "compositor_denoise_device",
        "type": str,
        "choices": ("AUTO", "CPU", "GPU"),
        "min_version": (5, 2, 0),
    },
    "compositor_denoise_preview_quality": {
        "target": "render",
        "attr": "compositor_denoise_preview_quality",
        "type": str,
        "choices": ("HIGH", "BALANCED", "FAST"),
        "min_version": (5, 2, 0),
    },
    "compositor_denoise_final_quality": {
        "target": "render",
        "attr": "compositor_denoise_final_quality",
        "type": str,
        "choices": ("HIGH", "BALANCED", "FAST"),
        "min_version": (5, 2, 0),
    },

    # Threads / Viewport ----------------------------------------------------
    "threads_mode": {
        "target": "render",
        "attr": "threads_mode",
        "type": str,
        "choices": ("AUTO", "FIXED"),
    },
    "threads": {
        "target": "render",
        "attr": "threads",
        "type": int,
        "min": 1,
        "default": None,
    },
    "preview_pixel_size": {
        "target": "render",
        "attr": "preview_pixel_size",
        "type": str,
        "choices": ("AUTO", "1", "2", "4", "8"),
    },
}


# ---------------------------------------------------------------------------
# Workflow presets
# ---------------------------------------------------------------------------

# These are workflow presets maintained by this script. They are not meant
# to reproduce Blender's internal preset implementation byte-for-byte.
PRESETS: dict[str, dict[str, Any]] = {
    "FASTER_RENDER": {
        "persistent_data": True,
        "tile_size": 2048,
        "spatial_splits": True,
        "compact_bvh": False,
        "curves_bvh": True,
        "compositor_device": "GPU",
        "compositor_precision": "FULL",
        "use_texture_cache": False,
    },
    "LOWER_MEMORY": {
        "persistent_data": False,
        "tile_size": 512,
        "spatial_splits": False,
        "compact_bvh": True,
        "curves_bvh": False,
        "compositor_device": "CPU",
        "use_texture_cache": True,
    },
    "BALANCED": {
        "persistent_data": False,
        "tile_size": 2048,
        "spatial_splits": False,
        "compact_bvh": False,
        "curves_bvh": True,
        "compositor_device": "GPU",
        "compositor_precision": "AUTO",
        # This is intentionally a workflow choice, not a claim about
        # Blender's current factory default.
        "use_texture_cache": False,
    },
}

PRESET_ALIASES = {
    # Preserve the CLI used by the user's existing script.
    "DEFAULT": "BALANCED",
}

PRESET_CHOICES = tuple(PRESETS) + tuple(PRESET_ALIASES)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class ConfigurationError(ValueError):
    """Raised when a requested setting cannot be safely applied."""


def _version_string(version: tuple[int, ...]) -> str:
    return ".".join(str(x) for x in version)


def _expected_type_name(expected: type) -> str:
    if expected is bool:
        return "boolean"
    if expected is int:
        return "integer"
    if expected is str:
        return "string"
    return expected.__name__


def validate_value(key: str, value: Any) -> None:
    """Validate a value against the script-level schema."""
    if key not in PERFORMANCE_SCHEMA:
        raise ConfigurationError(f"unknown Performance setting: {key!r}")

    spec = PERFORMANCE_SCHEMA[key]
    expected = spec["type"]

    # bool is a subclass of int in Python, so handle integer validation
    # separately to prevent True/False being accepted as thread counts.
    if expected is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigurationError(
                f"{key}: expected {_expected_type_name(expected)}, "
                f"got {type(value).__name__}"
            )
    elif not isinstance(value, expected):
        raise ConfigurationError(
            f"{key}: expected {_expected_type_name(expected)}, "
            f"got {type(value).__name__}"
        )

    if "choices" in spec and value not in spec["choices"]:
        choices = ", ".join(repr(v) for v in spec["choices"])
        raise ConfigurationError(
            f"{key}: invalid value {value!r}; expected one of {choices}"
        )

    if "min" in spec and value < spec["min"]:
        raise ConfigurationError(
            f"{key}: value {value!r} is below minimum {spec['min']}"
        )

    if "max" in spec and value > spec["max"]:
        raise ConfigurationError(
            f"{key}: value {value!r} is above maximum {spec['max']}"
        )


def validate_version(key: str, version: tuple[int, ...]) -> None:
    spec = PERFORMANCE_SCHEMA[key]

    min_version = spec.get("min_version")
    if min_version is not None and version < min_version:
        raise ConfigurationError(
            f"{key}: requires Blender >= {_version_string(min_version)}; "
            f"running Blender {_version_string(version)}"
        )

    max_version = spec.get("max_version")
    if max_version is not None and version >= max_version:
        raise ConfigurationError(
            f"{key}: is a legacy setting not available for Blender "
            f">= {_version_string(max_version)}; "
            f"running Blender {_version_string(version)}"
        )


def _rna_property(obj: Any, attr_name: str) -> Any | None:
    """Return the RNA property definition when available."""
    try:
        return obj.bl_rna.properties[attr_name]
    except Exception:
        return None


def _validate_against_rna(obj: Any, attr_name: str, value: Any) -> None:
    """Use Blender RNA metadata as a second line of validation."""
    prop = _rna_property(obj, attr_name)
    if prop is None:
        return

    # Check enum values against Blender itself where possible.
    if getattr(prop, "type", None) == "ENUM":
        try:
            identifiers = {item.identifier for item in prop.enum_items}
            if identifiers and value not in identifiers:
                raise ConfigurationError(
                    f"{attr_name}: Blender RNA does not accept {value!r}; "
                    f"available values: {sorted(identifiers)}"
                )
        except ConfigurationError:
            raise
        except Exception:
            pass

    # Check hard RNA range when exposed.
    if isinstance(value, int) and not isinstance(value, bool):
        hard_min = getattr(prop, "hard_min", None)
        hard_max = getattr(prop, "hard_max", None)

        if hard_min is not None and value < hard_min:
            raise ConfigurationError(
                f"{attr_name}: value {value} is below Blender RNA minimum "
                f"{hard_min}"
            )
        if hard_max is not None and value > hard_max:
            raise ConfigurationError(
                f"{attr_name}: value {value} is above Blender RNA maximum "
                f"{hard_max}"
            )


def _targets(scene: Any) -> dict[str, Any]:
    """Resolve schema target names to scene objects."""
    result = {
        "render": getattr(scene, "render", None),
        "cycles": getattr(scene, "cycles", None),
    }

    missing = [name for name, obj in result.items() if obj is None]
    if missing:
        raise ConfigurationError(
            "scene is missing required target object(s): "
            + ", ".join(missing)
        )

    return result


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def apply_settings(
    scene: Any,
    settings: dict[str, Any],
    *,
    blender_version: tuple[int, ...] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """
    Apply settings to scene.render / scene.cycles.

    strict=True:
        Unknown, unsupported, missing, or invalid settings raise
        ConfigurationError.

    strict=False:
        Unsupported/missing settings are reported and skipped. Value
        validation errors still raise, because applying an invalid value is
        never treated as safe.

    Returns a report containing the successfully applied settings.
    """
    version = tuple(blender_version or BLENDER_VERSION)
    targets = _targets(scene)
    applied: dict[str, Any] = {}

    for key, value in settings.items():
        if key not in PERFORMANCE_SCHEMA:
            message = f"unknown Performance setting: {key!r}"
            if strict:
                raise ConfigurationError(message)
            print(f"  [!] {message} -- skipped")
            continue

        validate_value(key, value)

        try:
            validate_version(key, version)
        except ConfigurationError as exc:
            if strict:
                raise
            print(f"  [!] {exc} -- skipped")
            continue

        spec = PERFORMANCE_SCHEMA[key]
        target_name = spec["target"]
        target_obj = targets[target_name]
        attr_name = spec["attr"]

        if not hasattr(target_obj, attr_name):
            message = (
                f"{key}: Blender {target_name} object does not expose "
                f"attribute {attr_name!r}"
            )
            if strict:
                raise ConfigurationError(message)
            print(f"  [!] {message} -- skipped")
            continue

        _validate_against_rna(target_obj, attr_name, value)

        old_value = getattr(target_obj, attr_name)
        setattr(target_obj, attr_name, value)
        new_value = getattr(target_obj, attr_name)

        # Verify the assignment actually took effect. Blender RNA normally
        # normalizes values only within its allowed ranges; this catches
        # unexpected type coercion or custom mock behavior as well.
        if new_value != value:
            raise ConfigurationError(
                f"{key}: requested {value!r}, but Blender stored "
                f"{new_value!r}"
            )

        applied[key] = new_value

        print(
            f"  [+] Set {target_name}.{attr_name} = {new_value!r}"
            + (f" (was {old_value!r})" if old_value != new_value else "")
        )

    return applied


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

class CLIError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    """argparse parser that never calls SystemExit."""

    def error(self, message: str) -> None:
        raise CLIError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if status:
            raise CLIError(message or "argument parsing failed")
        raise CLIError(message or "")


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized in {"true", "yes", "y", "1", "on"}:
        return True
    if normalized in {"false", "no", "n", "0", "off"}:
        return False

    raise argparse.ArgumentTypeError(
        f"expected true/false, got {value!r}"
    )


def parser_for_type(spec: dict[str, Any]) -> dict[str, Any]:
    expected = spec["type"]

    if expected is bool:
        result: dict[str, Any] = {"type": parse_bool}
    elif expected is int:
        result = {"type": int}
    elif expected is str:
        # All current string schema entries are Blender enum properties.
        # Normalize CLI values so AUTO/auto and FIXED/fixed behave alike.
        result = {"type": str.upper if "choices" in spec else str}
    else:
        raise RuntimeError(f"Unsupported schema type: {expected!r}")

    if "choices" in spec:
        result["choices"] = spec["choices"]

    return result


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(
        description=(
            "Configure Blender Cycles Render Properties -> Performance "
            "settings. Run Blender with '--' before these arguments."
        )
    )

    parser.add_argument(
        "--preset",
        choices=PRESET_CHOICES,
        type=str.upper,
        help="Apply a workflow preset before individual overrides.",
    )

    for key, spec in PERFORMANCE_SCHEMA.items():
        option = f"--{key.replace('_', '-')}"
        parser.add_argument(
            option,
            dest=key,
            default=None,
            metavar=key.upper(),
            **parser_for_type(spec),
        )

    return parser


def parse_args(argv: list[str] | None = None) -> tuple[str | None, dict[str, Any]]:
    args = list(sys.argv[1:] if argv is None else argv)

    # When launched by Blender, arguments intended for the script are
    # conventionally placed after '--'.
    if "--" in args:
        args = args[args.index("--") + 1 :]

    parser = build_parser()

    try:
        parsed = parser.parse_args(args)
    except CLIError as exc:
        message = str(exc)
        if message:
            raise ConfigurationError(message) from exc
        return None, {}

    data = vars(parsed)
    preset = data.pop("preset", None)
    overrides = {
        key: value
        for key, value in data.items()
        if value is not None
    }

    return preset, overrides


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if bpy is None:
        print("ERROR: this script must run inside Blender.")
        return 2

    print("=" * 80)
    print("BLENDER CYCLES PERFORMANCE CONFIGURATOR")
    print("=" * 80)
    print(f"Blender version : {bpy.app.version_string}")

    scene = bpy.context.scene

    # Require Cycles explicitly. This is a render-settings configurator, not
    # a generic engine-selection tool.
    try:
        scene.render.engine = "CYCLES"
    except Exception as exc:
        print(f"ERROR: could not set render engine to CYCLES: {exc}")
        return 2

    print(f"Scene           : {scene.name}")
    print(f"Render engine   : {scene.render.engine}")

    try:
        preset, overrides = parse_args()

        if preset:
            canonical = PRESET_ALIASES.get(preset, preset)
            if canonical != preset:
                print(f"\n[*] Preset alias: {preset} -> {canonical}")

            print(f"[*] Applying Performance Preset: {canonical}")
            apply_settings(
                scene,
                PRESETS[canonical],
                blender_version=BLENDER_VERSION,
                strict=True,
            )

        if overrides:
            print("\n[*] Applying Overrides:")
            apply_settings(
                scene,
                overrides,
                blender_version=BLENDER_VERSION,
                strict=True,
            )

        if not preset and not overrides:
            print("\n[*] No settings supplied; nothing changed.")
            print("    Use --help after '--' for available options.")

    except (ConfigurationError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2

    print("\n[+] Performance configuration complete.")
    return 0


if __name__ == "__main__":
    # Deliberately do NOT use: raise SystemExit(main())
    # That can terminate the Blender process when a script is run from the
    # interactive application. The function return value is intentionally
    # ignored here.
    main()

