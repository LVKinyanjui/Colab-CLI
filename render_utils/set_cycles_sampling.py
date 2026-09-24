"""
Configure Blender Cycles Sampling settings.

Canonical target:
    Blender 5.2 LTS

Compatibility target:
    Blender 3.6

Implemented sampling slices:
    - Core sampling
    - Adaptive sampling (render + viewport)

The public API uses None to mean "leave this setting unchanged".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Schemas are keyed by Blender major/minor version.
# 5.2 is the canonical target. 3.6 is retained as an explicit compatibility
# schema rather than being inferred from a generic compatibility system.
PRIMARY_SCHEMA_VERSION = (5, 2)

SAMPLING_SCHEMAS: dict[tuple[int, int], dict[str, dict[str, Any]]] = {
    (3, 6): {
        "render_samples": {
            "target": "cycles",
            "attribute": "samples",
            "type": int,
            "minimum": 1,
        },
        "viewport_samples": {
            "target": "cycles",
            "attribute": "preview_samples",
            "type": int,
            "minimum": 0,
        },
        "time_limit": {
            "target": "cycles",
            "attribute": "time_limit",
            "type": float,
            "minimum": 0.0,
        },
        "adaptive_sampling": {
            "target": "cycles",
            "attribute": "use_adaptive_sampling",
            "type": bool,
        },
        "adaptive_threshold": {
            "target": "cycles",
            "attribute": "adaptive_threshold",
            "type": float,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "adaptive_min_samples": {
            "target": "cycles",
            "attribute": "adaptive_min_samples",
            "type": int,
            "minimum": 0,
            "maximum": 4096,
        },
        "viewport_adaptive_sampling": {
            "target": "cycles",
            "attribute": "use_preview_adaptive_sampling",
            "type": bool,
        },
        "viewport_adaptive_threshold": {
            "target": "cycles",
            "attribute": "preview_adaptive_threshold",
            "type": float,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "viewport_adaptive_min_samples": {
            "target": "cycles",
            "attribute": "preview_adaptive_min_samples",
            "type": int,
            "minimum": 0,
            "maximum": 4096,
        },
    },
    (5, 2): {
        "render_samples": {
            "target": "cycles",
            "attribute": "samples",
            "type": int,
            "minimum": 1,
        },
        "viewport_samples": {
            "target": "cycles",
            "attribute": "preview_samples",
            "type": int,
            "minimum": 0,
        },
        "time_limit": {
            "target": "cycles",
            "attribute": "time_limit",
            "type": float,
            "minimum": 0.0,
        },
        "adaptive_sampling": {
            "target": "cycles",
            "attribute": "use_adaptive_sampling",
            "type": bool,
        },
        "adaptive_threshold": {
            "target": "cycles",
            "attribute": "adaptive_threshold",
            "type": float,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "adaptive_min_samples": {
            "target": "cycles",
            "attribute": "adaptive_min_samples",
            "type": int,
            "minimum": 0,
            "maximum": 4096,
        },
        "viewport_adaptive_sampling": {
            "target": "cycles",
            "attribute": "use_preview_adaptive_sampling",
            "type": bool,
        },
        "viewport_adaptive_threshold": {
            "target": "cycles",
            "attribute": "preview_adaptive_threshold",
            "type": float,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "viewport_adaptive_min_samples": {
            "target": "cycles",
            "attribute": "preview_adaptive_min_samples",
            "type": int,
            "minimum": 0,
            "maximum": 4096,
        },
    },
}


@dataclass(frozen=True)
class SettingChange:
    name: str
    old_value: Any
    new_value: Any


@dataclass(frozen=True)
class SamplingResult:
    changed: tuple[SettingChange, ...]
    unchanged: tuple[str, ...]


def get_blender_version() -> tuple[int, int]:
    """Return the running Blender major/minor version."""
    try:
        import bpy
    except ImportError as exc:
        raise RuntimeError(
            "Blender is required for automatic schema selection."
        ) from exc

    return bpy.app.version[:2]


def get_sampling_schema(
    version: tuple[int, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the schema for an explicit or running Blender version.

    Outside Blender (for example, during mock tests), the canonical 5.2
    schema is used because there is no running Blender version to inspect.
    """
    if version is None:
        try:
            version = get_blender_version()
        except RuntimeError:
            version = PRIMARY_SCHEMA_VERSION

    try:
        return SAMPLING_SCHEMAS[version]
    except KeyError as exc:
        supported = ", ".join(
            f"{major}.{minor}"
            for major, minor in sorted(SAMPLING_SCHEMAS)
        )
        raise RuntimeError(
            f"Unsupported Blender version {version[0]}.{version[1]}. "
            f"Supported versions: {supported}"
        ) from exc


def _get_target(scene: Any, target: str) -> Any:
    try:
        return getattr(scene, target)
    except AttributeError as exc:
        raise ValueError(
            f"Scene does not expose required target '{target}'."
        ) from exc


def _get_rna_property(target: Any, attribute: str) -> Any | None:
    """
    Return Blender RNA metadata when available.

    Mock objects generally do not expose bl_rna, so schema-level validation
    remains the fallback outside Blender.
    """
    bl_rna = getattr(target, "bl_rna", None)
    if bl_rna is None:
        return None

    properties = getattr(bl_rna, "properties", None)
    if properties is None:
        return None

    try:
        return properties[attribute]
    except (KeyError, TypeError):
        return None


