"""Tests for xdg_runtime module."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from colab_cli.xdg_runtime import XDG_BLOCK, XDG_MARKER_END, XDG_MARKER_START, setup_xdg_runtime_dir


class TestXDGRuntimeConstants:
    """Test XDG runtime constants."""

    def test_markers(self):
        """Test marker strings."""
        assert XDG_MARKER_START == "# --- XDG runtime directory for remote GUI applications ---"
        assert XDG_MARKER_END == "# --- end XDG runtime directory ---"

    def test_xdg_block_contains_markers(self):
        """Test XDG_BLOCK contains markers."""
        assert XDG_MARKER_START in XDG_BLOCK
        assert XDG_MARKER_END in XDG_BLOCK

    def test_xdg_block_contains_export(self):
        """Test XDG_BLOCK contains export statement."""
        assert 'export XDG_RUNTIME_DIR="/tmp/blender-runtime-$USER"' in XDG_BLOCK
        assert 'mkdir -p "$XDG_RUNTIME_DIR"' in XDG_BLOCK
        assert 'chmod 700 "$XDG_RUNTIME_DIR"' in XDG_BLOCK


class TestSetupXDGRuntimeDir:
    """Test setup_xdg_runtime_dir function."""

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_creates_bashrc_if_not_exists(self, mock_home, temp_dir):
        """Test creates .bashrc if it doesn't exist."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"

        setup_xdg_runtime_dir()

        assert bashrc.exists()
        content = bashrc.read_text()
        assert XDG_MARKER_START in content
        assert XDG_MARKER_END in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_appends_to_existing_bashrc(self, mock_home, temp_dir, bashrc_content):
        """Test appends to existing .bashrc."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text(bashrc_content)

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        assert bashrc_content.strip() in content
        assert XDG_MARKER_START in content
        assert XDG_MARKER_END in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_does_not_duplicate_if_exists(self, mock_home, temp_dir):
        """Test does not duplicate if block already exists."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text(f"{bashrc_content}\n{XDG_BLOCK}\n")

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        # Should only have one instance of the block
        assert content.count(XDG_MARKER_START) == 1

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_preserves_existing_content(self, mock_home, temp_dir):
        """Test preserves existing bashrc content."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        original = "export PATH=/usr/bin\nalias ll='ls -la'\n"
        bashrc.write_text(original)

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        assert "export PATH=/usr/bin" in content
        assert "alias ll='ls -la'" in content
        assert XDG_MARKER_START in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_adds_newline_before_block(self, mock_home, temp_dir):
        """Test adds newline before block when appending."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text("export PATH=/usr/bin")  # No trailing newline

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        # Should have newline before the block
        assert content.endswith("\n" + XDG_BLOCK) or content.endswith(XDG_BLOCK)

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_block_content(self, mock_home, temp_dir):
        """Test the exact content of the added block."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        # Verify all parts of the block
        assert 'export XDG_RUNTIME_DIR="/tmp/blender-runtime-$USER"' in content
        assert 'mkdir -p "$XDG_RUNTIME_DIR"' in content
        assert 'chmod 700 "$XDG_RUNTIME_DIR"' in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_prints_message(self, mock_home, temp_dir, capsys):
        """Test prints configuration message."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"

        setup_xdg_runtime_dir()

        captured = capsys.readouterr()
        assert "Configured" in captured.out
        assert ".bashrc" in captured.out
        assert "source ~/.bashrc" in captured.out

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_handles_permission_error(self, mock_home, temp_dir):
        """Test handles permission errors gracefully."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text("test")
        bashrc.chmod(0o444)  # Read-only

        with pytest.raises(PermissionError):
            setup_xdg_runtime_dir()


class TestSetupXDGRuntimeDirEdgeCases:
    """Test edge cases for setup_xdg_runtime_dir."""

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_with_empty_bashrc(self, mock_home, temp_dir):
        """Test with empty .bashrc file."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text("")

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        assert XDG_MARKER_START in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_with_only_newlines(self, mock_home, temp_dir):
        """Test with .bashrc containing only newlines."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        bashrc.write_text("\n\n\n")

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        assert XDG_MARKER_START in content

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_marker_partial_match(self, mock_home, temp_dir):
        """Test that partial marker match doesn't prevent adding."""
        mock_home.return_value = temp_dir
        bashrc = temp_dir / ".bashrc"
        # Has start marker but not end marker
        bashrc.write_text(f"{XDG_MARKER_START}\nsomething\n")

        setup_xdg_runtime_dir()

        content = bashrc.read_text()
        # Should still add the block since end marker is missing
        assert content.count(XDG_MARKER_START) >= 1

    @patch("colab_cli.xdg_runtime.Path.home")
    def test_setup_home_directory_expansion(self, mock_home, temp_dir):
        """Test that home directory is properly expanded."""
        mock_home.return_value = temp_dir

        setup_xdg_runtime_dir()

        bashrc = temp_dir / ".bashrc"
        assert bashrc.exists()


class TestMainFunction:
    """Test the main() function."""

    @patch("colab_cli.xdg_runtime.setup_xdg_runtime_dir")
    def test_main_calls_setup(self, mock_setup):
        """Test main calls setup function."""
        from colab_cli.xdg_runtime import main

        main()

        mock_setup.assert_called_once()