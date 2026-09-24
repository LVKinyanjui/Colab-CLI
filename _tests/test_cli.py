"""Tests for cli module."""

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from colab_cli.cli import (
    build_parser,
    main,
    cmd_ssh_x11,
    cmd_xdg_runtime,
    cmd_blender_install,
    cmd_sample_files,
    cmd_blender_ops,
    cmd_colab_job,
    cmd_setup,
    cmd_render,
)


class TestBuildParser:
    """Test argument parser construction."""

    def test_parser_created(self):
        """Test parser is created with correct program name."""
        parser = build_parser()
        assert parser.prog == "colab-cli"

    def test_parser_has_version(self):
        """Test parser has version argument."""
        parser = build_parser()
        # Find version action
        version_action = None
        for action in parser._actions:
            if action.dest == "version":
                version_action = action
                break
        assert version_action is not None

    def test_parser_has_subcommands(self):
        """Test all subcommands are registered."""
        parser = build_parser()
        subparsers_action = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                subparsers_action = action
                break

        assert subparsers_action is not None
        subcommands = list(subparsers_action.choices.keys())
        expected = [
            "ssh-x11", "xdg-runtime", "blender-install", "sample-files",
            "blender-ops", "colab-job", "setup", "render"
        ]
        for cmd in expected:
            assert cmd in subcommands

    def test_ssh_x11_parser(self):
        """Test ssh-x11 subcommand parser."""
        parser = build_parser()
        args = parser.parse_args(["ssh-x11"])
        assert args.command == "ssh-x11"
        assert hasattr(args, "func")

    def test_xdg_runtime_parser(self):
        """Test xdg-runtime subcommand parser."""
        parser = build_parser()
        args = parser.parse_args(["xdg-runtime"])
        assert args.command == "xdg-runtime"

    def test_blender_install_parser(self):
        """Test blender-install subcommand parser."""
        parser = build_parser()
        args = parser.parse_args([
            "blender-install",
            "--version", "blender-4.0.0-linux-x64",
            "--url-base", "https://custom.url",
            "--install-path", "/usr/bin/blender",
        ])
        assert args.command == "blender-install"
        assert args.version == "blender-4.0.0-linux-x64"
        assert args.url_base == "https://custom.url"
        assert args.install_path == "/usr/bin/blender"

    def test_blender_install_parser_defaults(self):
        """Test blender-install default values."""
        parser = build_parser()
        args = parser.parse_args(["blender-install"])
        assert args.version == "blender-5.1.2-linux-x64"
        assert args.url_base == "https://download.blender.org/release/Blender5.1"
        assert args.install_path == "/usr/local/bin/blender"

    def test_sample_files_parser_name(self):
        """Test sample-files parser with --name."""
        parser = build_parser()
        args = parser.parse_args([
            "sample-files",
            "--name", "mr_elephant",
            "--output-dir", "/tmp/samples",
        ])
        assert args.command == "sample-files"
        assert args.name == "mr_elephant"
        assert args.output_dir == "/tmp/samples"

    def test_sample_files_parser_all(self):
        """Test sample-files parser with --all."""
        parser = build_parser()
        args = parser.parse_args(["sample-files", "--all", "--output-dir", "/tmp"])
        assert args.all is True
        assert args.output_dir == "/tmp"

    def test_sample_files_parser_list(self):
        """Test sample-files parser with --list."""
        parser = build_parser()
        args = parser.parse_args(["sample-files", "--list"])
        assert args.list is True

    def test_sample_files_parser_custom_url(self):
        """Test sample-files parser with --url."""
        parser = build_parser()
        args = parser.parse_args(["sample-files", "--name", "custom", "--url", "https://custom.url/file.blend"])
        assert args.url == "https://custom.url/file.blend"

    def test_blender_ops_parser_info(self):
        """Test blender-ops parser with --info."""
        parser = build_parser()
        args = parser.parse_args(["blender-ops", "--info"])
        assert args.info is True

    def test_blender_ops_parser_render_frame(self):
        """Test blender-ops parser with --frame."""
        parser = build_parser()
        args = parser.parse_args([
            "blender-ops",
            "--blend-file", "test.blend",
            "--engine", "EEVEE",
            "--frame", "5",
            "--output", "/custom/output",
            "--format", "JPEG",
        ])
        assert args.blend_file == "test.blend"
        assert args.engine == "EEVEE"
        assert args.frame == 5
        assert args.output == "/custom/output"
        assert args.format == "JPEG"
        assert args.frame_start == 1
        assert args.frame_end == 1

    def test_blender_ops_parser_render_animation(self):
        """Test blender-ops parser for animation."""
        parser = build_parser()
        args = parser.parse_args([
            "blender-ops",
            "--blend-file", "test.blend",
            "--frame-start", "10",
            "--frame-end", "20",
        ])
        assert args.frame_start == 10
        assert args.frame_end == 20
        assert args.frame is None

    def test_colab_job_parser(self):
        """Test colab-job parser."""
        parser = build_parser()
        args = parser.parse_args([
            "colab-job",
            "-s", "script.py",
            "-f", "out1.txt",
            "-f", "out2.txt",
            "-g", "A100",
            "--high-mem",
            "-l", "/logs",
            "-n", "my-job",
            "--dry-run",
        ])
        assert args.script == "script.py"
        assert args.file == ["out1.txt", "out2.txt"]
        assert args.gpu == "A100"
        assert args.high_mem is True
        assert args.log_dir == "/logs"
        assert args.name == "my-job"
        assert args.dry_run is True

    def test_colab_job_parser_defaults(self):
        """Test colab-job parser defaults."""
        parser = build_parser()
        args = parser.parse_args(["colab-job", "-s", "script.py"])
        assert args.gpu == "T4"
        assert args.high_mem is False
        assert args.log_dir == "./logs"
        assert args.name == ""
        assert args.file == []
        assert args.dry_run is False

    def test_setup_parser(self):
        """Test setup parser."""
        parser = build_parser()
        args = parser.parse_args(["setup"])
        assert args.command == "setup"

    def test_render_parser(self):
        """Test render parser."""
        parser = build_parser()
        args = parser.parse_args([
            "render",
            "--sample", "classroom",
            "--frame", "10",
            "--engine", "EEVEE",
        ])
        assert args.sample == "classroom"
        assert args.frame == 10
        assert args.engine == "EEVEE"

    def test_render_parser_defaults(self):
        """Test render parser defaults."""
        parser = build_parser()
        args = parser.parse_args(["render"])
        assert args.sample == "mr_elephant"
        assert args.frame == 1
        assert args.engine == "CYCLES"

    def test_no_command_shows_help(self, capsys):
        """Test no command shows help and exits with 1."""
        parser = build_parser()
        with patch.object(sys, "argv", ["colab-cli"]):
            result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "usage:" in captured.err.lower()


