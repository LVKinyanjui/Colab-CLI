"""Shared machinery for Cycles configuration groups.

Holds the versioned-schema pattern and conventions established by
set_cycles_sampling.py, generalised so every settings group (sampling,
performance, ...) shares one implementation:

- versioned schemas keyed by ``(major, minor)``
- ``None`` means "leave unchanged" and is never reported
- validation happens before any mutation (atomic configure calls)
- results split explicitly-requested settings into changed/unchanged
- Blender state is validated against live RNA when available; validation is
  fully permissive for enum wording when bpy is absent (mock/offline mode)
"""

from dataclasses import dataclass, field
from typing import Any, Callable


class ConfigurationError(ValueError):
    """Raised for unknown settings or values rejected by validation."""


@dataclass
class SettingChange:
    name: str
    old_value: Any
    new_value: Any


@dataclass
class GroupResult:
    """Base result object for a configuration group.

    Groups may attach extra informational attributes directly on the
    instance (e.g. performance attaches ``engine``, ``device``,
    ``num_devices``).
    """

    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def split_changes(changes: list[SettingChange]) -> tuple[list[str], list[str]]:
    """Split SettingChange records into (changed, unchanged) name lists."""
    changed = [c.name for c in changes if c.old_value != c.new_value]
    unchanged = [c.name for c in changes if c.old_value == c.new_value]
    return changed, unchanged


def get_blender_version() -> tuple[int, int] | None:
    """Return the running Blender (major, minor), or None without bpy."""
    try:
        import bpy

        return tuple(bpy.app.version[:2])
    except ImportError:
        return None


def get_schema_group(
    schemas: dict[tuple[int, int], dict[str, dict[str, Any]]],
    version: tuple[int, int] | None,
    group_name: str,
) -> dict[str, dict[str, Any]]:
    """Look up the schema for a Blender version, failing loudly.

    ``version`` may be None only when bpy is importable; otherwise a
    ConfigurationError lists the supported versions (no silent fallback).
    """
    if version is None:
        detected = get_blender_version()
        if detected is None:
            supported = sorted(f"Blender {major}.{minor}" for major, minor in schemas)
            raise ConfigurationError(
                f"Unable to auto-detect Blender version outside Blender; "
                f"known schemas: {', '.join(supported)}"
            )
        version = detected
    try:
        return schemas[version]
    except KeyError:
        supported = sorted(f"Blender {major}.{minor}" for major, minor in schemas)
        raise ConfigurationError(
            f"Unsupported Blender version {version[0]}.{version[1]} for {group_name}. "
            f"Supported: {', '.join(supported)}"
        ) from None


def make_range_message(
    group: str,
    name: str,
    internal_name: str,
    value: Any,
    min_value: Any,
    max_value: Any,
) -> str:
    """Central wording for out-of-range errors so all layers agree."""
    return (
        f"Invalid {group} value for '{name}' ({internal_name}): {value!r}. "
        f"Must be between {min_value} and {max_value}."
    )


def _rna_property(obj: Any, attr_name: str) -> Any | None:
    """Return the RNA property metadata for an attribute, or None."""
    rna = getattr(obj, "bl_rna", None)
    if rna is None:
        return None
    return rna.properties.get(attr_name)


def _blender_default(obj: Any, attr_name: str) -> Any:
    """Return the RNA-declared default for an attribute, or None."""
    prop = _rna_property(obj, attr_name)
    if prop is not None:
        return getattr(prop, "default", None)
    return None


def validate_setting(
    group: str,
    schema: dict[str, dict[str, Any]],
    name: str,
    value: Any,
    *,
    default_fn: Callable[[dict[str, Any]], Any] | None = None,
) -> None:
    """Validate one explicitly-requested setting against its schema spec.

    - Unknown names are rejected with the known-name list.
    - Types are checked against the schema's expected type.
    - Central min/max ranges produce the shared range message.
    - Enum-typed specs with an ``enum_range`` key substitute Blender defaults
      via ``default_fn`` when a part is None; groups without a default rule
      raise immediately (the boundary rule lives at group level). Without bpy
      the resolver cannot run, so enum wortding validation is permissive.
    """
    spec = schema.get(name)
    if spec is None:
        known = ", ".join(sorted(schema))
        raise ConfigurationError(f"Unknown setting: '{name}'. Known settings: {known}")

    expected_type = spec["type"]
    if not isinstance(value, expected_type):
        raise ConfigurationError(
            f"Invalid type for '{name}': expected {expected_type.__name__}, "
            f"got '{type(value).__name__}'"
        )

    min_value = spec.get("min")
    max_value = spec.get("max")

    enum_range = spec.get("enum_range")
    if enum_range is not None:
        resolved: dict[str, Any] = {}
        for part, needs_default in enum_range.items():
            if needs_default:
                if default_fn is None:
                    raise ConfigurationError(
                        f"Schema for '{name}' requires a Blender default for part "
                        f"'{part}', but this group has no default rule"
                    )
                resolved[part] = default_fn(spec)
            else:
                resolved[part] = value
        if resolved.get("preview_qual") is not None:
            min_value = resolved["preview_qual"]
        if resolved.get("final_qual") is not None:
            max_value = resolved["final_qual"]

    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and min_value is not None
        and max_value is not None
    ):
        if not (min_value <= value <= max_value):
            raise ConfigurationError(
                make_range_message(group, name, spec["attr"], value, min_value, max_value)
            )


def apply_schema(
    scene: Any,
    schema: dict[str, dict[str, Any]],
    settings: dict[str, Any],
    get_target: Callable[[dict[str, Any]], Any],
    *,
    default_fn: Callable[[dict[str, Any]], Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Validate then apply settings atomically; return (changed, unchanged).

    Phase 1 validates every explicitly-requested (non-None) setting against
    the schema; any failure raises before anything is written. Phase 2 reads
    the current value, writes the new one, and re-reads so mocks without
    real setattr semantics still record the attempted value.
    """
    for name, value in settings.items():
        if value is None:
            continue
        validate_setting(
            _group_name, schema, name, value, default_fn=default_fn
        )

    changes: list[SettingChange] = []
    for name, value in settings.items():
        if value is None:
            continue
        spec = schema[name]
        target = get_target(spec)
        attr = spec["attr"]
        old_value = getattr(target, attr, None)
        try:
            setattr(target, attr, value)
            new_value = getattr(target, attr)
        except (AttributeError, TypeError, ValueError):
            new_value = value
        changes.append(SettingChange(name=name, old_value=old_value, new_value=new_value))

    return split_changes(changes)


# Default group label used in range messages; groups that want their own
# wording pass it explicitly to validate_setting.
_group_name = "render"
