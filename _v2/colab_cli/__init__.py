"""Colab CLI - Automate Google Cloud VM setup, processing, and teardown."""

from .ssh_x11 import setup_x11_forwarding, main as ssh_x11_main
from .xdg_runtime import setup_xdg_runtime_dir, main as xdg_runtime_main
from .blender_install import install_blender, main as blender_install_main
from .sample_files import download_sample_file, main as sample_files_main
from .blender_ops import render_blender, main as blender_ops_main
from .colab_job import ColabJob, main as colab_job_main

__all__ = [
    "setup_x11_forwarding",
    "ssh_x11_main",
    "setup_xdg_runtime_dir",
    "xdg_runtime_main",
    "install_blender",
    "blender_install_main",
    "download_sample_file",
    "sample_files_main",
    "render_blender",
    "blender_ops_main",
    "ColabJob",
    "colab_job_main",
]

__version__ = "0.1.0"