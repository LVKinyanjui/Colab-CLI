import pytest

from set_cycles_sampling import (
    SAMPLING_SCHEMAS,
    configure_cycles_sampling,
    get_sampling_schema,
)


class MockCycles:
    def __init__(self):
        self.samples = 128
        self.preview_samples = 16
        self.time_limit = 0.0
        self.use_adaptive_sampling = False
        self.adaptive_threshold = 0.01
        self.adaptive_min_samples = 0
        self.use_preview_adaptive_sampling = False
        self.preview_adaptive_threshold = 0.1
        self.preview_adaptive_min_samples = 0


class MockScene:
    def __init__(self):
        self.cycles = MockCycles()


def test_supported_versions_exist():
    assert (3, 6) in SAMPLING_SCHEMAS
    assert (5, 2) in SAMPLING_SCHEMAS


def test_supported_schema_lookup():
    assert get_sampling_schema((3, 6)) is SAMPLING_SCHEMAS[(3, 6)]
    assert get_sampling_schema((5, 2)) is SAMPLING_SCHEMAS[(5, 2)]


def test_unknown_schema_rejected():
    with pytest.raises(RuntimeError, match="Unsupported Blender version"):
        get_sampling_schema((5, 3))


def test_36_and_52_are_currently_equivalent():
    assert SAMPLING_SCHEMAS[(3, 6)] == SAMPLING_SCHEMAS[(5, 2)]


def test_none_means_leave_unchanged_and_is_not_reported():
    scene = MockScene()

    result = configure_cycles_sampling(scene, render_samples=512)

    assert scene.cycles.samples == 512
    assert result.unchanged == ()
    assert [change.name for change in result.changed] == ["render_samples"]


def test_explicitly_unchanged_values_are_reported():
    scene = MockScene()

    result = configure_cycles_sampling(
        scene,
        render_samples=128,
        viewport_samples=16,
        time_limit=0.0,
        adaptive_sampling=False,
    )

    assert result.changed == ()
    assert result.unchanged == (
        "render_samples",
        "viewport_samples",
        "time_limit",
        "adaptive_sampling",
    )


def test_full_sampling_configuration():
    scene = MockScene()

    result = configure_cycles_sampling(
        scene,
        render_samples=512,
        viewport_samples=64,
        time_limit=300.0,
        adaptive_sampling=True,
        adaptive_threshold=0.02,
        adaptive_min_samples=32,
        viewport_adaptive_sampling=True,
        viewport_adaptive_threshold=0.05,
        viewport_adaptive_min_samples=8,
    )

    assert scene.cycles.samples == 512
    assert scene.cycles.preview_samples == 64
    assert scene.cycles.time_limit == 300.0
    assert scene.cycles.use_adaptive_sampling is True
    assert scene.cycles.adaptive_threshold == 0.02
    assert scene.cycles.adaptive_min_samples == 32
    assert scene.cycles.use_preview_adaptive_sampling is True
    assert scene.cycles.preview_adaptive_threshold == 0.05
    assert scene.cycles.preview_adaptive_min_samples == 8
    assert len(result.changed) == 9
    assert result.unchanged == ()


@pytest.mark.parametrize("value", [1, 512, 4096])
def test_render_samples_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, render_samples=value)
    assert scene.cycles.samples == value


@pytest.mark.parametrize("value", [0, 1, 32, 64])
def test_viewport_samples_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, viewport_samples=value)
    assert scene.cycles.preview_samples == value


@pytest.mark.parametrize("value", [0.0, 1.0, 300.0])
def test_time_limit_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, time_limit=value)
    assert scene.cycles.time_limit == value


@pytest.mark.parametrize("value", [False, True])
def test_adaptive_sampling_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, adaptive_sampling=value)
    assert scene.cycles.use_adaptive_sampling is value


@pytest.mark.parametrize("value", [0.0, 0.001, 0.1, 1.0])
def test_adaptive_threshold_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, adaptive_threshold=value)
    assert scene.cycles.adaptive_threshold == value


