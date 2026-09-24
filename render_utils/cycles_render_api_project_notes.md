# Cycles Render API Project Notes

## 1. Project purpose

This project is building a small, reliable Python configuration layer for Blender's Cycles Render Properties so that render settings can be controlled programmatically in **headless Blender** without requiring the Blender UI, a Properties editor, or simulated mouse/keyboard interaction.

The immediate motivation came from the need to configure the settings represented by the **Render Properties** panels from scripts used in a command-line / batch rendering workflow.

The core principle is:

> Use Blender's own RNA/data API to configure the values represented by the UI, rather than automating the UI itself.

The eventual scope is the complete Cycles Render Properties / Render tab, but the work is being implemented incrementally and tested after every feature group.

---

## 2. Why the project started with panel introspection

The original question was whether Blender's Python API allowed us to interact programmatically with the **exact controls visible in existing Blender panels**.

The Blender API exposes `bpy.types.Panel`, panel metadata, `draw()`, `layout`, panel hierarchy, etc., but it does **not** expose a DOM-like persistent hierarchy of rendered buttons/widgets that can simply be traversed and clicked.

This led to an important distinction:

```text
Existing Blender panel
        |
        +--> Panel class / metadata
        |
        +--> draw() implementation
        |
        +--> UILayout calls
        |
        +--> underlying RNA property / operator
```

The useful automation target is therefore the **underlying RNA property or operator**, not the rendered widget.

---

## 3. The experimental panel-introspection breakthrough

A recorder/fake `UILayout` was written to execute existing panel `draw()` methods without rendering the UI. The recorder captured calls such as:

```python
layout.prop(data, "tile_size")
layout.prop(scene.render, "threads")
layout.operator("render.generate_texture_cache")
```

and resolved the actual data owners and current values.

This proved that Blender's existing UI code can serve as a **map from human-visible controls to underlying RNA properties**.

A Blender 3.6.9 experiment against the Cycles Performance panel successfully discovered controls such as:

```text
Threads
    Threads Mode     -> scene.render.threads_mode
    Threads          -> scene.render.threads

Memory
    Use Tiling       -> scene.cycles.use_auto_tile   [legacy in 3.6]
    Tile Size        -> scene.cycles.tile_size

Final Render
    Persistent Data  -> scene.render.use_persistent_data

Viewport
    Pixel Size       -> scene.render.preview_pixel_size
```

It also demonstrated conditional panel behavior. For example, the Acceleration Structure panel exposed different controls depending on the CPU/Embree state.

This was important because the recorder captured **what the panel actually constructed under the current state**, rather than merely listing every property mentioned somewhere in the source code.

The experiment established the technique, but the production implementation does **not** need to dynamically introspect panels at runtime for the current project. Instead, the discovered mappings are being encoded in explicit schemas and tested directly against Blender RNA.

---

## 4. Scope decision

The project was deliberately narrowed from a generic Blender UI automation framework to a focused Cycles Render Properties configuration API.

Current implementation philosophy:

1. Do not simulate UI clicks.
2. Do not depend on a Properties editor existing.
3. Configure `scene.render`, `scene.cycles`, and eventually other relevant Blender data blocks directly.
4. Keep the API user-facing and semantic rather than exposing raw Blender property names everywhere.
5. Validate against Blender RNA metadata whenever running inside Blender.
6. Maintain explicit versioned schemas.
7. Add features one section at a time.
8. Test every addition with both mocks and Blender integration tests.

---

## 5. Version strategy

Two Blender versions are relevant:

### Primary integration target

**Blender 5.2 LTS**

The actual production implementation is being developed and validated against Blender 5.2, currently tested on **Blender 5.2.2 LTS**.

### Compatibility target

**Blender 3.6**

Blender 3.6 support is being preserved where a real property/API difference exists.

This version distinction is intentionally lightweight.

The project does **not** have a general compatibility translation framework. Instead, schemas are explicitly keyed by Blender major/minor versions:

```python
SAMPLING_SCHEMAS = {
    (3, 6): {...},
    (5, 2): {...},
}
```

Blender 5.2 is the canonical schema. Older schemas exist only to describe known compatibility differences.

When a future version is encountered without a schema, the current implementation raises an explicit unsupported-version error rather than silently guessing.

