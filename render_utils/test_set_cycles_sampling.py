import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


import bpy

from set_cycles_sampling import configure_cycles_sampling


scene = bpy.context.scene

assert hasattr(scene, "cycles")

cycles = scene.cycles
rna = cycles.bl_rna

assert "samples" in rna.properties
assert "preview_samples" in rna.properties
assert "time_limit" in rna.properties


samples_prop = rna.properties["samples"]
preview_samples_prop = rna.properties["preview_samples"]
time_limit_prop = rna.properties["time_limit"]


assert samples_prop.type == "INT"
assert preview_samples_prop.type == "INT"
assert time_limit_prop.type == "FLOAT"


configure_cycles_sampling(
    scene,
    render_samples=512,
    viewport_samples=64,
    time_limit=300.0,
)


assert scene.cycles.samples == 512
assert scene.cycles.preview_samples == 64
assert scene.cycles.time_limit == 300.0


configure_cycles_sampling(
    scene,
    viewport_samples=0,
    time_limit=0.0,
)


assert scene.cycles.preview_samples == 0
assert scene.cycles.time_limit == 0.0


print("Cycles Sampling integration test: PASS")