class TestCmdSshX11:
    """Test cmd_ssh_x11 function."""

    @patch("colab_cli.cli.setup_x11_forwarding")
    def test_cmd_ssh_x11_calls_setup(self, mock_setup):
        """Test cmd_ssh_x11 calls setup_x11_forwarding."""
        args = argparse.Namespace()
        result = cmd_ssh_x11(args)
        assert result == 0
        mock_setup.assert_called_once()


class TestCmdXdgRuntime:
    """Test cmd_xdg_runtime function."""

    @patch("colab_cli.cli.setup_xdg_runtime_dir")
    def test_cmd_xdg_runtime_calls_setup(self, mock_setup):
        """Test cmd_xdg_runtime calls setup_xdg_runtime_dir."""
        args = argparse.Namespace()
        result = cmd_xdg_runtime(args)
        assert result == 0
        mock_setup.assert_called_once()


class TestCmdBlenderInstall:
    """Test cmd_blender_install function."""

    @patch("colab_cli.cli.install_blender")
    def test_cmd_blender_install_calls_install(self, mock_install):
        """Test cmd_blender_install calls install_blender with args."""
        args = argparse.Namespace(
            version="blender-4.0.0-linux-x64",
            url_base="https://custom.url",
            install_path="/usr/bin/blender",
        )
        result = cmd_blender_install(args)
        assert result == 0
        mock_install.assert_called_once_with(
            version="blender-4.0.0-linux-x64",
            url_base="https://custom.url",
            install_path="/usr/bin/blender",
        )

    @patch("colab_cli.cli.install_blender")
    def test_cmd_blender_install_defaults(self, mock_install):
        """Test cmd_blender_install with default args."""
        args = argparse.Namespace(
            version="blender-5.1.2-linux-x64",
            url_base="https://download.blender.org/release/Blender5.1",
            install_path="/usr/local/bin/blender",
        )
        result = cmd_blender_install(args)
        assert result == 0
        mock_install.assert_called_once()