---

## 6. The complete intended Render-tab roadmap

The long-term target is the Cycles Render Properties / Render tab, organized by its major sections.

Planned sections:

```text
Cycles Render Properties
|
+-- Render
+-- Sampling
+-- Light Paths
+-- Volumes
+-- Subdivision
+-- Curves
+-- Simplify
+-- Motion Blur
+-- Film
+-- Performance
+-- Grease Pencil
```

The project is **not** implementing all of these simultaneously.

Current rollout principle:

```text
schema
  -> implementation
  -> mock tests
  -> Blender integration test
  -> regression suite
  -> next feature group
```

Sampling is intentionally being implemented before the other major groups because it has the greatest direct effect on the rendering process and is especially important to the workflow.

---

## 7. Current implementation state

The current completed Sampling slice contains:

### Core Sampling

```text
render_samples
viewport_samples
time_limit
```

### Adaptive Sampling

```text
adaptive_sampling
adaptive_threshold
adaptive_min_samples

viewport_adaptive_sampling
viewport_adaptive_threshold
viewport_adaptive_min_samples
```

The implementation maps these public API parameters to Blender's Cycles RNA properties.

Canonical 5.2 mappings:

| Public API | Blender RNA |
|---|---|
| `render_samples` | `scene.cycles.samples` |
| `viewport_samples` | `scene.cycles.preview_samples` |
| `time_limit` | `scene.cycles.time_limit` |
| `adaptive_sampling` | `scene.cycles.use_adaptive_sampling` |
| `adaptive_threshold` | `scene.cycles.adaptive_threshold` |
| `adaptive_min_samples` | `scene.cycles.adaptive_min_samples` |
| `viewport_adaptive_sampling` | `scene.cycles.use_preview_adaptive_sampling` |
| `viewport_adaptive_threshold` | `scene.cycles.preview_adaptive_threshold` |
| `viewport_adaptive_min_samples` | `scene.cycles.preview_adaptive_min_samples` |

Blender's own RNA metadata is used as the runtime authority for types and hard bounds whenever available.

---

## 8. Current public API shape

The main function is conceptually:

```python
configure_cycles_sampling(
    scene,
    *,
    render_samples=None,
    viewport_samples=None,
    time_limit=None,
    adaptive_sampling=None,
    adaptive_threshold=None,
    adaptive_min_samples=None,
    viewport_adaptive_sampling=None,
    viewport_adaptive_threshold=None,
    viewport_adaptive_min_samples=None,
)
```

### Important API convention: `None`

`None` means:

> Do not modify this setting.

It does **not** mean "set Blender's property to null" and it is not treated as a Blender value.

This is crucial for safe modification of existing `.blend` files.

For example:

```python
configure_cycles_sampling(
    scene,
    render_samples=512,
)
```

changes only render samples.

### Blender semantic zero values remain explicit

Some Blender values use `0` meaningfully:

```text
viewport_samples = 0
    -> indefinite viewport sampling

time_limit = 0.0
    -> disable time limit

adaptive_threshold = 0.0
    -> Blender's automatic threshold behavior

adaptive_min_samples = 0
    -> Blender's automatic minimum
```

These must not be confused with `None`.

---

## 9. Result semantics

The setter returns a result object containing changes and unchanged requested values.

The intended semantics are:

```text
changed
    explicitly requested AND previous value differed

unchanged
    explicitly requested AND previous value already matched

omitted / None
    not reported
```

This distinction was important enough to correct after a real integration-test failure.

It makes logs and future batch-render diagnostics much clearer.

---

## 10. Validation model

The validation design has two layers.

### Schema-level validation

Used even in mock tests and outside Blender.

The schema specifies:

- expected Python type
- minimum
- maximum where appropriate
- Blender target object
- Blender RNA attribute

### Blender RNA validation

When actually running inside Blender, the implementation inspects:

```python
scene.cycles.bl_rna.properties
```

and uses Blender's own property metadata where available, including:

- RNA type
- `hard_min`
- `hard_max`
- later, enum identifiers for enum properties

This is preferable to inventing independent hard-coded Blender rules.

The rule is:

> Blender RNA should be the final authority for whether a value is actually legal for the running Blender build.

The schema remains the fallback and the public documentation layer.

