# Cycles Sampling rollout

Canonical integration target: **Blender 5.2 LTS**  
Compatibility target: **Blender 3.6**

Implemented:
- Core sampling
  - Render Samples
  - Viewport Samples
  - Time Limit
- Adaptive Sampling
  - Render adaptive sampling
  - Viewport adaptive sampling

## Mock / unit tests

```bash
pytest -q
```

## Blender integration test

Run from this directory with the target Blender installation:

```bash
blender -b -P test_cycles_sampling_blender.py
```

The integration test adds its own directory to `sys.path`, because Blender's
embedded Python may not include the working directory automatically.

The public result semantics are:

- `changed`: explicitly requested settings whose values changed.
- `unchanged`: explicitly requested settings whose values already matched.
- omitted (`None`) settings are not reported.
