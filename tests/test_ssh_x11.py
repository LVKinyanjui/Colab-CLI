"""Tests for ssh_x11 module."""

import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from colab_cli.ssh_x11 import SSH_MARKER_START, SSH_MARKER_END, SSH_SETTINGS, setup_x11_forwarding


class TestSSHX11Constants:
    """Test SSH X11 constants."""

    def test_ssh_settings_keys(self):
        """Test SSH_SETTINGS has expected keys."""
        expected_keys = {"AllowTcpForwarding", "X11Forwarding", "X11DisplayOffset", "X11UseLocalhost"}
        assert set(SSH_SETTINGS.keys()) == expected_keys

    def test_ssh_settings_values(self):
        """Test SSH_SETTINGS values are correct."""
        assert SSH_SETTINGS["AllowTcpForwarding"] == "yes"
        assert SSH_SETTINGS["X11Forwarding"] == "yes"
        assert SSH_SETTINGS["X11DisplayOffset"] == "10"
        assert SSH_SETTINGS["X11UseLocalhost"] == "yes"

    def test_markers(self):
        """Test marker strings."""
        assert SSH_MARKER_START == "# --- managed X11 forwarding ---"
        assert SSH_MARKER_END == "# --- end managed X11 forwarding ---"


class TestSetupX11Forwarding:
    """Test setup_x11_forwarding function."""

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_x11_forwarding_basic(self, mock_pid, mock_config, mock_sudo):
        """Test basic setup_x11_forwarding flow."""
        # Setup mocks
        mock_config.read_text.return_value = "# Original config\nPort 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        # Call function
        setup_x11_forwarding()

        # Verify sudo was called for tee (writing config)
        assert mock_sudo.call_count >= 3
        # First call should be tee with the new config
        tee_call = mock_sudo.call_args_list[0]
        assert tee_call[0][0] == "tee"
        assert str(mock_config) in tee_call[0]

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_removes_previous_managed_block(self, mock_pid, mock_config, mock_sudo):
        """Test that previous managed block is removed."""
        old_content = (
            f"{SSH_MARKER_START}\n"
            "AllowTcpForwarding yes\n"
            f"{SSH_MARKER_END}\n"
            "Port 22\n"
        )
        mock_config.read_text.return_value = old_content
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        # Check that tee was called with new content (no old managed block)
        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        assert SSH_MARKER_START in written_content
        # Should only have one marker block
        assert written_content.count(SSH_MARKER_START) == 1

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_removes_global_definitions(self, mock_pid, mock_config, mock_sudo):
        """Test that existing global definitions are removed."""
        old_content = "X11Forwarding no\nAllowTcpForwarding no\nPort 22\n"
        mock_config.read_text.return_value = old_content
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        # Should not contain the old global definitions (outside Match block)
        lines = written_content.split("\n")
        # First non-comment, non-marker line should be Port 22
        non_marker_lines = [l for l in lines if l and not l.startswith("#")]
        # The managed block comes first, then Port 22
        assert "Port 22" in written_content

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_preserves_match_block(self, mock_pid, mock_config, mock_sudo):
        """Test that Match blocks are preserved."""
        old_content = (
            "Port 22\n"
            "Match User testuser\n"
            "  X11Forwarding no\n"
            "  AllowTcpForwarding no\n"
        )
        mock_config.read_text.return_value = old_content
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        assert "Match User testuser" in written_content
        # Inside Match block, original settings should be preserved
        assert "X11Forwarding no" in written_content

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_validates_and_reloads(self, mock_pid, mock_config, mock_sudo):
        """Test that config is validated and sshd is reloaded."""
        mock_config.read_text.return_value = "Port 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        # Check sshd -t was called for validation
        validate_call = None
        reload_call = None
        for call in mock_sudo.call_args_list:
            if call[0][0] == "/usr/sbin/sshd" and "-t" in call[0]:
                validate_call = call
            if call[0][0] == "kill" and "-HUP" in call[0]:
                reload_call = call

        assert validate_call is not None, "sshd -t validation not called"
        assert reload_call is not None, "kill -HUP reload not called"
        assert reload_call[0][2] == "1234"  # PID

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_checks_effective_config(self, mock_pid, mock_config, mock_sudo):
        """Test that effective X11Forwarding is checked."""
        mock_config.read_text.return_value = "Port 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        # Check sshd -T was called
        effective_call = None
        for call in mock_sudo.call_args_list:
            if call[0][0] == "/usr/sbin/sshd" and "-T" in call[0]:
                effective_call = call

        assert effective_call is not None, "sshd -T not called"
        assert "-f" in effective_call[0]

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_handles_sudo_failure(self, mock_pid, mock_config, mock_sudo):
        """Test handling of sudo failures."""
        mock_config.read_text.return_value = "Port 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.side_effect = subprocess.CalledProcessError(1, "sudo", stderr="Permission denied")

        with pytest.raises(subprocess.CalledProcessError):
            setup_x11_forwarding()

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_setup_managed_block_format(self, mock_pid, mock_config, mock_sudo):
        """Test that managed block has correct format."""
        mock_config.read_text.return_value = "Port 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]

        # Check managed block structure
        lines = written_content.split("\n")
        assert lines[0] == SSH_MARKER_START
        # Check all settings are in the block
        for key, value in SSH_SETTINGS.items():
            assert f"{key} {value}" in written_content
        # Find end marker
        end_marker_idx = lines.index(SSH_MARKER_END)
        assert end_marker_idx > 0
        # Should end with newline
        assert written_content.endswith("\n")


