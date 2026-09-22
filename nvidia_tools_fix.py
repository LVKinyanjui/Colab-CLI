#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NVIDIA_LIB_DIR = Path("/usr/lib64-nvidia")
NVIDIA_CONF = Path("/etc/ld.so.conf.d/nvidia.conf")

CUDA_HOME = Path("/usr/local/cuda")
CUDA_BIN = CUDA_HOME / "bin"
CUDA_PROFILE = Path("/etc/profile.d/cuda.sh")
NVCC_LINK = Path("/usr/local/bin/nvcc")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, env=None):
    """
    Run a command and return the CompletedProcess.
    Output is printed so the script is easy to diagnose.
    """
    cmd = [str(x) for x in cmd]

    print(f"+ {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )

    if result.stdout:
        print(result.stdout, end="")

    return result


def command_exists(command):
    """Check whether a command is available in PATH."""
    result = subprocess.run(
        ["bash", "-lc", f"command -v {command}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def is_root():
    return os.geteuid() == 0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_nvidia():
    """
    NVIDIA is considered healthy if:
      1. nvidia-smi exists
      2. nvidia-smi can initialize NVML successfully
    """
    print("\n[CHECK] NVIDIA")

    if not command_exists("nvidia-smi"):
        print("[!] nvidia-smi not found")
        return False

    result = run(["nvidia-smi"])

    if result.returncode == 0:
        print("[+] NVIDIA runtime is working")
        return True

    print("[!] nvidia-smi exists but cannot initialize NVIDIA")
    return False


def detect_nvml_library():
    """Check for the host-provided NVIDIA NVML library."""
    nvml = NVIDIA_LIB_DIR / "libnvidia-ml.so.1"

    print("\n[CHECK] NVIDIA runtime library")

    if nvml.exists():
        print(f"[+] Found {nvml}")
        return True

    print(f"[!] Missing {nvml}")
    return False


def detect_cuda():
    """
    CUDA is considered healthy if nvcc is available and executable.
    """
    print("\n[CHECK] CUDA")

    nvcc = CUDA_BIN / "nvcc"

    if not nvcc.exists():
        print(f"[!] Missing {nvcc}")
        return False

    result = run([nvcc, "--version"])

    if result.returncode == 0:
        print("[+] CUDA compiler is working")
        return True

    print("[!] nvcc exists but cannot execute")
    return False


def detect_cuda_path():
    """Check whether CUDA bin is present in the current Python process PATH."""
    print("\n[CHECK] CUDA PATH")

    path_entries = os.environ.get("PATH", "").split(":")

    cuda_bin = str(CUDA_BIN)

    if cuda_bin in path_entries:
        print(f"[+] {cuda_bin} is already in PATH")
        return True

    print(f"[!] {cuda_bin} is missing from PATH")
    return False


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def repair_nvidia_runtime():
    """
    Register the container's host-provided NVIDIA userspace libraries
    with the dynamic linker.
    """
    print("\n[REPAIR] NVIDIA runtime")

    nvml = NVIDIA_LIB_DIR / "libnvidia-ml.so.1"

    if not nvml.exists():
        print(f"[ERROR] Cannot repair: {nvml} does not exist")
        return False

    desired = f"{NVIDIA_LIB_DIR}\n"

    current = ""

    if NVIDIA_CONF.exists():
        current = NVIDIA_CONF.read_text()

    if current != desired:
        print(f"[+] Writing {NVIDIA_CONF}")
        NVIDIA_CONF.write_text(desired)
    else:
        print(f"[+] {NVIDIA_CONF} already correct")

    print("[+] Running ldconfig")
    result = run(["ldconfig"])

    if result.returncode != 0:
        print("[!] ldconfig returned an error")
        return False

    return detect_nvidia()


def repair_cuda_path():
    """
    Make CUDA available to:
      - future login shells
      - the current Python process
      - processes that rely on /usr/local/bin being in PATH
    """
    print("\n[REPAIR] CUDA PATH")

    if not CUDA_BIN.exists():
        print(f"[ERROR] CUDA bin directory missing: {CUDA_BIN}")
        return False

    # -----------------------------------------------------------------------
    # Future shells
    # -----------------------------------------------------------------------

    profile_contents = (
        f'export CUDA_HOME="{CUDA_HOME}"\n'
        'export PATH="$CUDA_HOME/bin:$PATH"\n'
    )

    current_profile = (
        CUDA_PROFILE.read_text()
        if CUDA_PROFILE.exists()
        else ""
    )

    if current_profile != profile_contents:
        print(f"[+] Writing {CUDA_PROFILE}")
        CUDA_PROFILE.write_text(profile_contents)
    else:
        print(f"[+] {CUDA_PROFILE} already correct")

    # -----------------------------------------------------------------------
    # Stable /usr/local/bin/nvcc path
    # -----------------------------------------------------------------------

    real_nvcc = CUDA_BIN / "nvcc"

    if real_nvcc.exists():

        if NVCC_LINK.is_symlink():
            target = NVCC_LINK.resolve()

            if target != real_nvcc:
                print(
                    f"[+] Correcting {NVCC_LINK} "
                    f"-> {real_nvcc}"
                )
                NVCC_LINK.unlink()
                NVCC_LINK.symlink_to(real_nvcc)

        elif NVCC_LINK.exists():
            print(
                f"[!] {NVCC_LINK} exists and is not a symlink; "
                f"leaving it untouched"
            )

        else:
            print(f"[+] Creating {NVCC_LINK} -> {real_nvcc}")
            NVCC_LINK.symlink_to(real_nvcc)

    # -----------------------------------------------------------------------
    # Current Python process
    # -----------------------------------------------------------------------

    os.environ["CUDA_HOME"] = str(CUDA_HOME)

    path_entries = os.environ.get("PATH", "").split(":")

    cuda_bin = str(CUDA_BIN)

    if cuda_bin not in path_entries:
        os.environ["PATH"] = (
            f"{cuda_bin}:"
            f"{os.environ.get('PATH', '')}"
        )

        print(f"[+] Added {cuda_bin} to current PATH")

    # -----------------------------------------------------------------------
    # Verify
    # -----------------------------------------------------------------------

    return detect_cuda()


# ---------------------------------------------------------------------------
# Main detector / repair logic
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print(" NVIDIA / CUDA ENVIRONMENT DETECTOR + AUTO-REPAIR")
    print("=" * 72)

    if not is_root():
        print()
        print("[ERROR] This script must run as root.")
        print("In Colab this normally means invoking it with appropriate")
        print("root privileges.")
        return 1

    # -----------------------------------------------------------------------
    # Initial detection
    # -----------------------------------------------------------------------

    nvidia_ok = detect_nvidia()
    nvml_ok = detect_nvml_library()
    cuda_ok = detect_cuda()
    path_ok = detect_cuda_path()

    # -----------------------------------------------------------------------
    # NVIDIA repair
    # -----------------------------------------------------------------------

    if not nvidia_ok or not nvml_ok:
        print("\n[!] NVIDIA environment requires repair")
        nvidia_ok = repair_nvidia_runtime()
    else:
        print("\n[+] NVIDIA environment already healthy")

    # -----------------------------------------------------------------------
    # CUDA repair
    # -----------------------------------------------------------------------

    if not cuda_ok or not path_ok:
        print("\n[!] CUDA environment requires repair")
        cuda_ok = repair_cuda_path()
    else:
        print("\n[+] CUDA environment already healthy")

    # -----------------------------------------------------------------------
    # Final verification
    # -----------------------------------------------------------------------

    print("\n" + "=" * 72)
    print(" FINAL VERIFICATION")
    print("=" * 72)

    final_nvidia = detect_nvidia()
    final_nvml = detect_nvml_library()
    final_cuda = detect_cuda()
    final_path = detect_cuda_path()

    print("\n" + "=" * 72)
    print(" RESULT")
    print("=" * 72)

    results = {
        "NVIDIA / nvidia-smi": final_nvidia,
        "NVIDIA NVML library": final_nvml,
        "CUDA / nvcc": final_cuda,
        "CUDA PATH": final_path,
    }

    all_ok = True

    for name, status in results.items():
        print(
            f"{'[OK]  ' if status else '[FAIL]'} "
            f"{name}"
        )

        if not status:
            all_ok = False

    print()

    print(f"CUDA_HOME = {os.environ.get('CUDA_HOME', '<not set>')}")
    print(f"PATH      = {os.environ.get('PATH', '')}")

    print()

    if all_ok:
        print("[SUCCESS] NVIDIA/CUDA environment is operational.")
        return 0

    print("[WARNING] Environment is still partially broken.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

