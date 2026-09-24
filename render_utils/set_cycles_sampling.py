"""
Configure Blender Cycles Sampling settings.

First implementation slice:
    - Render Samples
    - Viewport Samples
    - Time Limit

The public API uses None to mean "leave this setting unchanged".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SAMPLING_SCHEMA = {
    "render_samples": {
        "target": "cycles",
        "attribute": "samples",
        "type": int,
        "minimum": 0,
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

    Mock objects generally won't expose bl_rna, so the API falls back
    to schema-level validation in unit tests.
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
    # bool is an int subclass in Python, but it is not a valid sample count.
    if expected_type is int and isinstance(value, bool):
        raise TypeError(
            f"{name} must be an int, not bool."
        )

    if not isinstance(value, expected_type):
        raise TypeError(
            f"{name} must be {expected_type.__name__}, "
            f"got {type(value).__name__}."
        )


def _validate_range(
    name: str,
    value: Any,
    schema: dict[str, Any],
    rna_property: Any | None,
) -> None:
    """
    Validate against Blender RNA hard bounds when available.

    The schema minimum is used as a fallback for mocks/tests.
    """
    minimum = schema.get("minimum")

    if rna_property is not None:
        hard_min = getattr(rna_property, "hard_min", None)

        if hard_min is not None:
            minimum = hard_min

    if minimum is not None and value < minimum:
        raise ValueError(
            f"{name} must be >= {minimum}, got {value}."
        )

    if rna_property is not None:
        hard_max = getattr(rna_property, "hard_max", None)

        if hard_max is not None and value > hard_max:
            raise ValueError(
                f"{name} must be <= {hard_max}, got {value}."
            )


def _validate_setting(
    scene: Any,
    name: str,
    value: Any,
) -> None:
    schema = SAMPLING_SCHEMA[name]
    target = _get_target(scene, schema["target"])
    attribute = schema["attribute"]

    rna_property = _get_rna_property(target, attribute)

    expected_type = schema["type"]

    if rna_property is not None:
        rna_type = getattr(rna_property, "type", None)

        expected_rna_type = {
            int: "INT",
            float: "FLOAT",
        }[expected_type]

        if rna_type is not None and rna_type != expected_rna_type:
            raise TypeError(
                f"RNA type mismatch for {name}: "
                f"expected {expected_rna_type}, got {rna_type}."
            )

    _validate_type(name, value, expected_type)
    _validate_range(name, value, schema, rna_property)


def _get_current_value(scene: Any, name: str) -> Any:
    schema = SAMPLING_SCHEMA[name]
    target = _get_target(scene, schema["target"])
    return getattr(target, schema["attribute"])


def _set_value(scene: Any, name: str, value: Any) -> None:
    schema = SAMPLING_SCHEMA[name]
    target = _get_target(scene, schema["target"])
    setattr(target, schema["attribute"], value)


def configure_cycles_sampling(
    scene: Any,
    *,
    render_samples: int | None = None,
    viewport_samples: int | None = None,
    time_limit: float | None = None,
) -> SamplingResult:
    """
    Configure Cycles core sampling settings.

    None means "leave unchanged".

    Parameters
    ----------
    scene:
        Blender Scene-like object.

    render_samples:
        Maximum render samples per pixel.

    viewport_samples:
        Maximum viewport samples per pixel.
        Blender defines 0 as indefinite viewport sampling.

    time_limit:
        Maximum render time in seconds.
        Blender defines 0 as no time limit.
    """
    requested = {
        "render_samples": render_samples,
        "viewport_samples": viewport_samples,
        "time_limit": time_limit,
    }

    changed: list[SettingChange] = []
    unchanged: list[str] = []

    # Validate everything before mutating anything.
    for name, value in requested.items():
        if value is not None:
            _validate_setting(scene, name, value)

    # Apply only after validation succeeds.
    for name, value in requested.items():
        if value is None:
            unchanged.append(name)
            continue

        old_value = _get_current_value(scene, name)

        if old_value == value:
            unchanged.append(name)
            continue

        _set_value(scene, name, value)

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
