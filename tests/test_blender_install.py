"""Tests for blender_install module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from colab_cli.blender_install import (
    DEFAULT_VERSION,
    DEFAULT_URL_BASE,
    run_command,
    install_blender,
    get_blender_version,
)


class TestBlenderInstallConstants:
    """Test blender_install constants."""

    def test_default_version(self):
        """Test DEFAULT_VERSION is set."""
        assert DEFAULT_VERSION == "blender-5.1.2-linux-x64"

    def test_default_url_base(self):
        """Test DEFAULT_URL_BASE is set."""
        assert DEFAULT_URL_BASE == "https://download.blender.org/release/Blender5.1"


class TestRunCommand:
    """Test run_command helper function."""

    @patch("colab_cli.blender_install.subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = run_command(["echo", "test"])

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["echo", "test"],
            capture_output=True,
            check=True,
            text=True,
        )

    @patch("colab_cli.blender_install.subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command failure raises CalledProcessError."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, ["false"], stderr="error")

        with pytest.raises(CalledProcessError):
            run_command(["false"])


class TestInstallBlender:
    """Test install_blender function."""

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_downloads_and_installs(
        self, mock_cwd, mock_exists, mock_run_command, temp_dir
    ):
        """Test full install flow: download, extract, symlink, verify."""
        # Setup mocks
        mock_cwd.return_value = temp_dir
        # First check for version_file: doesn't exist -> download
        # Second check for version dir: doesn't exist -> extract
        mock_exists.side_effect = [False, False, True]  # version_file, version_dir, blender_binary

        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender()

        # Verify wget called
        assert mock_run_command.call_count >= 3
        # Check wget call
        wget_call = mock_run_command.call_args_list[0]
        assert "wget" in wget_call[0][0]
        # Check tar call
        tar_call = mock_run_command.call_args_list[1]
        assert "tar" in tar_call[0][0]
        assert "-xf" in tar_call[0][0]
        # Check symlink call
        ln_call = mock_run_command.call_args_list[2]
        assert "sudo" in ln_call[0][0]
        assert "ln" in ln_call[0][0]
        assert "-sf" in ln_call[0][0]
        # Check verify call
        verify_call = mock_run_command.call_args_list[3]
        assert "/usr/local/bin/blender" in verify_call[0][0]
        assert "--version" in verify_call[0][0]

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_skips_existing_download(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test skips download if version file exists."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [True, False, True]  # version_file exists, version_dir doesn't, binary exists

        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender()

        # wget should not be called
        wget_calls = [c for c in mock_run_command.call_args_list if "wget" in c[0][0]]
        assert len(wget_calls) == 0

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_skips_existing_extract(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test skips extraction if version directory exists."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, True, True]  # version_file doesn't exist, version_dir exists, binary exists

        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender()

        # tar should not be called
        tar_calls = [c for c in mock_run_command.call_args_list if "tar" in c[0][0]]
        assert len(tar_calls) == 0

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_raises_if_binary_missing(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test raises FileNotFoundError if blender binary not found after extract."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, False, False]  # version_file, version_dir, blender_binary - all missing

        mock_run_command.return_value = MagicMock(stdout="", stderr="", returncode=0)

        with pytest.raises(FileNotFoundError, match="Blender binary not found"):
            install_blender()

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_custom_version(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test install with custom version."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, False, True]
        mock_run_command.return_value = MagicMock(stdout="Blender 4.2.0\n", stderr="", returncode=0)

        install_blender(version="blender-4.2.0-linux-x64")

        # Check download URL contains custom version
        wget_call = mock_run_command.call_args_list[0]
        assert "blender-4.2.0-linux-x64.tar.xz" in wget_call[0][0]

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_custom_url_base(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test install with custom URL base."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, False, True]
        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender(url_base="https://custom.url/blender")

        wget_call = mock_run_command.call_args_list[0]
        assert "https://custom.url/blender" in wget_call[0][0]

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_custom_install_path(self, mock_cwd, mock_exists, mock_run_command, temp_dir):
        """Test install with custom install path."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, False, True]
        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender(install_path="/custom/path/blender")

        # Check symlink uses custom path
        ln_call = mock_run_command.call_args_list[2]
        assert "/custom/path/blender" in ln_call[0][0]
        # Check verify uses custom path
        verify_call = mock_run_command.call_args_list[3]
        assert "/custom/path/blender" in verify_call[0][0]

    @patch("colab_cli.blender_install.run_command")
    @patch("colab_cli.blender_install.os.path.exists")
    @patch("colab_cli.blender_install.Path.cwd")
    def test_install_blender_dry_run_prints_commands(self, mock_cwd, mock_exists, mock_run_command, temp_dir, capsys):
        """Test install prints commands to stdout."""
        mock_cwd.return_value = temp_dir
        mock_exists.side_effect = [False, False, True]
        mock_run_command.return_value = MagicMock(stdout="Blender 5.1.2\n", stderr="", returncode=0)

        install_blender()

        captured = capsys.readouterr()
        assert "Downloading" in captured.out
        assert "Extracting" in captured.out
        assert "Creating symlink" in captured.out
        assert "Verifying installation" in captured.out


class TestGetBlenderVersion:
    """Test get_blender_version function."""

    @patch("colab_cli.blender_install.subprocess.run")
    def test_get_blender_version_success(self, mock_run):
        """Test successful version retrieval."""
        mock_result = MagicMock()
        mock_result.stdout = "Blender 5.1.2\n"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        version = get_blender_version()

        assert version == "Blender 5.1.2"
        mock_run.assert_called_once_with(
            ["blender", "--version"],
            capture_output=True,
            check=True,
            text=True,
        )

    @patch("colab_cli.blender_install.subprocess.run")
    def test_get_blender_version_failure(self, mock_run):
        """Test version retrieval failure raises CalledProcessError."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, ["blender", "--version"], stderr="not found")

        with pytest.raises(CalledProcessError):
            get_blender_version()


class TestMainFunction:
    """Test the main() function."""

    @patch("colab_cli.blender_install.install_blender")
    def test_main_calls_install(self, mock_install):
        """Test main calls install_blender."""
        from colab_cli.blender_install import main

        main()

        mock_install.assert_called_once_with(
            version=DEFAULT_VERSION,
            url_base=DEFAULT_URL_BASE,
            install_path="/usr/local/bin/blender",
        )