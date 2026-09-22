"""Sample Blend Files Download Module.

Downloads sample .blend files from the Blender demo site.
Can be run independently or imported as a module.
"""

import subprocess
from pathlib import Path


SAMPLE_FILES = {
    "loft": "https://download.blender.org/demo/cycles/loft.blend",
    "mr_elephant": "https://download.blender.org/demo/eevee/mr_elephant/mr_elephant.blend",
    "classroom": "https://download.blender.org/demo/cycles/classroom/classroom.blend",
    "bmw": "https://download.blender.org/demo/cycles/bmw/bmw27.blend",
    "pavilion": "https://download.blender.org/demo/cycles/pavilion/pavilion.blend",
}


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command with error checking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        text=True,
    )


def download_sample_file(
    name: str,
    output_dir: str = ".",
    url: str | None = None,
) -> Path:
    """Download a sample .blend file.

    Args:
        name: Name of the sample (key in SAMPLE_FILES) or custom filename
        output_dir: Directory to save the file
        url: Custom URL (if name not in SAMPLE_FILES)

    Returns:
        Path to the downloaded file
    """
    output_path = Path(output_dir)

    if url is None:
        if name not in SAMPLE_FILES:
            raise ValueError(f"Unknown sample: {name}. Available: {list(SAMPLE_FILES.keys())}")
        url = SAMPLE_FILES[name]
        filename = f"{name}.blend"
    else:
        filename = Path(url).name

    filepath = output_path / filename

    if filepath.exists():
        print(f"{filepath} already exists, skipping download")
        return filepath

    print(f"Downloading {url} to {filepath}...")
    run_command(["wget", "-O", str(filepath), url])

    return filepath


def download_all_samples(output_dir: str = ".") -> list[Path]:
    """Download all known sample files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    for name in SAMPLE_FILES:
        results.append(download_sample_file(name, output_dir))

    return results


def main() -> None:
    """Entry point when run as a script.

    Usage: python -m colab_cli.sample_files [sample_name] [output_dir]
    """
    import sys

    if len(sys.argv) > 1:
        sample_name = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        download_sample_file(sample_name, output_dir)
    else:
        print("Downloading all sample files...")
        download_all_samples(".")


if __name__ == "__main__":
    main()