---

## 11. Atomic configuration behavior

Validation occurs before mutation.

This is deliberate.

For example, if a call contains three settings and the third is invalid:

```python
configure_cycles_sampling(
    scene,
    render_samples=512,
    viewport_samples=64,
    adaptive_min_samples=999999,
)
```

the function should reject the request without leaving the scene partially modified.

This property is explicitly covered by the mock tests.

---

## 12. Testing architecture

There are two complementary test layers.

### Mock/unit tests

Run with ordinary Python/pytest.

These test:

- public API behavior
- schema selection
- type validation
- range validation
- result semantics
- atomicity
- assignment behavior
- version handling

Mocks represent the minimal `scene.cycles` object necessary for each test.

### Blender integration tests

Run through Blender's embedded Python:

```bash
blender -b -P test_cycles_sampling_blender.py
```

These verify:

- the actual Blender RNA properties exist
- schema mappings match the running Blender build
- RNA types are correct
- values can actually be assigned
- values round-trip back through Blender
- Blender's runtime numeric bounds are honored

The Blender integration test is intentionally separate from ordinary pytest execution.

---

## 13. Blender Python import-path lesson

A significant practical issue was encountered when the Blender integration test attempted:

```python
from set_cycles_sampling import configure_cycles_sampling
```

Blender's embedded Python did not automatically include the project directory on `sys.path`, despite the shell's current working directory being the directory containing the module.

The diagnostic showed:

```text
CWD:
/home/jovian/Projects/Colab-CLI/render_utils

EXPECTED:
/home/jovian/Projects/Colab-CLI/render_utils/set_cycles_sampling.py

EXISTS:
True

IMPORTER:
None
```

But explicitly adding the directory worked:

```python
sys.path.insert(0, SCRIPT_DIR)
```

The correct integration-test pattern is therefore:

```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
```

### Important conclusion

Do **not** install the project into Blender's Python environment just to solve this.

The current project intentionally has no external Python dependencies and should remain a collection of local Python modules that are imported explicitly by Blender test scripts.

This is simpler and better suited to headless render environments.

---

## 14. Important Blender shutdown pitfall

An early experimental script ended with:

```python
raise SystemExit(main())
```

When run inside Blender, this caused Blender itself to exit after the script completed.

For Blender-hosted scripts, do not use the normal standalone pattern if it causes `SystemExit` to escape into Blender.

Prefer:

```python
if __name__ == "__main__":
    main()
```

and simply ignore the return value, or handle script termination explicitly without raising `SystemExit` into the Blender process.

This was the reason an early panel-introspection experiment appeared to "make the GUI exit" despite completing its diagnostics successfully.

---

## 15. Floating-point round-trip pitfall

A Blender 5.2.2 integration test initially failed on:

```python
assert cycles.adaptive_threshold == 0.01
```

The mapping itself was correct. Blender's RNA float storage is single precision, so reading a value back can produce a value numerically very close to, but not bit-for-bit identical to, the Python literal.

The integration suite therefore uses tolerance for Blender FLOAT round-trips, for example:

```python
math.isclose(
    cycles.adaptive_threshold,
    0.01,
    rel_tol=0.0,
    abs_tol=1e-6,
)
```

Integers and booleans continue to use exact equality.

This should remain a standard rule for future Blender integration tests:

```text
RNA INT / BOOLEAN -> exact comparison
RNA FLOAT         -> tolerant comparison
```

---

## 16. Version-specific property differences are expected

The original Performance investigation used Blender 3.6.9 and found properties that have changed or disappeared by 5.2.

Examples:

### Legacy tiling

Blender 3.6 had:

```python
scene.cycles.use_auto_tile
```

The current Cycles UI no longer treats this as an ordinary 5.2 Performance control.

### Texture cache

The correct 5.2 mapping is:

```python
scene.render.use_texture_cache
scene.render.use_auto_generate_texture_cache
```

not a guessed property on `scene.cycles`.

### Compositor denoising names

Current 5.2 names use:

```python
scene.render.compositor_denoise_device
scene.render.compositor_denoise_preview_quality
scene.render.compositor_denoise_final_quality
```

The schema must therefore not blindly carry older or guessed names forward.

General rule:

