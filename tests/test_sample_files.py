"""Tests for sample_files module."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from colab_cli.sample_files import (
    SAMPLE_FILES,
    run_command,
    download_sample_file,
    download_all_samples,
)


class TestSampleFilesConstants:
    """Test sample_files constants."""

    def test_sample_files_dict(self):
        """Test SAMPLE_FILES dictionary structure."""
        assert isinstance(SAMPLE_FILES, dict)
        assert "loft" in SAMPLE_FILES
        assert "mr_elephant" in SAMPLE_FILES
        assert "classroom" in SAMPLE_FILES
        assert "bmw" in SAMPLE_FILES
        assert "pavilion" in SAMPLE_FILES

        # Check URLs are valid
        for name, url in SAMPLE_FILES.items():
            assert url.startswith("https://download.blender.org/demo/")
            assert url.endswith(".blend")


class TestRunCommand:
    """Test run_command helper function."""

    @patch("colab_cli.sample_files.subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = run_command(["wget", "url"])

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["wget", "url"],
            capture_output=True,
            check=True,
            text=True,
        )

    @patch("colab_cli.sample_files.subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command failure raises CalledProcessError."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, ["wget"], stderr="error")

        with pytest.raises(CalledProcessError):
            run_command(["wget", "invalid"])


class TestDownloadSampleFile:
    """Test download_sample_file function."""

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_success(self, mock_exists, mock_run_command, temp_dir):
        """Test successful download of known sample."""
        mock_exists.return_value = False
        mock_run_command.return_value = MagicMock(stdout="", stderr="", returncode=0)

        result = download_sample_file("mr_elephant", str(temp_dir))

        assert result == temp_dir / "mr_elephant.blend"
        mock_run_command.assert_called_once_with([
            "wget", "-O", str(temp_dir / "mr_elephant.blend"),
            SAMPLE_FILES["mr_elephant"]
        ])

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_custom_url(self, mock_exists, mock_run_command, temp_dir):
        """Test download with custom URL."""
        mock_exists.return_value = False
        mock_run_command.return_value = MagicMock(stdout="", stderr="", returncode=0)

        custom_url = "https://example.com/custom.blend"
        result = download_sample_file("custom", str(temp_dir), url=custom_url)

        assert result == temp_dir / "custom.blend"
        mock_run_command.assert_called_once_with([
            "wget", "-O", str(temp_dir / "custom.blend"),
            custom_url
        ])

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_skips_existing(self, mock_exists, mock_run_command, temp_dir):
        """Test skips download if file already exists."""
        mock_exists.return_value = True

        result = download_sample_file("mr_elephant", str(temp_dir))

        assert result == temp_dir / "mr_elephant.blend"
        mock_run_command.assert_not_called()

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_unknown_sample(self, mock_exists, mock_run_command):
        """Test raises ValueError for unknown sample without custom URL."""
        with pytest.raises(ValueError, match="Unknown sample: unknown"):
            download_sample_file("unknown", ".")

        mock_run_command.assert_not_called()

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_creates_output_dir(self, mock_exists, mock_run_command, temp_dir):
        """Test creates output directory if needed."""
        mock_exists.return_value = False
        mock_run_command.return_value = MagicMock(stdout="", stderr="", returncode=0)

        output_dir = temp_dir / "subdir" / "nested"
        result = download_sample_file("mr_elephant", str(output_dir))

        assert result == output_dir / "mr_elephant.blend"

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_prints_message(self, mock_exists, mock_run_command, temp_dir, capsys):
        """Test prints download message."""
        mock_exists.return_value = False
        mock_run_command.return_value = MagicMock(stdout="", stderr="", returncode=0)

        download_sample_file("mr_elephant", str(temp_dir))

        captured = capsys.readouterr()
        assert "Downloading" in captured.out
        assert SAMPLE_FILES["mr_elephant"] in captured.out
        assert "mr_elephant.blend" in captured.out

    @patch("colab_cli.sample_files.run_command")
    @patch("colab_cli.sample_files.Path.exists")
    def test_download_sample_file_wget_failure(self, mock_exists, mock_run_command, temp_dir):
        """Test handles wget failure."""
        from subprocess import CalledProcessError

        mock_exists.return_value = False
        mock_run_command.side_effect = CalledProcessError(1, ["wget"], stderr="404 Not Found")

        with pytest.raises(CalledProcessError):
            download_sample_file("mr_elephant", str(temp_dir))


class TestDownloadAllSamples:
    """Test download_all_samples function."""

    @patch("colab_cli.sample_files.download_sample_file")
    @patch("colab_cli.sample_files.Path.mkdir")
    def test_download_all_samples(self, mock_mkdir, mock_download, temp_dir):
        """Test downloads all samples."""
        mock_download.side_effect = [
            temp_dir / "loft.blend",
            temp_dir / "mr_elephant.blend",
            temp_dir / "classroom.blend",
            temp_dir / "bmw.blend",
            temp_dir / "pavilion.blend",
        ]

        results = download_all_samples(str(temp_dir))

        assert len(results) == 5
        assert mock_download.call_count == 5
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("colab_cli.sample_files.download_sample_file")
    @patch("colab_cli.sample_files.Path.mkdir")
    def test_download_all_samples_returns_paths(self, mock_mkdir, mock_download, temp_dir):
        """Test returns list of downloaded file paths."""
        expected_paths = [
            temp_dir / "loft.blend",
            temp_dir / "mr_elephant.blend",
            temp_dir / "classroom.blend",
            temp_dir / "bmw.blend",
            temp_dir / "pavilion.blend",
        ]
        mock_download.side_effect = expected_paths

        results = download_all_samples(str(temp_dir))

        assert results == expected_paths

    @patch("colab_cli.sample_files.download_sample_file")
    @patch("colab_cli.sample_files.Path.mkdir")
    def test_download_all_samples_continues_on_error(self, mock_mkdir, mock_download, temp_dir):
        """Test continues downloading other samples if one fails."""
        from subprocess import CalledProcessError

        mock_download.side_effect = [
            temp_dir / "loft.blend",
            CalledProcessError(1, ["wget"], stderr="error"),
            temp_dir / "classroom.blend",
            temp_dir / "bmw.blend",
            temp_dir / "pavilion.blend",
        ]

        # Should raise the exception
        with pytest.raises(CalledProcessError):
            download_all_samples(str(temp_dir))


class TestMainFunction:
    """Test the main() function."""

    @patch("colab_cli.sample_files.download_sample_file")
    def test_main_single_sample(self, mock_download):
        """Test main with single sample argument."""
        import sys
        from colab_cli.sample_files import main

        with patch.object(sys, "argv", ["sample_files", "mr_elephant", "/output"]):
            main()

        mock_download.assert_called_once_with("mr_elephant", "/output", None)

    @patch("colab_cli.sample_files.download_all_samples")
    def test_main_all_samples(self, mock_download_all):
        """Test main with no arguments (downloads all)."""
        import sys
        from colab_cli.sample_files import main

        with patch.object(sys, "argv", ["sample_files"]):
            main()

        mock_download_all.assert_called_once_with(".")

    @patch("colab_cli.sample_files.download_sample_file")
    def test_main_with_custom_url(self, mock_download):
        """Test main with custom URL."""
        import sys
        from colab_cli.sample_files import main

        with patch.object(sys, "argv", ["sample_files", "custom", ".", "https://custom.url/file.blend"]):
            main()

        mock_download.assert_called_once_with("custom", ".", "https://custom.url/file.blend")