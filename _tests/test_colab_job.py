"""Tests for colab_job module."""

import argparse
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from colab_cli.colab_job import ColabJobConfig, ColabJob, main


class TestColabJobConfig:
    """Test ColabJobConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ColabJobConfig(script_path="test.py")

        assert config.script_path == "test.py"
        assert config.gpu_type == "T4"
        assert config.high_mem is False
        assert config.log_dir == "./logs"
        assert config.session_name == ""
        assert config.remote_files == []
        assert config.dry_run is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ColabJobConfig(
            script_path="script.py",
            gpu_type="A100",
            high_mem=True,
            log_dir="/custom/logs",
            session_name="my-job",
            remote_files=["output.txt", "result.png"],
            dry_run=True,
        )

        assert config.script_path == "script.py"
        assert config.gpu_type == "A100"
        assert config.high_mem is True
        assert config.log_dir == "/custom/logs"
        assert config.session_name == "my-job"
        assert config.remote_files == ["output.txt", "result.png"]
        assert config.dry_run is True


class TestColabJob:
    """Test ColabJob class."""

    def test_init_creates_session_name(self):
        """Test that session name is auto-generated if not provided."""
        config = ColabJobConfig(script_path="test.py")
        job = ColabJob(config)

        assert job.session_name.startswith("job-")
        assert len(job.session_name) > 10  # Contains timestamp and uuid

    def test_init_uses_custom_session_name(self):
        """Test that custom session name is used."""
        config = ColabJobConfig(script_path="test.py", session_name="custom-job")
        job = ColabJob(config)

        assert job.session_name == "custom-job"

    def test_format_duration(self):
        """Test format_duration converts seconds to HH:MM:SS."""
        config = ColabJobConfig(script_path="test.py")
        job = ColabJob(config)

        assert job.format_duration(0) == "00h:00m:00s (0s)"
        assert job.format_duration(59) == "00h:00m:59s (59s)"
        assert job.format_duration(60) == "00h:01m:00s (60s)"
        assert job.format_duration(3600) == "01h:00m:00s (3600s)"
        assert job.format_duration(3661) == "01h:01m:01s (3661s)"
        assert job.format_duration(7200) == "02h:00m:00s (7200s)"
        assert job.format_duration(86400) == "24h:00m:00s (86400s)"

    @patch("colab_cli.colab_job.subprocess.run")
    def test_run_command_success(self, mock_run, temp_dir):
        """Test run_command executes command."""
        config = ColabJobConfig(script_path="test.py")
        job = ColabJob(config)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = job.run_command(["echo", "test"])

        assert result == mock_result
        mock_run.assert_called_once_with(
            ["echo", "test"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("colab_cli.colab_job.subprocess.run")
    def test_run_command_dry_run(self, mock_run, temp_dir):
        """Test run_command skips execution in dry_run mode."""
        config = ColabJobConfig(script_path="test.py", dry_run=True)
        job = ColabJob(config)

        result = job.run_command(["echo", "test"])

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""
        mock_run.assert_not_called()

    @patch("colab_cli.colab_job.subprocess.run")
    def test_run_command_failure(self, mock_run, temp_dir):
        """Test run_command propagates CalledProcessError."""
        from subprocess import CalledProcessError

        config = ColabJobConfig(script_path="test.py")
        job = ColabJob(config)

        mock_run.side_effect = CalledProcessError(1, ["false"], stderr="error")

        with pytest.raises(CalledProcessError):
            job.run_command(["false"])

    def test_setup_logging(self, temp_dir):
        """Test setup_logging creates log directory and returns paths."""
        config = ColabJobConfig(script_path="test.py", log_dir=str(temp_dir / "logs"))
        job = ColabJob(config)

        stdout_log, stderr_log = job.setup_logging()

        assert stdout_log.parent.exists()
        assert "stdout.log" in stdout_log.name
        assert "stderr.log" in stderr_log.name
        assert job.session_name in stdout_log.name

    def test_provision_vm_dry_run(self, temp_dir):
        """Test provision_vm returns placeholder in dry_run mode."""
        config = ColabJobConfig(script_path="test.py", dry_run=True)
        job = ColabJob(config)

        session_id = job.provision_vm()

        assert session_id == "dry-run-session-id"

    def test_provision_vm_not_implemented(self, temp_dir):
        """Test provision_vm raises NotImplementedError when not dry_run."""
        config = ColabJobConfig(script_path="test.py", dry_run=False)
        job = ColabJob(config)

        with pytest.raises(NotImplementedError, match="VM provisioning not yet implemented"):
            job.provision_vm()

    def test_upload_script_dry_run(self, temp_dir, capsys):
        """Test upload_script prints message in dry_run mode."""
        config = ColabJobConfig(script_path="test.py", dry_run=True)
        job = ColabJob(config)

        job.upload_script("session-123")

        captured = capsys.readouterr()
        assert "Uploading test.py to session-123" in captured.out

    def test_execute_script_not_implemented(self, temp_dir):
        """Test execute_script raises NotImplementedError."""
        config = ColabJobConfig(script_path="test.py")
        job = ColabJob(config)

        with pytest.raises(NotImplementedError, match="Remote execution not yet implemented"):
            job.execute_script("session-123")

    def test_download_files_dry_run(self, temp_dir, capsys):
        """Test download_files prints message in dry_run mode."""
        config = ColabJobConfig(
            script_path="test.py",
            remote_files=["output.txt", "result.png"],
            dry_run=True,
        )
        job = ColabJob(config)

        job.download_files("session-123")

        captured = capsys.readouterr()
        assert "Downloading output.txt from session-123" in captured.out
        assert "Downloading result.png from session-123" in captured.out

    def test_cleanup_vm_dry_run(self, temp_dir, capsys):
        """Test cleanup_vm prints message in dry_run mode."""
        config = ColabJobConfig(script_path="test.py", dry_run=True)
        job = ColabJob(config)

        job.cleanup_vm("session-123")

        captured = capsys.readouterr()
        assert "Cleaning up VM: session-123" in captured.out

    @patch("colab_cli.colab_job.ColabJob.provision_vm")
    @patch("colab_cli.colab_job.ColabJob.upload_script")
    @patch("colab_cli.colab_job.ColabJob.execute_script")
    @patch("colab_cli.colab_job.ColabJob.download_files")
    @patch("colab_cli.colab_job.ColabJob.cleanup_vm")
    @patch("colab_cli.colab_job.ColabJob.setup_logging")
    def test_run_dry_run_full_flow(
        self, mock_setup_logging, mock_cleanup, mock_download, mock_execute,
        mock_upload, mock_provision, temp_dir
    ):
        """Test run() executes full flow in dry_run mode."""
        mock_setup_logging.return_value = (temp_dir / "stdout.log", temp_dir / "stderr.log")
        mock_provision.return_value = "dry-run-session-id"
        mock_execute.return_value = 0

        config = ColabJobConfig(
            script_path="test.py",
            remote_files=["output.txt"],
            dry_run=True,
        )
        job = ColabJob(config)

        exit_code = job.run()

        assert exit_code == 0
        mock_provision.assert_called_once()
        mock_upload.assert_called_once_with("dry-run-session-id")
        mock_execute.assert_called_once_with("dry-run-session-id")
        mock_download.assert_called_once_with("dry-run-session-id")
        # cleanup_vm should not be called in dry_run mode
        mock_cleanup.assert_not_called()

    @patch("colab_cli.colab_job.ColabJob.provision_vm")
    @patch("colab_cli.colab_job.ColabJob.upload_script")
    @patch("colab_cli.colab_job.ColabJob.execute_script")
    @patch("colab_cli.colab_job.ColabJob.download_files")
    @patch("colab_cli.colab_job.ColabJob.cleanup_vm")
    @patch("colab_cli.colab_job.ColabJob.setup_logging")
    def test_run_success_downloads_files(
        self, mock_setup_logging, mock_cleanup, mock_download, mock_execute,
        mock_upload, mock_provision, temp_dir
    ):
        """Test run() downloads files on success."""
        mock_setup_logging.return_value = (temp_dir / "stdout.log", temp_dir / "stderr.log")
        mock_provision.return_value = "session-123"
        mock_execute.return_value = 0

        config = ColabJobConfig(
            script_path="test.py",
            remote_files=["output.txt"],
            dry_run=False,
        )
        job = ColabJob(config)

        exit_code = job.run()

        assert exit_code == 0
        mock_download.assert_called_once_with("session-123")
        mock_cleanup.assert_called_once_with("session-123")

    @patch("colab_cli.colab_job.ColabJob.provision_vm")
    @patch("colab_cli.colab_job.ColabJob.upload_script")
    @patch("colab_cli.colab_job.ColabJob.execute_script")
    @patch("colab_cli.colab_job.ColabJob.download_files")
    @patch("colab_cli.colab_job.ColabJob.cleanup_vm")
    @patch("colab_cli.colab_job.ColabJob.setup_logging")
    def test_run_failure_no_download(
        self, mock_setup_logging, mock_cleanup, mock_download, mock_execute,
        mock_upload, mock_provision, temp_dir
    ):
        """Test run() doesn't download files on failure."""
        mock_setup_logging.return_value = (temp_dir / "stdout.log", temp_dir / "stderr.log")
        mock_provision.return_value = "session-123"
        mock_execute.return_value = 1  # Failure

        config = ColabJobConfig(
            script_path="test.py",
            remote_files=["output.txt"],
            dry_run=False,
        )
        job = ColabJob(config)

        exit_code = job.run()

        assert exit_code == 1
        mock_download.assert_not_called()
        mock_cleanup.assert_called_once_with("session-123")

    @patch("colab_cli.colab_job.ColabJob.provision_vm")
    @patch("colab_cli.colab_job.ColabJob.upload_script")
    @patch("colab_cli.colab_job.ColabJob.execute_script")
    @patch("colab_cli.colab_job.ColabJob.download_files")
    @patch("colab_cli.colab_job.ColabJob.cleanup_vm")
    @patch("colab_cli.colab_job.ColabJob.setup_logging")
    def test_run_exception_handled(
        self, mock_setup_logging, mock_cleanup, mock_download, mock_execute,
        mock_upload, mock_provision, temp_dir, capsys
    ):
        """Test run() handles exceptions and returns exit code 1."""
        mock_setup_logging.return_value = (temp_dir / "stdout.log", temp_dir / "stderr.log")
        mock_provision.side_effect = Exception("Provisioning failed")

        config = ColabJobConfig(script_path="test.py", dry_run=False)
        job = ColabJob(config)

        exit_code = job.run()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error: Provisioning failed" in captured.err
        mock_cleanup.assert_not_called()  # No session_id yet

    @patch("colab_cli.colab_job.ColabJob.provision_vm")
    @patch("colab_cli.colab_job.ColabJob.upload_script")
    @patch("colab_cli.colab_job.ColabJob.execute_script")
    @patch("colab_cli.colab_job.ColabJob.download_files")
    @patch("colab_cli.colab_job.ColabJob.cleanup_vm")
    @patch("colab_cli.colab_job.ColabJob.setup_logging")
    def test_run_exception_after_provision(
        self, mock_setup_logging, mock_cleanup, mock_download, mock_execute,
        mock_upload, mock_provision, temp_dir
    ):
        """Test run() cleans up VM if exception occurs after provisioning."""
        mock_setup_logging.return_value = (temp_dir / "stdout.log", temp_dir / "stderr.log")
        mock_provision.return_value = "session-123"
        mock_upload.side_effect = Exception("Upload failed")

        config = ColabJobConfig(script_path="test.py", dry_run=False)
        job = ColabJob(config)

        exit_code = job.run()

        assert exit_code == 1
        mock_cleanup.assert_called_once_with("session-123")

    def test_run_prints_duration(self, temp_dir, capsys):
        """Test run() prints job duration."""
        config = ColabJobConfig(script_path="test.py", dry_run=True)
        job = ColabJob(config)

        # Mock time to control duration
        with patch("colab_cli.colab_job.time.time", side_effect=[1000.0, 1065.5]):
            job.run()

        captured = capsys.readouterr()
        assert "Duration:" in captured.out
        # 65.5 seconds = 00h:01m:05s
        assert "00h:01m:05s" in captured.out


