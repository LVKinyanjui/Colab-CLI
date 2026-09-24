#!/usr/bin/env python3
"""Mock tests for set_cycles_performance.py.

These tests deliberately do not require Blender. They exercise the schema,
validation, application layer, CLI parsing, and the corrected Blender 5.2
property mappings using simple scene/render/cycles mocks.
"""

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("set_cycles_performance.py")
spec = importlib.util.spec_from_file_location("set_cycles_performance", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MockRender:
    def __init__(self):
        self.use_persistent_data = False
        self.use_texture_cache = True
        self.use_auto_generate_texture_cache = False
        self.compositor_device = "GPU"
        self.compositor_precision = "AUTO"
        self.compositor_denoise_device = "AUTO"
        self.compositor_denoise_preview_quality = "BALANCED"
        self.compositor_denoise_final_quality = "HIGH"
        self.threads_mode = "AUTO"
        self.threads = 8
        self.preview_pixel_size = "AUTO"
        self.engine = "CYCLES"


class MockCycles:
    def __init__(self):
        self.tile_size = 2048
        self.debug_use_spatial_splits = False
        self.debug_use_compact_bvh = False
        self.debug_use_hair_bvh = True
        self.debug_bvh_time_steps = 0
        self.device = "GPU"


class MockScene:
    def __init__(self):
        self.name = "MockScene"
        self.render = MockRender()
        self.cycles = MockCycles()


class TestPerformanceSchema(unittest.TestCase):
    VERSION = (5, 2, 0)

    def test_texture_cache_5_2_mapping(self):
        schema = module.PERFORMANCE_SCHEMA
        self.assertEqual(schema["use_texture_cache"]["target"], "render")
        self.assertEqual(schema["use_texture_cache"]["attr"], "use_texture_cache")

        self.assertEqual(
            schema["texture_cache_auto_generate"]["target"],
            "render",
        )
        self.assertEqual(
            schema["texture_cache_auto_generate"]["attr"],
            "use_auto_generate_texture_cache",
        )

    def test_compositor_denoise_names(self):
        schema = module.PERFORMANCE_SCHEMA
        self.assertEqual(
            schema["compositor_denoise_device"]["attr"],
            "compositor_denoise_device",
        )
        self.assertEqual(
            schema["compositor_denoise_preview_quality"]["attr"],
            "compositor_denoise_preview_quality",
        )
        self.assertEqual(
            schema["compositor_denoise_final_quality"]["attr"],
            "compositor_denoise_final_quality",
        )

    def test_threads_validation(self):
        module.validate_value("threads_mode", "AUTO")
        module.validate_value("threads_mode", "FIXED")
        module.validate_value("threads", 1)

        with self.assertRaises(module.ConfigurationError):
            module.validate_value("threads_mode", "INVALID")

        with self.assertRaises(module.ConfigurationError):
            module.validate_value("threads", 0)

        with self.assertRaises(module.ConfigurationError):
            module.validate_value("threads", True)


class TestApplySettings(unittest.TestCase):
    VERSION = (5, 2, 0)

    def test_core_performance_settings(self):
        scene = MockScene()

        applied = module.apply_settings(
            scene,
            {
                "threads_mode": "FIXED",
                "threads": 4,
                "tile_size": 512,
                "persistent_data": True,
            },
            blender_version=self.VERSION,
        )

        self.assertEqual(applied["threads_mode"], "FIXED")
        self.assertEqual(scene.render.threads_mode, "FIXED")
        self.assertEqual(scene.render.threads, 4)
        self.assertEqual(scene.cycles.tile_size, 512)
        self.assertTrue(scene.render.use_persistent_data)

    def test_texture_cache_settings(self):
        scene = MockScene()

        module.apply_settings(
            scene,
            {
                "use_texture_cache": False,
                "texture_cache_auto_generate": True,
            },
            blender_version=self.VERSION,
        )

        self.assertFalse(scene.render.use_texture_cache)
        self.assertTrue(scene.render.use_auto_generate_texture_cache)

    def test_compositor_settings(self):
        scene = MockScene()

        module.apply_settings(
            scene,
            {
                "compositor_device": "CPU",
                "compositor_precision": "FULL",
                "compositor_denoise_device": "GPU",
                "compositor_denoise_preview_quality": "FAST",
                "compositor_denoise_final_quality": "HIGH",
            },
            blender_version=self.VERSION,
        )

        self.assertEqual(scene.render.compositor_device, "CPU")
        self.assertEqual(scene.render.compositor_precision, "FULL")
        self.assertEqual(scene.render.compositor_denoise_device, "GPU")
        self.assertEqual(scene.render.compositor_denoise_preview_quality, "FAST")
        self.assertEqual(scene.render.compositor_denoise_final_quality, "HIGH")

    def test_invalid_setting_does_not_mutate_scene(self):
        scene = MockScene()

        with self.assertRaises(module.ConfigurationError):
            module.apply_settings(
                scene,
                {"threads": 0},
                blender_version=self.VERSION,
            )

        self.assertEqual(scene.render.threads, 8)

    def test_unsupported_5_2_setting_is_rejected_on_3_6(self):
        scene = MockScene()

        with self.assertRaises(module.ConfigurationError):
            module.apply_settings(
                scene,
                {"use_texture_cache": False},
                blender_version=(3, 6, 9),
            )

    def test_legacy_use_auto_tile_rejected_on_5_2(self):
        scene = MockScene()
        scene.cycles.use_auto_tile = True

        with self.assertRaises(module.ConfigurationError):
            module.apply_settings(
                scene,
                {"use_auto_tile": False},
                blender_version=self.VERSION,
            )

    def test_balanced_preset(self):
        scene = MockScene()

        module.apply_settings(
            scene,
            module.PRESETS["BALANCED"],
            blender_version=self.VERSION,
        )

        self.assertFalse(scene.render.use_persistent_data)
        self.assertEqual(scene.cycles.tile_size, 2048)
        self.assertFalse(scene.cycles.debug_use_spatial_splits)
        self.assertFalse(scene.cycles.debug_use_compact_bvh)
        self.assertTrue(scene.cycles.debug_use_hair_bvh)
        self.assertEqual(scene.render.compositor_device, "GPU")
        self.assertEqual(scene.render.compositor_precision, "AUTO")
        self.assertFalse(scene.render.use_texture_cache)


class TestCLI(unittest.TestCase):
    def test_parse_typed_overrides(self):
        preset, overrides = module.parse_args(
            [
                "--preset",
                "faster_render",
                "--threads-mode",
                "fixed",
                "--threads",
                "4",
                "--tile-size",
                "512",
                "--persistent-data",
                "true",
                "--preview-pixel-size",
                "2",
            ]
        )

        self.assertEqual(preset, "FASTER_RENDER")
        self.assertEqual(overrides["threads_mode"], "FIXED")
        self.assertEqual(overrides["threads"], 4)
        self.assertEqual(overrides["tile_size"], 512)
        self.assertIs(overrides["persistent_data"], True)
        self.assertEqual(overrides["preview_pixel_size"], "2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
