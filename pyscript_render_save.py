import bpy
import shutil
from pathlib import Path
from datetime import datetime

DRIVE_ROOT = Path("/content/drive/My Drive/code/output")

# Name this render uniquely, e.g. based on the .blend file + timestamp.
render_name = f"{bpy.path.basename(bpy.data.filepath).rsplit('.', 1)[0]}_{datetime.now():%Y%m%d_%H%M%S}"
drive_dir = DRIVE_ROOT / render_name
drive_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
original_frame = scene.frame_current

# Render into local storage first.
local_dir = Path("/tmp/blender-frames") / render_name
local_dir.mkdir(parents=True, exist_ok=True)

for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)

    # Example: /tmp/blender-frames/<render>/frame_0001.png
    local_file = local_dir / f"frame_{frame:04d}.png"
    scene.render.filepath = str(local_file)

    print(f"Rendering frame {frame}/{scene.frame_end}...")
    bpy.ops.render.render(write_still=True)

    if not local_file.exists():
        raise RuntimeError(f"Render failed: {local_file}")

    drive_file = drive_dir / local_file.name
    shutil.copy2(local_file, drive_file)
    local_file.unlink()

    print(f"Saved: {drive_file}")

scene.frame_set(original_frame)

print(f"\nRender complete: {drive_dir}")
