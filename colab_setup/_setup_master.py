#!/usr/bin/env python3
"""Master Setup Script for Colab CLI.

This script orchestrates the full setup process by importing and using
the modular components. Each module can still be run independently.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import colab_cli
sys.path.insert(0, str(Path(__file__).parent))

from colab_cli.ssh_x11 import setup_x11_forwarding
from colab_cli.xdg_runtime import setup_xdg_runtime_dir
from colab_cli.blender_install import install_blender, get_blender_version
from colab_cli.sample_files import download_sample_file, download_all_samples, SAMPLE_FILES
from colab_cli.blender_ops import render_frame, render_blender, get_blender_info
from colab_cli.colab_job import ColabJob, ColabJobConfig


def run_full_setup() -> int:
    """Run the complete setup: SSH X11, XDG runtime, Blender install."""
    print("=== Colab CLI Full Setup ===\n")

    try:
        print("1. Configuring SSH X11 forwarding...")
        setup_x11_forwarding()
        print("   ✓ SSH X11 forwarding configured\n")

        print("2. Configuring XDG_RUNTIME_DIR...")
        setup_xdg_runtime_dir()
        print("   ✓ XDG_RUNTIME_DIR configured\n")

        print("3. Installing Blender...")
        install_blender()
        print("   ✓ Blender installed\n")

        print("=== Setup Complete ===")
        print("Run 'source ~/.bashrc' to apply XDG_RUNTIME_DIR changes")
        return 0

    except Exception as e:
        print(f"\n✗ Setup failed: {e}", file=sys.stderr)
        return 1


def run_quick_render(sample: str = "mr_elephant", frame: int = 1, engine: str = "CYCLES") -> int:
    """Quick render pipeline: install blender, download sample, render."""
    print("=== Quick Render Pipeline ===\n")

    try:
        print("1. Installing Blender...")
        install_blender()
        print("   ✓ Blender installed\n")

        print(f"2. Downloading sample: {sample}...")
        blend_path = download_sample_file(sample, ".")
        print(f"   ✓ Downloaded to {blend_path}\n")

        print(f"3. Rendering {blend_path} (frame {frame}, {engine})...")
        render_frame(
            blend_file=str(blend_path),
            frame=frame,
            engine=engine,
        )
        print("   ✓ Render complete\n")

        print("=== Render Complete ===")
        return 0

    except Exception as e:
        print(f"\n✗ Render failed: {e}", file=sys.stderr)
        return 1


def run_colab_job(
    script: str,
    gpu: str = "T4",
    high_mem: bool = False,
    log_dir: str = "./logs",
    name: str = "",
    remote_files: list[str] = None,
    dry_run: bool = False,
) -> int:
    """Run a job on Colab VM."""
    print("=== Colab Job Execution ===\n")

    config = ColabJobConfig(
        script_path=script,
        gpu_type=gpu,
        high_mem=high_mem,
        log_dir=log_dir,
        session_name=name,
        remote_files=remote_files or [],
        dry_run=dry_run,
    )

    job = ColabJob(config)
    return job.run()


def main() -> int:
    """Main entry point with subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="setup_master.py",
        description="Master setup script for Colab CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Full setup
    p = subparsers.add_parser("setup", help="Run full setup (ssh-x11, xdg-runtime, blender-install)")
    p.set_defaults(func=lambda args: run_full_setup())

    # Quick render
    p = subparsers.add_parser("render", help="Quick pipeline: install blender, download sample, render")
    p.add_argument("--sample", default="mr_elephant", help="Sample to render")
    p.add_argument("--frame", type=int, default=1, help="Frame to render")
    p.add_argument("--engine", default="CYCLES", help="Render engine")
    p.set_defaults(func=lambda args: run_quick_render(args.sample, args.frame, args.engine))

    # Colab job
    p = subparsers.add_parser("colab-job", help="Run a job on Colab VM")
    p.add_argument("-s", "--script", required=True, help="Path to Python script")
    p.add_argument("-f", "--file", action="append", default=[], help="Remote file to download")
    p.add_argument("-g", "--gpu", default="T4", help="GPU type")
    p.add_argument("--high-mem", action="store_true", help="High memory machine")
    p.add_argument("-l", "--log-dir", default="./logs", help="Log directory")
    p.add_argument("-n", "--name", default="", help="Session name")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    p.set_defaults(func=lambda args: run_colab_job(
        args.script, args.gpu, args.high_mem, args.log_dir, args.name, args.file, args.dry_run
    ))

    # Individual module commands
    p = subparsers.add_parser("ssh-x11", help="Configure SSH for X11 forwarding")
    p.set_defaults(func=lambda args: (setup_x11_forwarding(), 0)[1])

    p = subparsers.add_parser("xdg-runtime", help="Configure XDG_RUNTIME_DIR")
    p.set_defaults(func=lambda args: (setup_xdg_runtime_dir(), 0)[1])

    p = subparsers.add_parser("blender-install", help="Install Blender")
    p.add_argument("--version", default="blender-5.1.2-linux-x64")
    p.add_argument("--url-base", default="https://download.blender.org/release/Blender5.1")
    p.add_argument("--install-path", default="/usr/local/bin/blender")
    p.set_defaults(func=lambda args: (install_blender(args.version, args.url_base, args.install_path), 0)[1])

    p = subparsers.add_parser("sample-files", help="Download sample files")
    p.add_argument("--name", help="Sample name")
    p.add_argument("--url", help="Custom URL")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--all", action="store_true")
    p.add_argument("--list", action="store_true", help="List available samples")
    p.set_defaults(func=lambda args: (
        (download_all_samples(args.output_dir) if args.all else
         (print("Available samples:") or [print(f"  {name}: {url}") for name, url in SAMPLE_FILES.items()] or 0))
        if args.list else
        download_sample_file(args.name, args.output_dir, args.url),
        0
    )[1])

    p = subparsers.add_parser("blender-ops", help="Blender operations")
    p.add_argument("--blend-file", required=True)
    p.add_argument("--engine", default="CYCLES")
    p.add_argument("--frame", type=int)
    p.add_argument("--frame-start", type=int, default=1)
    p.add_argument("--frame-end", type=int, default=1)
    p.add_argument("--output", default="//render")
    p.add_argument("--format", default="PNG")
    p.add_argument("--info", action="store_true")
    p.set_defaults(func=lambda args: (
        print(get_blender_info()) if args.info else (
            render_frame(args.blend_file, args.frame, args.engine, args.output, args.format)
            if args.frame else
            render_blender(args.blend_file, args.engine, args.frame_start, args.frame_end, args.output, args.format)
        ),
        0
    )[1])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())