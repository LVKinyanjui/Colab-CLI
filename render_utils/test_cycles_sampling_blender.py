"""Blender integration test for Cycles Sampling.

Primary integration target: Blender 5.2 LTS
Compatibility target: Blender 3.6

Run:
    blender -b -P test_cycles_sampling_blender.py
"""

from __future__ import annotations

import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import bpy
except ModuleNotFoundError:
    # Ordinary pytest collection happens outside Blender. In that environment
    # this is an integration-only test module.
    if "pytest" in sys.modules:
        import pytest
        pytest.skip(
            "Blender integration test; run with Blender 5.2 LTS.",
            allow_module_level=True,
        )
    raise

from set_cycles_sampling import (
    SAMPLING_SCHEMAS,
    configure_cycles_sampling,
    get_sampling_schema,
)


SUPPORTED_VERSION = bpy.app.version[:2]
PRIMARY_VERSION = (5, 2)

if SUPPORTED_VERSION not in SAMPLING_SCHEMAS:
    raise RuntimeError(
        f"Unsupported Blender version {SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}. "
        f"Supported versions: "
        f"{', '.join(f'{a}.{b}' for a, b in sorted(SAMPLING_SCHEMAS))}"
    )


print("Blender version:", bpy.app.version_string)
print("Sampling schema version:", f"{SUPPORTED_VERSION[0]}.{SUPPORTED_VERSION[1]}")
print(
    "Integration role:",
    "PRIMARY" if SUPPORTED_VERSION == PRIMARY_VERSION else "COMPATIBILITY",
)


scene = bpy.context.scene
assert hasattr(scene, "cycles")
cycles = scene.cycles
rna = cycles.bl_rna
schema = get_sampling_schema(SUPPORTED_VERSION)


EXPECTED_PROPERTIES = {
    "render_samples": "samples",
    "viewport_samples": "preview_samples",
    "time_limit": "time_limit",
    "adaptive_sampling": "use_adaptive_sampling",
    "adaptive_threshold": "adaptive_threshold",
    "adaptive_min_samples": "adaptive_min_samples",
    "viewport_adaptive_sampling": "use_preview_adaptive_sampling",
    "viewport_adaptive_threshold": "preview_adaptive_threshold",
    "viewport_adaptive_min_samples": "preview_adaptive_min_samples",
}

EXPECTED_RNA_TYPES = {
    "render_samples": "INT",
    "viewport_samples": "INT",
    "time_limit": "FLOAT",
    "adaptive_sampling": "BOOLEAN",
    "adaptive_threshold": "FLOAT",
    "adaptive_min_samples": "INT",
    "viewport_adaptive_sampling": "BOOLEAN",
    "viewport_adaptive_threshold": "FLOAT",
    "viewport_adaptive_min_samples": "INT",
}

for public_name, rna_name in EXPECTED_PROPERTIES.items():
    assert public_name in schema
    assert schema[public_name]["attribute"] == rna_name
    assert rna_name in rna.properties, rna_name
    assert rna.properties[rna_name].type == EXPECTED_RNA_TYPES[public_name]


# 5.2 is the canonical integration target. Check its RNA hard limits.
if SUPPORTED_VERSION == PRIMARY_VERSION:
    assert rna.properties["samples"].hard_min == 1
    assert rna.properties["preview_samples"].hard_min == 0
    assert rna.properties["time_limit"].hard_min == 0.0

    assert rna.properties["adaptive_threshold"].hard_min == 0.0
    assert rna.properties["adaptive_threshold"].hard_max == 1.0
    assert rna.properties["adaptive_min_samples"].hard_min == 0
    assert rna.properties["adaptive_min_samples"].hard_max == 4096

    assert rna.properties["preview_adaptive_threshold"].hard_min == 0.0
    assert rna.properties["preview_adaptive_threshold"].hard_max == 1.0
    assert rna.properties["preview_adaptive_min_samples"].hard_min == 0
    assert rna.properties["preview_adaptive_min_samples"].hard_max == 4096


# Positive round-trip.
configure_cycles_sampling(
    scene,
    render_samples=512,
    viewport_samples=64,
    time_limit=300.0,
    adaptive_sampling=True,
    adaptive_threshold=0.01,
    adaptive_min_samples=32,
    viewport_adaptive_sampling=True,
    viewport_adaptive_threshold=0.05,
    viewport_adaptive_min_samples=8,
)

assert cycles.samples == 512
assert cycles.preview_samples == 64
assert cycles.time_limit == 300.0
assert cycles.use_adaptive_sampling is True
assert cycles.adaptive_min_samples == 32
assert cycles.use_preview_adaptive_sampling is True
assert cycles.preview_adaptive_min_samples == 8

# Blender RNA FLOAT values are single precision. Do not compare them with
# exact Python-float equality after a round-trip through RNA.
assert math.isclose(
    cycles.adaptive_threshold,
    0.01,
    rel_tol=0.0,
    abs_tol=1e-6,
)
assert math.isclose(
    cycles.preview_adaptive_threshold,
    0.05,
    rel_tol=0.0,
    abs_tol=1e-6,
)


# Explicit Blender-defined automatic/unlimited values.
configure_cycles_sampling(
    scene,
    viewport_samples=0,
    time_limit=0.0,
    adaptive_threshold=0.0,
    adaptive_min_samples=0,
    viewport_adaptive_threshold=0.0,
    viewport_adaptive_min_samples=0,
)

assert cycles.preview_samples == 0
assert cycles.time_limit == 0.0
assert math.isclose(cycles.adaptive_threshold, 0.0, abs_tol=1e-9)
assert cycles.adaptive_min_samples == 0
assert math.isclose(cycles.preview_adaptive_threshold, 0.0, abs_tol=1e-9)
assert cycles.preview_adaptive_min_samples == 0


# Existing values should be left unchanged and reported as such.
result = configure_cycles_sampling(
    scene,
    render_samples=512,
    viewport_samples=0,
    time_limit=0.0,
)

assert result.changed == ()
assert result.unchanged == (
    "render_samples",
    "viewport_samples",
    "time_limit",
)


# RNA-backed invalid range checks.
for kwargs in (
    {"render_samples": 0},
    {"viewport_samples": -1},
    {"time_limit": -1.0},
    {"adaptive_threshold": -0.001},
    {"adaptive_threshold": 1.001},
    {"adaptive_min_samples": -1},
    {"adaptive_min_samples": 4097},
    {"viewport_adaptive_threshold": -0.001},
    {"viewport_adaptive_threshold": 1.001},
    {"viewport_adaptive_min_samples": -1},
    {"viewport_adaptive_min_samples": 4097},
):
    try:
        configure_cycles_sampling(scene, **kwargs)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Expected ValueError for {kwargs}")


print("Cycles Sampling integration test: PASS")
