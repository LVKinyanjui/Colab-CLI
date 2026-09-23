"""
set_cycles_performance.py (Updated with complete 5.2 options + Presets)
"""

import sys
import argparse
import bpy

BLENDER_VERSION = bpy.app.version

# ---------------------------------------------------------------------------
# 1. COMPLETE EXHAUSTIVE SCHEMA
# ---------------------------------------------------------------------------
PERFORMANCE_SCHEMA = {
    # Final Render
    "persistent_data": {
        "target": "render", "attr": "use_persistent_data", "type": bool
    },

    # Memory / Tiling
    "tile_size": {
        "target": "cycles", "attr": "tile_size", "type": int
    },
    "use_auto_tile": {
        "target": "cycles", "attr": "use_auto_tile", "type": bool, "max_version": (4, 0, 0)
    },

    # Texture Cache (Blender 5.2+)
    "use_texture_cache": {
        "target": "cycles", "attr": "use_texture_cache", "type": bool, "min_version": (5, 2, 0)
    },
    "texture_cache_auto_generate": {
        "target": "cycles", "attr": "texture_cache_auto_generate", "type": bool, "min_version": (5, 2, 0)
    },

    # Acceleration Structure
    "spatial_splits": {
        "target": "cycles", "attr": "debug_use_spatial_splits", "type": bool
    },
    "compact_bvh": {
        "target": "cycles", "attr": "debug_use_compact_bvh", "type": bool
    },
    "curves_bvh": {
        "target": "cycles", "attr": "debug_use_hair_bvh", "type": bool
    },
    "bvh_time_steps": {
        "target": "cycles", "attr": "debug_bvh_time_steps", "type": int
    },

    # Compositor
    "compositor_device": {
        "target": "render", "attr": "compositor_device", "type": str, "min_version": (4, 0, 0)
    },
    "compositor_precision": {
        "target": "render", "attr": "compositor_precision", "type": str, "min_version": (4, 0, 0)
    },
    "compositor_denoising_device": {
        "target": "render", "attr": "compositor_denoising_device", "type": str, "min_version": (5, 2, 0)
    },
    "compositor_denoising_final_quality": {
        "target": "render", "attr": "compositor_denoising_final_quality", "type": str, "min_version": (5, 2, 0)
    },

    # Threads & Viewport
    "threads_mode": {
        "target": "render", "attr": "threads_mode", "type": str
    },
    "threads": {
        "target": "render", "attr": "threads", "type": int
    },
    "preview_pixel_size": {
        "target": "render", "attr": "preview_pixel_size", "type": str
    },
}

# ---------------------------------------------------------------------------
# 2. OFFICIAL PRESETS (SPEED VS VRAM TRADEOFFS)
# ---------------------------------------------------------------------------
PRESETS = {
    # Maximize VRAM usage to render as fast as possible
    "FASTER_RENDER": {
        "persistent_data": True,             # Keep BVH & meshes in VRAM across frames
        "tile_size": 2048,                   # Full buffer in VRAM (bypasses tile overhead)
        "spatial_splits": True,              # Faster ray traversal at the cost of VRAM
        "compact_bvh": False,                # Uncompressed BVH in memory (fastest)
        "curves_bvh": True,                  # Specialized curve acceleration in VRAM
        "compositor_device": "GPU",          # Execute compositing on VRAM/GPU
        "compositor_precision": "FULL",
        "use_texture_cache": False,          # Keep raw textures in VRAM (fastest if VRAM fits)
    },

    # Minimize VRAM usage when rendering large scenes or limited GPUs
    "LOWER_MEMORY": {
        "persistent_data": False,            # Flush VRAM immediately after render
        "tile_size": 512,                    # Break image into smaller tiles to fit VRAM
        "spatial_splits": False,             # Reduce BVH memory usage
        "compact_bvh": True,                 # Compress BVH structures
        "curves_bvh": False,                 # Fallback to standard BVH
        "compositor_device": "CPU",          # Free GPU VRAM from compositing load
        "use_texture_cache": True,           # Stream textures on demand
    },

    # Blender defaults (balanced)
    "DEFAULT": {
        "persistent_data": False,
        "tile_size": 2048,
        "spatial_splits": False,
        "compact_bvh": False,
        "curves_bvh": True,
        "compositor_device": "GPU",
        "compositor_precision": "AUTO",
        "use_texture_cache": False,
    }
}


def apply_settings(scene: bpy.types.Scene, settings: dict):
    targets = {
        "render": scene.render,
        "cycles": scene.cycles,
    }

    for key, val in settings.items():
        if key not in PERFORMANCE_SCHEMA:
            continue

        spec = PERFORMANCE_SCHEMA[key]
        if "min_version" in spec and BLENDER_VERSION < spec["min_version"]:
            continue
        if "max_version" in spec and BLENDER_VERSION >= spec["max_version"]:
            continue

        target_obj = targets[spec["target"]]
        attr_name = spec["attr"]

        if hasattr(target_obj, attr_name):
            setattr(target_obj, attr_name, val)
            print(f"  [+] Set {spec['target']}.{attr_name} = {val!r}")


def parse_args():
    argv = sys.argv
    if "--" not in argv:
        return None, {}

    custom_args = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=["FASTER_RENDER", "LOWER_MEMORY", "DEFAULT"],
                        help="Apply one of the official Performance presets")
    
    # Custom overrides
    for key in PERFORMANCE_SCHEMA:
        parser.add_argument(f"--{key.replace('_', '-')}", type=str, default=None)

    parsed, _ = parser.parse_known_args(custom_args)
    parsed_dict = vars(parsed)
    preset = parsed_dict.pop("preset", None)

    # Filter overrides
    overrides = {k: v for k, v in parsed_dict.items() if v is not None}
    return preset, overrides


def main():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'

    preset, overrides = parse_args()

    # 1. Apply Preset if selected
    if preset:
        print(f"\n[*] Applying Performance Preset: {preset}")
        apply_settings(scene, PRESETS[preset])

    # 2. Apply individual flag overrides on top of the preset
    if overrides:
        print(f"\n[*] Applying Overrides:")
        # Convert string bools/ints where appropriate
        converted = {}
        for k, v in overrides.items():
            if v.lower() in ("true", "yes", "1"):
                converted[k] = True
            elif v.lower() in ("false", "no", "0"):
                converted[k] = False
            elif v.isdigit():
                converted[k] = int(v)
            else:
                converted[k] = v
        apply_settings(scene, converted)


if __name__ == "__main__":
    main()
