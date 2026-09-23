"""
set_cycles_performance.py

Standalone headless script to configure Cycles Performance settings.
Zero dependencies outside Blender's built-in Python.

Usage:
  blender -b scene.blend -P set_cycles_performance.py -f 1 -- [OPTIONS]
"""

import sys
import argparse
import bpy


# ---------------------------------------------------------------------------
# 1. HARDCODED VERSION-AWARE SCHEMA
# ---------------------------------------------------------------------------
# Derived from our introspection probe results on Blender 3.6 and 5.1.2.
# Targets:
#   - "render" -> context.scene.render
#   - "cycles" -> context.scene.cycles

BLENDER_VERSION = bpy.app.version  # e.g. (3, 6, 9) or (5, 1, 2)

PERFORMANCE_SCHEMA = {
    # Threads (RenderSettings)
    "threads_mode": {
        "target": "render",
        "attr": "threads_mode",
        "type": str,
        "choices": ["AUTO", "FIXED"],
        "help": "Thread count mode: AUTO or FIXED",
    },
    "threads": {
        "target": "render",
        "attr": "threads",
        "type": int,
        "help": "Number of CPU threads (only effective when threads_mode is FIXED)",
    },

    # Memory / Tiling (CyclesRenderSettings)
    "tile_size": {
        "target": "cycles",
        "attr": "tile_size",
        "type": int,
        "help": "Render tile size in pixels (e.g. 256, 512, 2048)",
    },
    "use_auto_tile": {
        "target": "cycles",
        "attr": "use_auto_tile",
        "type": bool,
        "max_version": (4, 0, 0),  # Present in 3.6, removed/integrated in 4.x+
        "help": "Enable auto-tiling (Blender 3.x only)",
    },

    # Final Render (RenderSettings)
    "persistent_data": {
        "target": "render",
        "attr": "use_persistent_data",
        "type": bool,
        "help": "Keep render data in memory across frames (True/False)",
    },

    # Viewport / Preview (RenderSettings)
    "preview_pixel_size": {
        "target": "render",
        "attr": "preview_pixel_size",
        "type": str,
        "choices": ["AUTO", "1", "2", "4", "8"],
        "help": "Pixel downsampling for viewport rendering",
    },

    # Compositor (RenderSettings) - Added in modern Blender
    "compositor_device": {
        "target": "render",
        "attr": "compositor_device",
        "type": str,
        "choices": ["CPU", "GPU"],
        "min_version": (4, 0, 0),
        "help": "Compositor execution device (Blender 4.x+)",
    },

    # Acceleration Structure (CyclesRenderSettings)
    "spatial_splits": {
        "target": "cycles",
        "attr": "debug_use_spatial_splits",
        "type": bool,
        "help": "Use spatial splits for BVH generation",
    },
    "compact_bvh": {
        "target": "cycles",
        "attr": "debug_use_compact_bvh",
        "type": bool,
        "help": "Use compact BVH to reduce memory footprint",
    },
}


# ---------------------------------------------------------------------------
# 2. FAST DIRECT RNA SETTER (NO INTROSPECTION OVERHEAD)
# ---------------------------------------------------------------------------

def apply_performance_settings(scene: bpy.types.Scene, settings: dict):
    """
    Applies performance settings directly to scene RNA data in microseconds.
    Respects Blender version boundaries and validates targets.
    """
    render_data = scene.render
    cycles_data = scene.cycles

    targets = {
        "render": render_data,
        "cycles": cycles_data,
    }

    print(f"\n[*] Applying Cycles performance settings (Blender {bpy.app.version_string}):")

    for key, val in settings.items():
        if key not in PERFORMANCE_SCHEMA:
            print(f"  [!] Warning: Unknown property '{key}', skipping.")
            continue

        spec = PERFORMANCE_SCHEMA[key]

        # Version gating
        if "min_version" in spec and BLENDER_VERSION < spec["min_version"]:
            print(f"  [-] Skipped '{key}': requires Blender >="
                  f" {'.'.join(map(str, spec['min_version']))}")
            continue

        if "max_version" in spec and BLENDER_VERSION >= spec["max_version"]:
            print(f"  [-] Skipped '{key}': deprecated in Blender >="
                  f" {'.'.join(map(str, spec['max_version']))}")
            continue

        target_obj = targets[spec["target"]]
        attr_name = spec["attr"]

        if not hasattr(target_obj, attr_name):
            print(f"  [!] Warning: '{attr_name}' not found on {spec['target']}, skipping.")
            continue

        # Direct in-place RNA assignment
        setattr(target_obj, attr_name, val)
        print(f"  [+] Set {spec['target']}.{attr_name} = {val!r}")


# ---------------------------------------------------------------------------
# 3. CLI ARGUMENT PARSER (SAFE FOR BACKGROUND BLENDER)
# ---------------------------------------------------------------------------

def parse_cli_args():
    """Parses arguments passed after the double-dash '--'."""
    argv = sys.argv
    if "--" not in argv:
        return {}, None

    custom_args = argv[argv.index("--") + 1:]

    parser = argparse.ArgumentParser(
        description="Set Cycles Performance parameters for headless rendering."
    )

    # Automatically generate CLI flags from the schema
    for key, spec in PERFORMANCE_SCHEMA.items():
        flag = f"--{key.replace('_', '-')}"
        
        if spec["type"] == bool:
            parser.add_argument(
                flag,
                type=lambda x: str(x).lower() in ("true", "1", "yes"),
                help=spec.get("help")
            )
        elif "choices" in spec:
            parser.add_argument(
                flag,
                type=str,
                choices=spec["choices"],
                help=spec.get("help")
            )
        else:
            parser.add_argument(
                flag,
                type=spec["type"],
                help=spec.get("help")
            )

    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional filepath to save the modified .blend file"
    )

    parsed, _ = parser.parse_known_args(custom_args)
    parsed_dict = vars(parsed)

    save_path = parsed_dict.pop("save", None)
    # Return only flags explicitly provided by the user
    active_settings = {k: v for k, v in parsed_dict.items() if v is not None}

    return active_settings, save_path


# ---------------------------------------------------------------------------
# 4. ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    scene = bpy.context.scene

    # Always ensure the active engine is Cycles
    scene.render.engine = 'CYCLES'

    settings, save_path = parse_cli_args()

    if settings:
        apply_performance_settings(scene, settings)
    else:
        print("[*] No custom flags supplied. Printing current values:")
        for key, spec in PERFORMANCE_SCHEMA.items():
            target_obj = scene.render if spec["target"] == "render" else scene.cycles
            attr = spec["attr"]
            val = getattr(target_obj, attr, "<NOT AVAILABLE>")
            print(f"    {key:<20} ({spec['target']}.{attr}) = {val!r}")

    if save_path:
        bpy.ops.wm.save_as_mainfile(filepath=save_path)
        print(f"[+] Saved updated .blend to: {save_path}")


if __name__ == "__main__":
    main()