@pytest.mark.parametrize("value", [0, 1, 32, 4096])
def test_adaptive_min_samples_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, adaptive_min_samples=value)
    assert scene.cycles.adaptive_min_samples == value


@pytest.mark.parametrize("value", [False, True])
def test_viewport_adaptive_sampling_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, viewport_adaptive_sampling=value)
    assert scene.cycles.use_preview_adaptive_sampling is value


@pytest.mark.parametrize("value", [0.0, 0.001, 0.1, 1.0])
def test_viewport_adaptive_threshold_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, viewport_adaptive_threshold=value)
    assert scene.cycles.preview_adaptive_threshold == value


@pytest.mark.parametrize("value", [0, 1, 32, 4096])
def test_viewport_adaptive_min_samples_valid(value):
    scene = MockScene()
    configure_cycles_sampling(scene, viewport_adaptive_min_samples=value)
    assert scene.cycles.preview_adaptive_min_samples == value


@pytest.mark.parametrize("value", [0, -1])
def test_render_samples_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, render_samples=value)


@pytest.mark.parametrize("value", [-1])
def test_viewport_samples_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, viewport_samples=value)


@pytest.mark.parametrize("value", [-1.0])
def test_time_limit_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, time_limit=value)


@pytest.mark.parametrize("value", [-0.001, 1.001])
def test_adaptive_threshold_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, adaptive_threshold=value)


@pytest.mark.parametrize("value", [-0.001, 1.001])
def test_viewport_adaptive_threshold_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, viewport_adaptive_threshold=value)


@pytest.mark.parametrize("value", [-1, 4097])
def test_adaptive_min_samples_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, adaptive_min_samples=value)


@pytest.mark.parametrize("value", [-1, 4097])
def test_viewport_adaptive_min_samples_invalid(value):
    scene = MockScene()
    with pytest.raises(ValueError):
        configure_cycles_sampling(scene, viewport_adaptive_min_samples=value)


@pytest.mark.parametrize("value", ["512", 512.5, True])
def test_render_samples_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, render_samples=value)


@pytest.mark.parametrize("value", ["64", 64.5, True])
def test_viewport_samples_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, viewport_samples=value)


@pytest.mark.parametrize("value", ["300", 300, True])
def test_time_limit_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, time_limit=value)


@pytest.mark.parametrize("value", [0, 1, "true"])
def test_adaptive_sampling_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, adaptive_sampling=value)


@pytest.mark.parametrize("value", ["0.01", True])
def test_adaptive_threshold_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, adaptive_threshold=value)


@pytest.mark.parametrize("value", ["32", 32.0, True])
def test_adaptive_min_samples_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, adaptive_min_samples=value)


@pytest.mark.parametrize("value", [0, 1, "true"])
def test_viewport_adaptive_sampling_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, viewport_adaptive_sampling=value)


@pytest.mark.parametrize("value", ["0.01", True])
def test_viewport_adaptive_threshold_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, viewport_adaptive_threshold=value)


@pytest.mark.parametrize("value", ["32", 32.0, True])
def test_viewport_adaptive_min_samples_type_invalid(value):
    scene = MockScene()
    with pytest.raises(TypeError):
        configure_cycles_sampling(scene, viewport_adaptive_min_samples=value)


def test_validation_is_atomic():
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            render_samples=512,
            viewport_samples=-1,
        )

    assert scene.cycles.samples == 128
    assert scene.cycles.preview_samples == 16


def test_validation_is_atomic_across_adaptive_settings():
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            adaptive_sampling=True,
            adaptive_threshold=0.01,
            adaptive_min_samples=4097,
            viewport_adaptive_sampling=True,
        )

    assert scene.cycles.use_adaptive_sampling is False
    assert scene.cycles.adaptive_threshold == 0.01
    assert scene.cycles.adaptive_min_samples == 0
    assert scene.cycles.use_preview_adaptive_sampling is False