class TestMainFunction:
    """Test the main() function."""

    @patch("colab_cli.colab_job.ColabJob.run")
    def test_main_parses_args(self, mock_run, temp_dir):
        """Test main parses arguments correctly."""
        mock_run.return_value = 0

        script_path = str(temp_dir / "script.py")
        Path(script_path).write_text("print('hello')")

        with patch.object(sys, "argv", [
            "colab_job",
            "-s", script_path,
            "-g", "A100",
            "--high-mem",
            "-l", "/custom/logs",
            "-n", "my-session",
            "-f", "output.txt",
            "-f", "result.png",
            "--dry-run",
        ]):
            result = main()

        assert result == 0
        mock_run.assert_called_once()

    @patch("colab_cli.colab_job.ColabJob.run")
    def test_main_default_args(self, mock_run, temp_dir):
        """Test main with minimal required arguments."""
        mock_run.return_value = 0

        script_path = str(temp_dir / "script.py")
        Path(script_path).write_text("print('hello')")

        with patch.object(sys, "argv", ["colab_job", "-s", script_path]):
            result = main()

        assert result == 0

    def test_main_missing_script_exits(self, capsys):
        """Test main exits with error if script not provided."""
        with patch.object(sys, "argv", ["colab_job"]):
            result = main()

        assert result == 1  # argparse error
        captured = capsys.readouterr()
        assert "required" in captured.err or "error" in captured.err.lower()

    @patch("colab_cli.colab_job.ColabJob.run")
    def test_main_creates_config_correctly(self, mock_run, temp_dir):
        """Test main creates ColabJobConfig with correct values."""
        mock_run.return_value = 0

        script_path = str(temp_dir / "script.py")
        Path(script_path).write_text("print('hello')")

        with patch.object(sys, "argv", [
            "colab_job",
            "-s", script_path,
            "-g", "L4",
            "--high-mem",
            "-l", "/var/log/jobs",
            "-n", "custom-name",
            "-f", "file1.txt",
            "-f", "file2.txt",
            "--dry-run",
        ]):
            main()

        # Verify ColabJob was created with correct config
        from colab_cli.colab_job import ColabJob
        call_args = ColabJob.call_args
        config = call_args[0][0]  # First positional arg

        assert config.script_path == script_path
        assert config.gpu_type == "L4"
        assert config.high_mem is True
        assert config.log_dir == "/var/log/jobs"
        assert config.session_name == "custom-name"
        assert config.remote_files == ["file1.txt", "file2.txt"]
        assert config.dry_run is True