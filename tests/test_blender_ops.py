"""Tests for blender_ops module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from colab_cli.blender_ops import (
    run_command,
    render_blender,
    render_frame,
    get_blender_info,
)


class TestRunCommand:
    """Test run_command helper function."""

    @patch("colab_cli.blender_ops.subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = run_command(["blender", "--version"])

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["blender", "--version"],
            capture_output=True,
            check=True,
            text=True,
        )

    @patch("colab_cli.blender_ops.subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command failure raises CalledProcessError."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, ["blender"], stderr="error")

        with pytest.raises(CalledProcessError):
            run_command(["blender", "invalid"])


class TestRenderBlender:
    """Test render_blender function."""

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_default_args(self, mock_run_command, temp_dir):
        """Test render_blender with default arguments."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = "Render complete"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        render_blender(str(blend_file))

        mock_run_command.assert_called_once()
        cmd = mock_run_command.call_args[0][0]
        assert cmd[0] == "blender"
        assert "-b" in cmd
        assert str(blend_file) in cmd
        assert "-E" in cmd
        assert "CYCLES" in cmd
        assert "-s" in cmd
        assert "1" in cmd
        assert "-e" in cmd
        assert "-o" in cmd
        assert "//render" in cmd
        assert "-F" in cmd
        assert "PNG" in cmd
        assert "-a" in cmd

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_custom_engine(self, mock_run_command, temp_dir):
        """Test render_blender with custom engine."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        render_blender(str(blend_file), engine="EEVEE")

        cmd = mock_run_command.call_args[0][0]
        assert "-E" in cmd
        idx = cmd.index("-E")
        assert cmd[idx + 1] == "EEVEE"

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_custom_frames(self, mock_run_command, temp_dir):
        """Test render_blender with custom frame range."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        render_blender(str(blend_file), frame_start=10, frame_end=20)

        cmd = mock_run_command.call_args[0][0]
        assert "-s" in cmd
        idx = cmd.index("-s")
        assert cmd[idx + 1] == "10"
        assert "-e" in cmd
        idx = cmd.index("-e")
        assert cmd[idx + 1] == "20"

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_custom_output(self, mock_run_command, temp_dir):
        """Test render_blender with custom output path and format."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        render_blender(
            str(blend_file),
            output_path="/custom/output",
            output_format="OPEN_EXR",
        )

        cmd = mock_run_command.call_args[0][0]
        assert "-o" in cmd
        idx = cmd.index("-o")
        assert cmd[idx + 1] == "/custom/output"
        assert "-F" in cmd
        idx = cmd.index("-F")
        assert cmd[idx + 1] == "OPEN_EXR"

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_extra_args(self, mock_run_command, temp_dir):
        """Test render_blender with extra arguments."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        render_blender(str(blend_file), extra_args=["--cycles-device", "CUDA"])

        cmd = mock_run_command.call_args[0][0]
        assert "--cycles-device" in cmd
        assert "CUDA" in cmd

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_prints_command(self, mock_run_command, temp_dir, capsys):
        """Test render_blender prints the command."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_result = MagicMock()
        mock_result.stdout = "Render done"
        mock_result.stderr = "Some warning"
        mock_run_command.return_value = mock_result

        render_blender(str(blend_file))

        captured = capsys.readouterr()
        assert "Running:" in captured.out
        assert "blender" in captured.out
        assert "Render done" in captured.out
        assert "STDERR:" in captured.out
        assert "Some warning" in captured.out

    @patch("colab_cli.blender_ops.run_command")
    def test_render_blender_failure(self, mock_run_command, temp_dir):
        """Test render_blender propagates CalledProcessError."""
        from subprocess import CalledProcessError

        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        mock_run_command.side_effect = CalledProcessError(1, ["blender"], stderr="Error")

        with pytest.raises(CalledProcessError):
            render_blender(str(blend_file))


class TestRenderFrame:
    """Test render_frame function."""

    @patch("colab_cli.blender_ops.render_blender")
    def test_render_frame_calls_render_blender(self, mock_render_blender, temp_dir):
        """Test render_frame calls render_blender with frame_start=frame_end."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        render_frame(str(blend_file), frame=5, engine="EEVEE", output_path="/out", output_format="JPEG")

        mock_render_blender.assert_called_once_with(
            blend_file=str(blend_file),
            engine="EEVEE",
            frame_start=5,
            frame_end=5,
            output_path="/out",
            output_format="JPEG",
            extra_args=None,
        )

    @patch("colab_cli.blender_ops.render_blender")
    def test_render_frame_defaults(self, mock_render_blender, temp_dir):
        """Test render_frame with default arguments."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        render_frame(str(blend_file))

        mock_render_blender.assert_called_once_with(
            blend_file=str(blend_file),
            engine="CYCLES",
            frame_start=1,
            frame_end=1,
            output_path="//render",
            output_format="PNG",
            extra_args=None,
        )

    @patch("colab_cli.blender_ops.render_blender")
    def test_render_frame_passes_extra_args(self, mock_render_blender, temp_dir):
        """Test render_frame passes extra_args."""
        blend_file = temp_dir / "test.blend"
        blend_file.write_text("BLENDER")

        render_frame(str(blend_file), extra_args=["--debug"])

        mock_render_blender.assert_called_once()
        call_kwargs = mock_render_blender.call_args[1]
        assert call_kwargs["extra_args"] == ["--debug"]


class TestGetBlenderInfo:
    """Test get_blender_info function."""

    @patch("colab_cli.blender_ops.run_command")
    def test_get_blender_info_success(self, mock_run_command):
        """Test successful blender info retrieval."""
        mock_result = MagicMock()
        mock_result.stdout = "Blender 5.1.2\n"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run_command.return_value = mock_result

        info = get_blender_info()

        assert info == "Blender 5.1.2"
        mock_run_command.assert_called_once_with(["blender", "--version"])

    @patch("colab_cli.blender_ops.run_command")
    def test_get_blender_info_failure(self, mock_run_command):
        """Test get_blender_info propagates CalledProcessError."""
        from subprocess import CalledProcessError

        mock_run_command.side_effect = CalledProcessError(1, ["blender", "--version"], stderr="not found")

        with pytest.raises(CalledProcessError):
            get_blender_info()


class TestMainFunction:
    """Test the main() function."""

    @patch("colab_cli.blender_ops.render_frame")
    @patch("colab_cli.blender_ops.get_blender_info")
    def test_main_info_flag(self, mock_get_info, mock_render_frame):
        """Test main with --info flag."""
        import sys
        from colab_cli.blender_ops import main

        mock_get_info.return_value = "Blender 5.1.2"

        with patch.object(sys, "argv", ["blender_ops", "--info"]):
            result = main()

        assert result == 0
        mock_get_info.assert_called_once()
        mock_render_frame.assert_not_called()

    @patch("colab_cli.blender_ops.render_frame")
    def test_main_render_frame(self, mock_render_frame):
        """Test main with blend file and frame."""
        import sys
        from colab_cli.blender_ops import main

        with patch.object(sys, "argv", ["blender_ops", "test.blend", "EEVEE", "5"]):
            result = main()

        assert result == 0
        mock_render_frame.assert_called_once_with("test.blend", frame=5, engine="EEVEE")

    @patch("colab_cli.blender_ops.render_blender")
    def test_main_render_animation(self, mock_render_blender):
        """Test main with blend file (no frame = animation)."""
        import sys
        from colab_cli.blender_ops import main

        with patch.object(sys, "argv", ["blender_ops", "test.blend", "CYCLES"]):
            result = main()

        assert result == 0
        mock_render_blender.assert_called_once_with(
            blend_file="test.blend",
            engine="CYCLES",
            frame_start=1,
            frame_end=1,
            output_path="//render",
            output_format="PNG",
        )

    @patch("colab_cli.blender_ops.render_blender")
    def test_main_defaults(self, mock_render_blender):
        """Test main with minimal arguments."""
        import sys
        from colab_cli.blender_ops import main

        with patch.object(sys, "argv", ["blender_ops", "test.blend"]):
            result = main()

        assert result == 0
        mock_render_blender.assert_called_once()

    def test_main_no_args_shows_usage(self, capsys):
        """Test main with no arguments shows usage and exits with 1."""
        import sys
        from colab_cli.blender_ops import main

        with patch.object(sys, "argv", ["blender_ops"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Usage:" in captured.out