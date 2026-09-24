import pytest

from set_cycles_sampling import configure_cycles_sampling


class MockCycles:
    def __init__(
        self,
        *,
        samples=128,
        preview_samples=16,
        time_limit=0.0,
    ):
        self.samples = samples
        self.preview_samples = preview_samples
        self.time_limit = time_limit


class MockScene:
    def __init__(self):
        self.cycles = MockCycles()


def test_configure_all_core_sampling_settings():
    scene = MockScene()

    result = configure_cycles_sampling(
        scene,
        render_samples=512,
        viewport_samples=64,
        time_limit=300.0,
    )

    assert scene.cycles.samples == 512
    assert scene.cycles.preview_samples == 64
    assert scene.cycles.time_limit == 300.0

    assert len(result.changed) == 3
    assert result.unchanged == ()


def test_none_leaves_setting_unchanged():
    scene = MockScene()

    result = configure_cycles_sampling(
        scene,
        render_samples=512,
        viewport_samples=None,
        time_limit=None,
    )

    assert scene.cycles.samples == 512
    assert scene.cycles.preview_samples == 16
    assert scene.cycles.time_limit == 0.0

    assert [change.name for change in result.changed] == [
        "render_samples"
    ]

    assert result.unchanged == (
        "viewport_samples",
        "time_limit",
    )


def test_existing_value_is_reported_unchanged():
    scene = MockScene()

    result = configure_cycles_sampling(
        scene,
        render_samples=128,
        viewport_samples=16,
        time_limit=0.0,
    )

    assert result.changed == ()

    assert result.unchanged == (
        "render_samples",
        "viewport_samples",
        "time_limit",
    )


@pytest.mark.parametrize(
    "value",
    [1, 512, 4096],
)
def test_valid_render_samples(value):
    scene = MockScene()

    configure_cycles_sampling(
        scene,
        render_samples=value,
    )

    assert scene.cycles.samples == value


@pytest.mark.parametrize(
    "value",
    [0, 32, 64],
)
def test_valid_viewport_samples(value):
    scene = MockScene()

    configure_cycles_sampling(
        scene,
        viewport_samples=value,
    )

    assert scene.cycles.preview_samples == value


@pytest.mark.parametrize(
    "value",
    [0.0, 1.0, 300.0],
)
def test_valid_time_limit(value):
    scene = MockScene()

    configure_cycles_sampling(
        scene,
        time_limit=value,
    )

    assert scene.cycles.time_limit == value


@pytest.mark.parametrize(
    "value",
    [-1, -100],
)
def test_render_samples_rejects_negative(value):
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            render_samples=value,
        )


@pytest.mark.parametrize(
    "value",
    [-1, -100],
)
def test_viewport_samples_rejects_negative(value):
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            viewport_samples=value,
        )


@pytest.mark.parametrize(
    "value",
    [-1.0, -0.1],
)
def test_time_limit_rejects_negative(value):
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            time_limit=value,
        )


@pytest.mark.parametrize(
    "value",
    ["512", 512.5, True],
)
def test_render_samples_rejects_invalid_types(value):
    scene = MockScene()

    with pytest.raises(TypeError):
        configure_cycles_sampling(
            scene,
            render_samples=value,
        )


@pytest.mark.parametrize(
    "value",
    ["64", 64.5, True],
)
def test_viewport_samples_rejects_invalid_types(value):
    scene = MockScene()

    with pytest.raises(TypeError):
        configure_cycles_sampling(
            scene,
            viewport_samples=value,
        )


@pytest.mark.parametrize(
    "value",
    ["300", 300, True],
)
def test_time_limit_rejects_invalid_types(value):
    scene = MockScene()

    with pytest.raises(TypeError):
        configure_cycles_sampling(
            scene,
            time_limit=value,
        )


def test_validation_is_atomic():
    scene = MockScene()

    with pytest.raises(ValueError):
        configure_cycles_sampling(
            scene,
            render_samples=512,
            viewport_samples=-1,
        )

    # Nothing was changed because validation happened first.
    assert scene.cycles.samples == 128
    assert scene.cycles.preview_samples == 16
