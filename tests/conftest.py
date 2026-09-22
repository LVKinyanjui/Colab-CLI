"""Shared pytest fixtures for colab_cli tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_subprocess_check_output():
    """Mock subprocess.check_output for testing."""
    with patch("subprocess.check_output") as mock_check:
        mock_check.return_value = b""
        yield mock_check


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_home_dir(temp_dir):
    """Mock the user's home directory."""
    with patch.dict(os.environ, {"HOME": str(temp_dir)}):
        with patch("pathlib.Path.home", return_value=temp_dir):
            yield temp_dir


@pytest.fixture
def mock_sshd_config(temp_dir):
    """Create a mock sshd_config file."""
    sshd_config = temp_dir / "sshd_config"
    sshd_config.write_text("# Test sshd config\nPort 22\n")
    return sshd_config


@pytest.fixture
def mock_bashrc(temp_dir):
    """Create a mock .bashrc file."""
    bashrc = temp_dir / ".bashrc"
    bashrc.write_text("# Test bashrc\nexport PATH=/usr/bin\n")
    return bashrc


@pytest.fixture
def mock_sshd_pid(temp_dir):
    """Create a mock sshd.pid file."""
    sshd_pid = temp_dir / "sshd.pid"
    sshd_pid.write_text("1234\n")
    return sshd_pid


@pytest.fixture
def sample_blend_file(temp_dir):
    """Create a mock .blend file."""
    blend_file = temp_dir / "test.blend"
    blend_file.write_text("BLENDER")
    return blend_file


@pytest.fixture
def mock_wget_download(temp_dir):
    """Mock wget download to create a local file."""
    def _mock_download(url: str, output: str | None = None):
        if output:
            filepath = Path(output)
        else:
            filepath = temp_dir / Path(url).name
        filepath.write_text("MOCK DOWNLOAD CONTENT")
        return filepath
    return _mock_download


# Common mock responses
@pytest.fixture
def blender_version_output():
    """Mock blender --version output."""
    return "Blender 5.1.2\n"


@pytest.fixture
def sshd_config_content():
    """Sample sshd_config content for testing."""
    return """# Test sshd config
Port 22
PermitRootLogin no
X11Forwarding no
AllowTcpForwarding no
"""


@pytest.fixture
def bashrc_content():
    """Sample .bashrc content for testing."""
    return """# Test bashrc
export PATH=/usr/bin:/bin
export EDITOR=vim
"""