> When adding a new version to the project, inspect that Blender version's actual RNA and UI source rather than assuming property names are stable.

---

## 17. Why explicit versioned schemas are preferred

The project should not evolve into a complicated compatibility framework prematurely.

The current strategy is enough:

```text
Blender version
      |
      v
select explicit schema
      |
      v
map public name -> RNA property
      |
      v
validate against live RNA
```

If Blender 5.3 changes a property, we can add `(5, 3)` when needed.

We should only add a version-specific difference when an actual Blender difference exists.

---

## 18. Presets: intended architecture

Presets will be added later, after the underlying property APIs are stable.

The intended layering is:

```text
Scene preset
    |
    v
public configuration API
    |
    v
schema / RNA validation
    |
    v
Blender scene
```

Presets are recommendations/workflow profiles, not Blender's canonical truth.

Potential future examples include:

```text
OUTDOOR_FAST
ARCHITECTURAL_INTERIOR
PRODUCT
GLASS_HEAVY
VOLUMETRIC
ANIMATION
LOW_MEMORY
FAST_PREVIEW
HIGH_QUALITY
```

The project should avoid presenting heuristic presets as universally optimal settings.

---

## 19. Sampling heuristics that informed the design

Some practical heuristics were collected for future presets, including:

- 256–1024 render samples as a common production starting region
- lower viewport sample counts for interactive work
- adaptive threshold around `0.01` as a useful starting point
- lower thresholds for higher convergence requirements
- denoising as a major quality/time optimization
- different behavior for architectural interiors, outdoor scenes, glass-heavy scenes, etc.
- higher sample counts for difficult caustic/refraction situations

These are **preset heuristics only**. They are not API validity constraints.

The configuration API should validate:

```text
is the value legal?
```

not:

```text
is this the best setting for the scene?
```

Those concerns must remain separate.

---

## 20. Important UI/API distinction for future features

Some UI controls are ordinary RNA properties.

Some are:

- conditional on another setting
- hardware-dependent
- version-dependent
- operators rather than properties
- structured data rather than a scalar property

The API should not blindly reproduce UI enable/disable behavior as validation failure.

Example:

```python
adaptive_threshold = 0.01
adaptive_sampling = False
```

Both values are individually valid RNA settings, even though the UI may gray the threshold control when adaptive sampling is disabled.

The project should distinguish:

```text
VALUE INVALID
```

from:

```text
VALUE VALID BUT CURRENTLY INACTIVE / CONDITIONAL
```

This distinction becomes increasingly important for Denoising, Path Guiding, Light Paths, and device-dependent controls.

---

## 21. Planned Sampling rollout after the current pause

Sampling is being implemented before the other Render-tab sections.

Current status:

```text
Sampling
|
+-- Core                      COMPLETE
|   +-- Render Samples
|   +-- Viewport Samples
|   +-- Time Limit
|
+-- Adaptive Sampling         COMPLETE
|   +-- Render
|   |   +-- Enable
|   |   +-- Threshold
|   |   +-- Min Samples
|   |
|   +-- Viewport
|       +-- Enable
|       +-- Threshold
|       +-- Min Samples
|
+-- Denoising                 NEXT
+-- Path Guiding
+-- Lights
+-- Advanced
```

The Sampling section should be completed before moving to Light Paths or other Render Properties.

---

## 22. Future Denoising considerations

Denoising is the next major Sampling subsection.

It is more complicated than the current slices because it introduces:

- render vs viewport denoising
- multiple enum properties
- hardware-dependent denoiser availability
- different behavior for OpenImageDenoise and OptiX
- conditional prefilter/quality controls
- GPU usage

The implementation should therefore rely heavily on live RNA enum discovery rather than a permanently hard-coded enum list.

For example, a future schema may say:

```text
den oiser:
    target = cycles
    attribute = denoiser
    type = enum
```

and obtain valid enum identifiers from Blender at runtime.

---

## 23. Future full Render-tab schema

The eventual schema will likely have groups such as:

```python
CYCLES_RENDER_SCHEMAS = {
    "render": {...},
    "sampling": {...},
    "light_paths": {...},
    "volumes": {...},
    "subdivision": {...},
    "curves": {...},
    "simplify": {...},
    "motion_blur": {...},
    "film": {...},
    "performance": {...},
    "grease_pencil": {...},
}
```