def _validate_type(name: str, value: Any, expected_type: type) -> None:
    if expected_type is bool:
        if not isinstance(value, bool):
            raise TypeError(
                f"{name} must be bool, got {type(value).__name__}."
            )
        return

    # bool is an int subclass in Python, but it is not a valid sample count.
    if expected_type is int and isinstance(value, bool):
        raise TypeError(f"{name} must be int, not bool.")

    if not isinstance(value, expected_type):
        raise TypeError(
            f"{name} must be {expected_type.__name__}, "
            f"got {type(value).__name__}."
        )


def _validate_range(
    name: str,
    value: Any,
    setting_schema: dict[str, Any],
    rna_property: Any | None,
) -> None:
    """
    Validate against Blender RNA hard bounds when available.

    Schema bounds are the fallback for mock/unit-test execution.
    """
    minimum = setting_schema.get("minimum")
    maximum = setting_schema.get("maximum")

    if rna_property is not None:
        hard_min = getattr(rna_property, "hard_min", None)
        hard_max = getattr(rna_property, "hard_max", None)

        if hard_min is not None:
            minimum = hard_min
        if hard_max is not None:
            maximum = hard_max

    if minimum is not None and value < minimum:
        raise ValueError(
            f"{name} must be >= {minimum}, got {value}."
        )

    if maximum is not None and value > maximum:
        raise ValueError(
            f"{name} must be <= {maximum}, got {value}."
        )


def _validate_setting(
    scene: Any,
    schema: dict[str, dict[str, Any]],
    name: str,
    value: Any,
) -> None:
    setting_schema = schema[name]
    target = _get_target(scene, setting_schema["target"])
    attribute = setting_schema["attribute"]

    rna_property = _get_rna_property(target, attribute)
    expected_type = setting_schema["type"]

    if rna_property is not None:
        rna_type = getattr(rna_property, "type", None)
        expected_rna_type = {
            int: "INT",
            float: "FLOAT",
            bool: "BOOLEAN",
        }[expected_type]

        if rna_type is not None and rna_type != expected_rna_type:
            raise TypeError(
                f"RNA type mismatch for {name}: "
                f"expected {expected_rna_type}, got {rna_type}."
            )

    _validate_type(name, value, expected_type)
    _validate_range(name, value, setting_schema, rna_property)


def _get_current_value(
    scene: Any,
    schema: dict[str, dict[str, Any]],
    name: str,
) -> Any:
    setting_schema = schema[name]
    target = _get_target(scene, setting_schema["target"])
    return getattr(target, setting_schema["attribute"])


def _set_value(
    scene: Any,
    schema: dict[str, dict[str, Any]],
    name: str,
    value: Any,
) -> None:
    setting_schema = schema[name]
    target = _get_target(scene, setting_schema["target"])
    setattr(target, setting_schema["attribute"], value)


def configure_cycles_sampling(
    scene: Any,
    *,
    render_samples: int | None = None,
    viewport_samples: int | None = None,
    time_limit: float | None = None,
    adaptive_sampling: bool | None = None,
    adaptive_threshold: float | None = None,
    adaptive_min_samples: int | None = None,
    viewport_adaptive_sampling: bool | None = None,
    viewport_adaptive_threshold: float | None = None,
    viewport_adaptive_min_samples: int | None = None,
) -> SamplingResult:
    """
    Configure Cycles Sampling settings.

    None means "leave unchanged".

    Blender semantics retained by this API:
        - viewport_samples=0 means unlimited viewport samples.
        - time_limit=0.0 disables the render time limit.
        - adaptive_threshold=0.0 selects Blender's automatic threshold.
        - adaptive_min_samples=0 selects Blender's automatic minimum.
        - viewport_adaptive_threshold=0.0 selects Blender's automatic threshold.
        - viewport_adaptive_min_samples=0 selects Blender's automatic minimum.
    """
    schema = get_sampling_schema()

    requested = {
        "render_samples": render_samples,
        "viewport_samples": viewport_samples,
        "time_limit": time_limit,
        "adaptive_sampling": adaptive_sampling,
        "adaptive_threshold": adaptive_threshold,
        "adaptive_min_samples": adaptive_min_samples,
        "viewport_adaptive_sampling": viewport_adaptive_sampling,
        "viewport_adaptive_threshold": viewport_adaptive_threshold,
        "viewport_adaptive_min_samples": viewport_adaptive_min_samples,
    }

    # Validate everything before mutating anything.
    for name, value in requested.items():
        if value is not None:
            _validate_setting(scene, schema, name, value)

    changed: list[SettingChange] = []
    unchanged: list[str] = []

    # Apply only after validation succeeds.
    for name, value in requested.items():
        if value is None:
            unchanged.append(name)
            continue

        old_value = _get_current_value(scene, schema, name)

        if old_value == value:
            unchanged.append(name)
            continue

        _set_value(scene, schema, name, value)
        changed.append(
            SettingChange(
                name=name,
                old_value=old_value,
                new_value=value,
            )
        )

    return SamplingResult(
        changed=tuple(changed),
        unchanged=tuple(unchanged),
    )
