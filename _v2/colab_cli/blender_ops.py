"""Blender Rendering Operations Module.

Provides utilities for rendering .blend files with Blender CLI.
Can be run independently or imported as a module.
"""

import subprocess
from pathlib import Path
from typing import Optional


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command with error checking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        text=True,
    )


def render_blender(
    blend_file: str,
    engine: str = "CYCLES",
    frame_start: int = 1,
    frame_end: int = 1,
    output_path: str = "//render",
    output_format: str = "PNG",
    extra_args: Optional[list[str]] = None,
) -> None:
    """Render a .blend file using Blender CLI.

    Args:
        blend_file: Path to the .blend file
        engine: Render engine (CYCLES, EEVEE, EEVEE_NEXT, BLENDER_WORKBENCH)
        frame_start: Start frame
        frame_end: End frame
        output_path: Output path (// for relative to blend file)
        output_format: Output format (PNG, JPEG, OPEN_EXR, etc.)
        extra_args: Additional arguments to pass to blender
    """
    cmd = [
        "blender",
        "-b", blend_file,
        "-E", engine,
        "-s", str(frame_start),
        "-e", str(frame_end),
        "-o", output_path,
        "-F", output_format,
        "-a",  # Render animation
    ]

    if extra_args:
        cmd.extend(extra_args)

    print(f"Running: {' '.join(cmd)}")
    result = run_command(cmd)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)


def render_frame(
    blend_file: str,
    frame: int = 1,
    engine: str = "CYCLES",
    output_path: str = "//render",
    output_format: str = "PNG",
    extra_args: Optional[list[str]] = None,
) -> None:
    """Render a single frame."""
    render_blender(
        blend_file=blend_file,
        engine=engine,
        frame_start=frame,
        frame_end=frame,
        output_path=output_path,
        output_format=output_format,
        extra_args=extra_args,
    )


def get_blender_info() -> str:
    """Get Blender version info."""
    result = run_command(["blender", "--version"])
    return result.stdout.strip()


def main() -> None:
    """Entry point when run as a script."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m colab_cli.blender_ops <blend_file> [engine] [frame]")
        print("Example: python -m colab_cli.blender_ops mr_elephant.blend CYCLES 1")
        sys.exit(1)

    blend_file = sys.argv[1]
    engine = sys.argv[2] if len(sys.argv) > 2 else "CYCLES"
    frame = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    render_frame(blend_file, frame=frame, engine=engine)


if __name__ == "__main__":
    main()