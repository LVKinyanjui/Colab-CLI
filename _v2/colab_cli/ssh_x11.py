"""SSH X11 Forwarding Configuration Module.

Configures /etc/ssh/sshd_config for X11 forwarding to enable remote GUI applications.
Can be run independently or imported as a module.
"""

import re
import subprocess
from pathlib import Path

SSHD_CONFIG = Path("/etc/ssh/sshd_config")
SSHD_PID = Path("/var/run/sshd.pid")

SSH_SETTINGS = {
    "AllowTcpForwarding": "yes",
    "X11Forwarding": "yes",
    "X11DisplayOffset": "10",
    "X11UseLocalhost": "yes",
}

SSH_MARKER_START = "# --- managed X11 forwarding ---"
SSH_MARKER_END = "# --- end managed X11 forwarding ---"


def sudo(*args, **kwargs):
    """Run command with sudo."""
    return subprocess.run(["sudo", *map(str, args)], check=True, **kwargs)


def setup_x11_forwarding() -> None:
    """Configure SSH for X11 forwarding.

    This function:
    1. Removes any previously managed block
    2. Removes existing global definitions of our settings
    3. Prepends our managed block at the top of the file
    4. Validates the config
    5. Reloads sshd
    """
    content = SSHD_CONFIG.read_text()

    # Remove our previous managed block.
    pattern = rf"{re.escape(SSH_MARKER_START)}.*?{re.escape(SSH_MARKER_END)}\n?"
    content = re.sub(pattern, "", content, flags=re.S)

    # Remove existing global definitions so ours become the first value.
    lines = []
    in_match = False

    for line in content.splitlines():
        if re.match(r"^\s*Match\b", line, re.I):
            in_match = True

        if not in_match and any(
            re.match(rf"^\s*#?\s*{key}\b", line, re.I)
            for key in SSH_SETTINGS
        ):
            continue

        lines.append(line)

    managed = "\n".join(
        [SSH_MARKER_START]
        + [f"{key} {value}" for key, value in SSH_SETTINGS.items()]
        + [SSH_MARKER_END, ""]
    )

    new_content = managed + "\n".join(lines) + "\n"

    # Write through sudo while preserving the rest of the file.
    sudo("tee", SSHD_CONFIG, input=new_content, text=True,
         stdout=subprocess.DEVNULL)

    print("\n--- validating sshd config ---")
    sudo("/usr/sbin/sshd", "-t", "-f", SSHD_CONFIG)

    print("\n--- reloading sshd ---")
    pid = SSHD_PID.read_text().strip()
    sudo("kill", "-HUP", pid)

    print("\n--- effective X11Forwarding ---")
    result = sudo("/usr/sbin/sshd", "-T", "-f", SSHD_CONFIG,
                  capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if line.startswith("x11forwarding "):
            print(line)


def main() -> None:
    """Entry point when run as a script."""
    setup_x11_forwarding()


if __name__ == "__main__":
    main()