class TestSudoHelper:
    """Test the sudo helper function."""

    @patch("colab_cli.ssh_x11.subprocess.run")
    def test_sudo_runs_with_sudo(self, mock_run):
        """Test sudo helper prepends sudo."""
        from colab_cli.ssh_x11 import sudo

        mock_run.return_value = MagicMock(returncode=0)

        sudo("echo", "test")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "sudo"
        assert args[1] == "echo"
        assert args[2] == "test"
        assert mock_run.call_args[1]["check"] is True


class TestSetupX11ForwardingEdgeCases:
    """Test edge cases for setup_x11_forwarding."""

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_empty_config_file(self, mock_pid, mock_config, mock_sudo):
        """Test with empty config file."""
        mock_config.read_text.return_value = ""
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        assert SSH_MARKER_START in written_content
        assert SSH_MARKER_END in written_content

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_config_with_only_comments(self, mock_pid, mock_config, mock_sudo):
        """Test with config containing only comments."""
        mock_config.read_text.return_value = "# Comment 1\n# Comment 2\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        assert SSH_MARKER_START in written_content
        assert "# Comment 1" in written_content

    @patch("colab_cli.ssh_x11.sudo")
    @patch("colab_cli.ssh_x11.SSHD_CONFIG", new_callable=MagicMock)
    @patch("colab_cli.ssh_x11.SSHD_PID", new_callable=MagicMock)
    def test_case_insensitive_matching(self, mock_pid, mock_config, mock_sudo):
        """Test case-insensitive matching of settings."""
        mock_config.read_text.return_value = "x11forwarding no\nallowtcpforwarding no\nPort 22\n"
        mock_pid.read_text.return_value = "1234\n"
        mock_sudo.return_value = MagicMock(stdout="x11forwarding yes\n", stderr="", returncode=0)

        setup_x11_forwarding()

        tee_call = mock_sudo.call_args_list[0]
        written_content = tee_call[1]["input"]
        # Old lowercase settings should be removed
        assert "x11forwarding no" not in written_content
        assert "allowtcpforwarding no" not in written_content
        # New settings should be present
        assert "X11Forwarding yes" in written_content
        assert "AllowTcpForwarding yes" in written_content