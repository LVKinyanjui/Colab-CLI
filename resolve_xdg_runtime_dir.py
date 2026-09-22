import os
from pathlib import Path

runtime_dir = Path(f"/tmp/blender-runtime-{os.environ['USER']}")
runtime_dir.mkdir(mode=0o700, exist_ok=True)
runtime_dir.chmod(0o700)

os.environ["XDG_RUNTIME_DIR"] = str(runtime_dir)

print(f"XDG_RUNTIME_DIR={runtime_dir}")
