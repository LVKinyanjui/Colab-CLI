"""XDG Runtime Directory Configuration Module.

Sets up XDG_RUNTIME_DIR in ~/.bashrc for remote GUI applications.
Can be run independently or imported as a module.
"""

from pathlib import Path


XDG_MARKER_START = "# --- XDG runtime directory for remote GUI applications ---"
XDG_MARKER_END = "# --- end XDG runtime directory ---"

XDG_BLOCK = f"""{XDG_MARKER_START}
export XDG_RUNTIME_DIR="/tmp/blender-runtime-$USER"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
{XDG_MARKER_END}
"""


def setup_xdg_runtime_dir() -> None:
    """Configure XDG_RUNTIME_DIR in ~/.bashrc.

    Adds a managed block to ~/.bashrc that sets up the XDG runtime directory
    for remote GUI applications (like Blender).
    """
    bashrc = Path.home() / ".bashrc"

    content = bashrc.read_text() if bashrc.exists() else ""

    if XDG_MARKER_START not in content:
        with bashrc.open("a") as f:
            f.write("\n" + XDG_BLOCK)

    print(f"Configured {bashrc}")
    print("Open a new terminal or run: source ~/.bashrc")


def main() -> None:
    """Entry point when run as a script."""
    setup_xdg_runtime_dir()


if __name__ == "__main__":
    main()