The important design rule is that each group should be implementable and testable independently.

---

## 24. Current files / project structure

The working render utility area currently follows this general organization:

```text
render_utils/
|
+-- set_cycles_performance.py
+-- set_cycles_sampling.py
|
+-- test_set_cycles_performance_mock.py
+-- test_set_cycles_sampling.py
+-- test_cycles_sampling_blender.py
|
+-- render_scheduler.sh
+-- render_terminate.sh
+-- render_job.sh
+-- render_simple.sh
```

The Sampling rollout package additionally contains a README describing the test commands and integration target.

---

## 25. Recommended testing procedure for future features

For every new property group:

### Step 1 — Identify mapping

Determine:

```text
Public API name
        -> Blender RNA owner
        -> Blender RNA property
```

### Step 2 — Confirm 5.2 RNA

Run a Blender 5.2 integration probe if necessary.

Inspect:

```python
scene.<target>.bl_rna.properties["<property>"]
```

### Step 3 — Add version schema

Add the 5.2 definition and only add a 3.6 definition difference if needed.

### Step 4 — Add mock tests

Cover:

- valid values
- boundary values
- invalid values
- invalid types
- omitted values
- unchanged values
- atomicity

### Step 5 — Add Blender integration tests

Check:

- property exists
- RNA type is correct
- RNA bounds are correct
- setter succeeds
- value round-trips

For floats, use tolerance.

### Step 6 — Run the full regression suite

Do not test only the new section.

The complete existing suite should continue passing before moving on.

### Step 7 — Run Blender 5.2 integration

Primary command:

```bash
blender -b -P test_cycles_sampling_blender.py
```

or the equivalent integration test for the new section.

### Step 8 — Only then add presets

Presets should consume stable public APIs, not bypass them.

---

## 26. Pitfalls to remember

### Blender is not your shell Python

Blender ships an embedded Python environment.

Do not assume your shell virtualenv or `PYTHONPATH` is automatically used by Blender.

### Blender does not automatically make the test script directory importable

Use the explicit `SCRIPT_DIR` / `sys.path.insert(0, SCRIPT_DIR)` pattern in integration scripts.

### Avoid `SystemExit` inside Blender

Do not use:

```python
raise SystemExit(main())
```

unless there is a deliberate reason to terminate Blender itself.

### Do not guess RNA names

Always verify them against the target Blender version.

### Do not treat UI visibility as property validity

A grayed/conditional UI control can still correspond to a valid RNA property.

### Do not treat heuristics as validation rules

A setting can be technically valid even if a preset considers it poor for a particular scene.

### Do not compare Blender FLOAT values with exact equality

Use an appropriate tolerance.

### Validate before mutating

Configuration should be atomic whenever practical.

### Do not silently ignore configuration errors in production mode

Unknown settings and invalid values should normally fail loudly in headless render workflows. Silent misconfiguration is worse than a failed job.

### Avoid premature overengineering

Keep version support explicit and small until an actual version difference requires more machinery.

---

## 27. Project philosophy

The overall project can be summarized in five principles:

1. **Use Blender's data/RNA API, not UI automation.**
2. **Treat Blender 5.2 LTS as the canonical target.**
3. **Preserve 3.6 compatibility through explicit schemas, not guesswork.**
4. **Use Blender RNA metadata as the runtime authority for actual property constraints.**
5. **Grow the API through small, independently tested feature slices.**

The goal is not merely to make a script that can set a few Cycles values.

The goal is to build a dependable configuration layer that can eventually express the important Cycles Render Properties in a clean, automation-friendly interface while remaining faithful to the Blender version actually running the render.

---

## 28. Current milestone

At the point this document was created:

- Panel introspection technique: **proven**
- Performance mapping: **proven / implemented as the initial prototype**
- Blender 3.6 integration environment: **proven**
- Blender 5.2 integration environment: **proven**
- Core Sampling: **implemented and tested**
- Adaptive Sampling: **implemented and tested**
- Mock/regression suite: **passing**
- Blender 5.2.2 integration: **passing**
- Next feature: **Denoising**
- Current work status: **paused intentionally**

This is the baseline to preserve before continuing the rollout.