class TestCmdSampleFiles:
    """Test cmd_sample_files function."""

    @patch("colab_cli.cli.download_sample_file")
    def test_cmd_sample_files_name(self, mock_download):
        """Test cmd_sample_files with --name."""
        args = argparse.Namespace(
            name="mr_elephant",
            url=None,
            output_dir="/tmp",
            all=False,
            list=False,
        )
        result = cmd_sample_files(args)
        assert result == 0
        mock_download.assert_called_once_with("mr_elephant", "/tmp", None)

    @patch("colab_cli.cli.download_sample_file")
    def test_cmd_sample_files_name_with_url(self, mock_download):
        """Test cmd_sample_files with --name and --url."""
        args = argparse.Namespace(
            name="custom",
            url="https://custom.url/file.blend",
            output_dir="/tmp",
            all=False,
            list=False,
        )
        result = cmd_sample_files(args)
        assert result == 0
        mock_download.assert_called_once_with("custom", "/tmp", "https://custom.url/file.blend")

    @patch("colab_cli.cli.download_all_samples")
    def test_cmd_sample_files_all(self, mock_download_all):
        """Test cmd_sample_files with --all."""
        args = argparse.Namespace(
            name=None,
            url=None,
            output_dir="/tmp",
            all=True,
            list=False,
        )
        result = cmd_sample_files(args)
        assert result == 0
        mock_download_all.assert_called_once_with("/tmp")

    @patch("colab_cli.cli.SAMPLE_FILES", {"test": "https://example.com/test.blend"})
    def test_cmd_sample_files_list(self, capsys):
        """Test cmd_sample_files with --list."""
        args = argparse.Namespace(
            name=None,
            url=None,
            output_dir=".",
            all=False,
            list=True,
        )
        result = cmd_sample_files(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Available samples:" in captured.out
        assert "test: https://example.com/test.blend" in captured.out

    def test_cmd_sample_files_no_args_error(self, capsys):
        """Test cmd_sample_files without required args returns error."""
        args = argparse.Namespace(
            name=None,
            url=None,
            output_dir=".",
            all=False,
            list=False,
        )
        result = cmd_sample_files(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: specify --name, --all, or --list" in captured.out


class TestCmdBlenderOps:
    """Test cmd_blender_ops function."""

    @patch("colab_cli.cli.get_blender_info")
    def test_cmd_blender_ops_info(self, mock_get_info):
        """Test cmd_blender_ops with --info."""
        mock_get_info.return_value = "Blender 5.1.2"
        args = argparse.Namespace(
            info=True,
            blend_file=None,
            engine="CYCLES",
            frame=None,
            frame_start=1,
            frame_end=1,
            output="//render",
            format="PNG",
        )
        result = cmd_blender_ops(args)
        assert result == 0
        mock_get_info.assert_called_once()

    @patch("colab_cli.cli.render_frame")
    def test_cmd_blender_ops_render_frame(self, mock_render_frame):
        """Test cmd_blender_ops with --frame."""
        args = argparse.Namespace(
            info=False,
            blend_file="test.blend",
            engine="EEVEE",
            frame=5,
            frame_start=1,
            frame_end=1,
            output="/custom/output",
            format="JPEG",
        )
        result = cmd_blender_ops(args)
        assert result == 0
        mock_render_frame.assert_called_once_with(
            blend_file="test.blend",
            frame=5,
            engine="EEVEE",
            output_path="/custom/output",
            output_format="JPEG",
        )

    @patch("colab_cli.cli.render_blender")
    def test_cmd_blender_ops_render_animation(self, mock_render_blender):
        """Test cmd_blender_ops without --frame (animation)."""
        args = argparse.Namespace(
            info=False,
            blend_file="test.blend",
            engine="CYCLES",
            frame=None,
            frame_start=10,
            frame_end=20,
            output="//render",
            format="PNG",
        )
        result = cmd_blender_ops(args)
        assert result == 0
        mock_render_blender.assert_called_once_with(
            blend_file="test.blend",
            engine="CYCLES",
            frame_start=10,
            frame_end=20,
            output_path="//render",
            output_format="PNG",
        )

    def test_cmd_blender_ops_missing_blend_file(self, capsys):
        """Test cmd_blender_ops without --blend-file returns error."""
        args = argparse.Namespace(
            info=False,
            blend_file=None,
            engine="CYCLES",
            frame=None,
            frame_start=1,
            frame_end=1,
            output="//render",
            format="PNG",
        )
        result = cmd_blender_ops(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: --blend-file required" in captured.out


class TestCmdColabJob:
    """Test cmd_colab_job function."""

    @patch("colab_cli.cli.ColabJob")
    def test_cmd_colab_job_creates_job(self, mock_job_class):
        """Test cmd_colab_job creates ColabJob and runs it."""
        mock_job = MagicMock()
        mock_job.run.return_value = 0
        mock_job_class.return_value = mock_job

        args = argparse.Namespace(
            script="script.py",
            gpu="T4",
            high_mem=False,
            log_dir="./logs",
            name="",
            file=[],
            dry_run=False,
        )
        result = cmd_colab_job(args)
        assert result == 0
        mock_job_class.assert_called_once()
        mock_job.run.assert_called_once()

    @patch("colab_cli.cli.ColabJob")
    def test_cmd_colab_job_passes_config(self, mock_job_class):
        """Test cmd_colab_job passes correct config."""
        mock_job = MagicMock()
        mock_job.run.return_value = 0
        mock_job_class.return_value = mock_job

        args = argparse.Namespace(
            script="test.py",
            gpu="A100",
            high_mem=True,
            log_dir="/var/log",
            name="custom-job",
            file=["out.txt"],
            dry_run=True,
        )
        result = cmd_colab_job(args)
        assert result == 0

        # Check ColabJobConfig was created correctly
        call_args = mock_job_class.call_args[0][0]
        from colab_cli.cli import ColabJobConfig
        assert isinstance(call_args, ColabJobConfig)
        assert call_args.script_path == "test.py"
        assert call_args.gpu_type == "A100"
        assert call_args.high_mem is True
        assert call_args.log_dir == "/var/log"
        assert call_args.session_name == "custom-job"
        assert call_args.remote_files == ["out.txt"]
        assert call_args.dry_run is True


class TestCmdSetup:
    """Test cmd_setup function."""

    @patch("colab_cli.cli.setup_x11_forwarding")
    @patch("colab_cli.cli.setup_xdg_runtime_dir")
    @patch("colab_cli.cli.install_blender")
    def test_cmd_setup_calls_all(self, mock_install, mock_xdg, mock_ssh):
        """Test cmd_setup calls all three setup functions."""
        args = argparse.Namespace()
        result = cmd_setup(args)
        assert result == 0
        mock_ssh.assert_called_once()
        mock_xdg.assert_called_once()
        mock_install.assert_called_once_with()

    @patch("colab_cli.cli.setup_x11_forwarding")
    @patch("colab_cli.cli.setup_xdg_runtime_dir")
    @patch("colab_cli.cli.install_blender")
    def test_cmd_setup_prints_messages(self, mock_install, mock_xdg, mock_ssh, capsys):
        """Test cmd_setup prints progress messages."""
        args = argparse.Namespace()
        result = cmd_setup(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Running Full Setup" in captured.out
        assert "Configuring SSH X11 forwarding" in captured.out
        assert "Configuring XDG_RUNTIME_DIR" in captured.out
        assert "Installing Blender" in captured.out
        assert "Setup Complete" in captured.out
        assert "source ~/.bashrc" in captured.out


class TestCmdRender:
    """Test cmd_render function."""

    @patch("colab_cli.cli.install_blender")
    @patch("colab_cli.cli.download_sample_file")
    @patch("colab_cli.cli.render_frame")
    def test_cmd_render_pipeline(self, mock_render, mock_download, mock_install, temp_dir):
        """Test cmd_render runs full pipeline."""
        mock_download.return_value = temp_dir / "mr_elephant.blend"

        args = argparse.Namespace(
            sample="mr_elephant",
            frame=1,
            engine="CYCLES",
        )
        result = cmd_render(args)
        assert result == 0

        mock_install.assert_called_once_with()
        mock_download.assert_called_once_with("mr_elephant", ".")
        mock_render.assert_called_once_with(
            blend_file=str(temp_dir / "mr_elephant.blend"),
            frame=1,
            engine="CYCLES",
        )

    @patch("colab_cli.cli.install_blender")
    @patch("colab_cli.cli.download_sample_file")
    @patch("colab_cli.cli.render_frame")
    def test_cmd_render_custom_args(self, mock_render, mock_download, mock_install, temp_dir):
        """Test cmd_render with custom arguments."""
        mock_download.return_value = temp_dir / "classroom.blend"

        args = argparse.Namespace(
            sample="classroom",
            frame=10,
            engine="EEVEE",
        )
        result = cmd_render(args)
        assert result == 0

        mock_download.assert_called_once_with("classroom", ".")
        mock_render.assert_called_once_with(
            blend_file=str(temp_dir / "classroom.blend"),
            frame=10,
            engine="EEVEE",
        )

    @patch("colab_cli.cli.install_blender")
    @patch("colab_cli.cli.download_sample_file")
    @patch("colab_cli.cli.render_frame")
    def test_cmd_render_prints_messages(self, mock_render, mock_download, mock_install, temp_dir, capsys):
        """Test cmd_render prints progress messages."""
        mock_download.return_value = temp_dir / "mr_elephant.blend"

        args = argparse.Namespace(sample="mr_elephant", frame=1, engine="CYCLES")
        result = cmd_render(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Quick Render Pipeline" in captured.out
        assert "Installing Blender" in captured.out
        assert "Downloading sample: mr_elephant" in captured.out
        assert "Rendering" in captured.out
        assert "Render Complete" in captured.out


class TestMainFunction:
    """Test main() function."""

    @patch("colab_cli.cli.build_parser")
    def test_main_calls_parser(self, mock_build_parser):
        """Test main builds parser and calls func."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "ssh-x11"
        mock_args.func = MagicMock(return_value=0)
        mock_parser.parse_args.return_value = mock_args
        mock_build_parser.return_value = mock_parser

        with patch.object(sys, "argv", ["colab-cli", "ssh-x11"]):
            result = main()

        assert result == 0
        mock_parser.parse_args.assert_called_once()
        mock_args.func.assert_called_once_with(mock_args)

    def test_main_no_command(self, capsys):
        """Test main with no command shows help."""
        with patch.object(sys, "argv", ["colab-cli"]):
            result = main()
        assert result == 1


class TestSubcommandIntegration:
    """Integration tests for subcommands via main()."""

    @patch("colab_cli.cli.setup_x11_forwarding")
    def test_main_ssh_x11(self, mock_setup):
        """Test main with ssh-x11 subcommand."""
        with patch.object(sys, "argv", ["colab-cli", "ssh-x11"]):
            result = main()
        assert result == 0
        mock_setup.assert_called_once()

    @patch("colab_cli.cli.setup_xdg_runtime_dir")
    def test_main_xdg_runtime(self, mock_setup):
        """Test main with xdg-runtime subcommand."""
        with patch.object(sys, "argv", ["colab-cli", "xdg-runtime"]):
            result = main()
        assert result == 0
        mock_setup.assert_called_once()

    @patch("colab_cli.cli.install_blender")
    def test_main_blender_install(self, mock_install):
        """Test main with blender-install subcommand."""
        with patch.object(sys, "argv", ["colab-cli", "blender-install"]):
            result = main()
        assert result == 0
        mock_install.assert_called_once()

    @patch("colab_cli.cli.download_sample_file")
    def test_main_sample_files(self, mock_download):
        """Test main with sample-files subcommand."""
        with patch.object(sys, "argv", ["colab-cli", "sample-files", "--name", "mr_elephant"]):
            result = main()
        assert result == 0
        mock_download.assert_called_once()

    @patch("colab_cli.cli.get_blender_info")
    def test_main_blender_ops_info(self, mock_info):
        """Test main with blender-ops --info."""
        with patch.object(sys, "argv", ["colab-cli", "blender-ops", "--info"]):
            result = main()
        assert result == 0
        mock_info.assert_called_once()

    @patch("colab_cli.cli.ColabJob")
    def test_main_colab_job(self, mock_job_class):
        """Test main with colab-job subcommand."""
        mock_job = MagicMock()
        mock_job.run.return_value = 0
        mock_job_class.return_value = mock_job

        with patch.object(sys, "argv", ["colab-cli", "colab-job", "-s", "script.py"]):
            result = main()
        assert result == 0
        mock_job_class.assert_called_once()

    @patch("colab_cli.cli.setup_x11_forwarding")
    @patch("colab_cli.cli.setup_xdg_runtime_dir")
    @patch("colab_cli.cli.install_blender")
    def test_main_setup(self, mock_install, mock_xdg, mock_ssh):
        """Test main with setup subcommand."""
        with patch.object(sys, "argv", ["colab-cli", "setup"]):
            result = main()
        assert result == 0
        mock_ssh.assert_called_once()
        mock_xdg.assert_called_once()
        mock_install.assert_called_once()

    @patch("colab_cli.cli.install_blender")
    @patch("colab_cli.cli.download_sample_file")
    @patch("colab_cli.cli.render_frame")
    def test_main_render(self, mock_render, mock_download, mock_install, temp_dir):
        """Test main with render subcommand."""
        mock_download.return_value = temp_dir / "mr_elephant.blend"

        with patch.object(sys, "argv", ["colab-cli", "render", "--sample", "mr_elephant"]):
            result = main()
        assert result == 0
        mock_install.assert_called_once()
        mock_download.assert_called_once()
        mock_render.assert_called_once()