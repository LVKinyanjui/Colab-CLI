# Cycles Sampling rollout — Core + Adaptive Sampling

Canonical integration target: **Blender 5.2 LTS**  
Compatibility schema: **Blender 3.6**

## Files

- `set_cycles_sampling.py` — versioned schemas, validation, mutation API.
- `test_set_cycles_sampling.py` — pure-Python mock/unit test suite.
- `test_cycles_sampling_blender.py` — Blender integration test. It adds its own directory to `sys.path` and works under Blender's embedded Python.

## Mock suite

From this directory:

```bash
pytest -q
```

The Blender integration test is skipped during ordinary pytest collection because `bpy` is unavailable outside Blender.

## Blender integration

From the directory containing the files:

```bash
blender -b -P test_cycles_sampling_blender.py
```

Run this with **Blender 5.2 LTS** for the primary integration test. Blender 3.6 is retained as an explicit compatibility path.
