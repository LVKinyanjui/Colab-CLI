"""Main CLI Entry Point for Colab CLI.

Provides subcommands for all modules.
"""

import argparse
import sys

from .ssh_x11 import setup_x11_forwarding
from .xdg_runtime import setup_xdg_runtime_dir
from .blender_install import install_blender
from .sample_files import download_sample_file, download_all_samples
from .blender_ops import render_blender, render_frame, get_blender_info
from .colab_job import ColabJob, ColabJobConfig


def cmd_ssh_x11(args: argparse.Namespace) -> int:
    """Configure SSH for X11 forwarding."""
    setup_x11_forwarding()
    return 0


def cmd_xdg_runtime(args: argparse.Namespace) -> int:
    """Configure XDG_RUNTIME_DIR."""
    setup_xdg_runtime_dir()
    return 0


def cmd_blender_install(args: argparse.Namespace) -> int:
    """Install Blender."""
    install_blender(
        version=args.version,
        url_base=args.url_base,
        install_path=args.install_path,
    )
    return 0


def cmd_sample_files(args: argparse.Namespace) -> int:
    """Download sample .blend files."""
    if args.list:
        from .sample_files import SAMPLE_FILES
        print("Available samples:")
        for name, url in SAMPLE_FILES.items():
            print(f"  {name}: {url}")
        return 0

    if args.all:
        download_all_samples(args.output_dir)
        return 0

    if args.name:
        download_sample_file(args.name, args.output_dir, args.url)
        return 0

    print("Error: specify --name, --all, or --list")
    return 1


def cmd_blender_ops(args: argparse.Namespace) -> int:
    """Blender rendering operations."""
    if args.info:
        print(get_blender_info())
        return 0

    if not args.blend_file:
        print("Error: --blend-file required")
        return 1

    if args.frame is not None:
        render_frame(
            blend_file=args.blend_file,
            frame=args.frame,
            engine=args.engine,
            output_path=args.output,
            output_format=args.format,
        )
    else:
        render_blender(
            blend_file=args.blend_file,
            engine=args.engine,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            output_path=args.output,
            output_format=args.format,
        )
    return 0


def cmd_colab_job(args: argparse.Namespace) -> int:
    """Run a Colab job."""
    config = ColabJobConfig(
        script_path=args.script,
        gpu_type=args.gpu,
        high_mem=args.high_mem,
        log_dir=args.log_dir,
        session_name=args.name,
        remote_files=args.file,
        dry_run=args.dry_run,
    )
    job = ColabJob(config)
    return job.run()


def cmd_setup(args: argparse.Namespace) -> int:
    """Run full setup: SSH X11, XDG runtime, Blender install."""
    print("=== Running Full Setup ===")
    print("\n1. Configuring SSH X11 forwarding...")
    setup_x11_forwarding()

    print("\n2. Configuring XDG_RUNTIME_DIR...")
    setup_xdg_runtime_dir()

    print("\n3. Installing Blender...")
    install_blender()

    print("\n=== Setup Complete ===")
    print("Run 'source ~/.bashrc' to apply XDG_RUNTIME_DIR changes")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Convenience: install blender, download sample, and render."""
    print("=== Quick Render Pipeline ===")

    print("\n1. Installing Blender...")
    install_blender()

    print(f"\n2. Downloading sample: {args.sample}...")
    blend_path = download_sample_file(args.sample, ".")

    print(f"\n3. Rendering {blend_path}...")
    render_frame(
        blend_file=str(blend_path),
        frame=args.frame,
        engine=args.engine,
    )

    print("\n=== Render Complete ===")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="colab-cli",
        description="Colab CLI - Automate Google Cloud VM setup, processing, and teardown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # ssh-x11
    p = subparsers.add_parser("ssh-x11", help="Configure SSH for X11 forwarding")
    p.set_defaults(func=cmd_ssh_x11)

    # xdg-runtime
    p = subparsers.add_parser("xdg-runtime", help="Configure XDG_RUNTIME_DIR in ~/.bashrc")
    p.set_defaults(func=cmd_xdg_runtime)

    # blender-install
    p = subparsers.add_parser("blender-install", help="Download and install Blender")
    p.add_argument("--version", default="blender-5.1.2-linux-x64", help="Blender version")
    p.add_argument("--url-base", default="https://download.blender.org/release/Blender5.1", help="Download base URL")
    p.add_argument("--install-path", default="/usr/local/bin/blender", help="Symlink destination")
    p.set_defaults(func=cmd_blender_install)

    # sample-files
    p = subparsers.add_parser("sample-files", help="Download sample .blend files")
    p.add_argument("--name", help="Sample name (loft, mr_elephant, classroom, bmw, pavilion)")
    p.add_argument("--url", help="Custom URL")
    p.add_argument("--output-dir", default=".", help="Output directory")
    p.add_argument("--all", action="store_true", help="Download all samples")
    p.add_argument("--list", action="store_true", help="List available samples")
    p.set_defaults(func=cmd_sample_files)

    # blender-ops
    p = subparsers.add_parser("blender-ops", help="Blender rendering operations")
    p.add_argument("--blend-file", help="Path to .blend file")
    p.add_argument("--engine", default="CYCLES", help="Render engine")
    p.add_argument("--frame", type=int, help="Render single frame")
    p.add_argument("--frame-start", type=int, default=1, help="Start frame")
    p.add_argument("--frame-end", type=int, default=1, help="End frame")
    p.add_argument("--output", default="//render", help="Output path")
    p.add_argument("--format", default="PNG", help="Output format")
    p.add_argument("--info", action="store_true", help="Show Blender version info")
    p.set_defaults(func=cmd_blender_ops)

    # colab-job
    p = subparsers.add_parser("colab-job", help="Run a job on Colab VM")
    p.add_argument("-s", "--script", required=True, help="Path to Python script")
    p.add_argument("-f", "--file", action="append", default=[], help="Remote file to download")
    p.add_argument("-g", "--gpu", default="T4", help="GPU type")
    p.add_argument("--high-mem", action="store_true", help="High memory machine")
    p.add_argument("-l", "--log-dir", default="./logs", help="Log directory")
    p.add_argument("-n", "--name", default="", help="Session name")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    p.set_defaults(func=cmd_colab_job)

    # setup (full setup)
    p = subparsers.add_parser("setup", help="Run full setup (ssh-x11, xdg-runtime, blender-install)")
    p.set_defaults(func=cmd_setup)

    # render (quick pipeline)
    p = subparsers.add_parser("render", help="Quick pipeline: install blender, download sample, render")
    p.add_argument("--sample", default="mr_elephant", help="Sample to render")
    p.add_argument("--frame", type=int, default=1, help="Frame to render")
    p.add_argument("--engine", default="CYCLES", help="Render engine")
    p.set_defaults(func=cmd_render)

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())