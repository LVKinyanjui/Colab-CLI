"""Blender Installation Module.

Downloads, extracts, and installs Blender to /usr/local/bin.
Can be run independently or imported as a module.
"""

import os
import subprocess
from pathlib import Path


DEFAULT_VERSION = "blender-5.1.2-linux-x64"
DEFAULT_URL_BASE = "https://download.blender.org/release/Blender5.1"


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command with error checking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        text=True,
    )


def install_blender(
    version: str = DEFAULT_VERSION,
    url_base: str = DEFAULT_URL_BASE,
    install_path: str = "/usr/local/bin/blender",
) -> None:
    """Download, extract, and symlink Blender.

    Args:
        version: Blender version directory name (e.g., "blender-5.1.2-linux-x64")
        url_base: Base URL for Blender downloads
        install_path: Where to create the symlink
    """
    version_file = f"{version}.tar.xz"
    download_url = f"{url_base}/{version_file}"

    # Download
    if not os.path.exists(version_file):
        print(f"Downloading {download_url}...")
        run_command(["wget", download_url])
    else:
        print(f"{version_file} already exists, skipping download")

    # Extract
    if not os.path.exists(version):
        print(f"Extracting {version_file}...")
        run_command(["tar", "-xf", version_file])
    else:
        print(f"{version} already exists, skipping extraction")

    # Symlink
    blender_binary = Path.cwd() / version / "blender"
    if not blender_binary.exists():
        raise FileNotFoundError(f"Blender binary not found at {blender_binary}")

    print(f"Creating symlink: {install_path} -> {blender_binary}")
    run_command(["sudo", "ln", "-sf", str(blender_binary), install_path])

    # Verify
    print("\n--- Verifying installation ---")
    run_command([install_path, "--version"])


def get_blender_version() -> str:
    """Get Blender version info."""
    import subprocess
    result = subprocess.run(
        ["blender", "--version"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    """Entry point when run as a script."""
    install_blender()


if __name__ == "__main__":
    main()