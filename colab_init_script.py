import re
import shutil
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

XDG_MARKER_START = "# --- XDG runtime directory for remote GUI applications ---"
XDG_MARKER_END = "# --- end XDG runtime directory ---"


def sudo(*args, **kwargs):
    return subprocess.run(["sudo", *map(str, args)], check=True, **kwargs)


def setup_x11():
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
    pid = subprocess.check_output(
        ["sudo", "cat", SSHD_PID], text=True
    ).strip()
    sudo("kill", "-HUP", pid)

    print("\n--- effective X11 configuration ---")
    result = subprocess.check_output(
        ["sudo", "/usr/sbin/sshd", "-T", "-f", SSHD_CONFIG],
        text=True,
    )

    for line in result.splitlines():
        if re.match(r"^(x11forwarding|x11displayoffset|x11uselocalhost|allowtcpforwarding) ", line):
            print(line)

    print("\n--- /etc/ssh/sshd_config ---")
    print(new_content)


def setup_xdg():
    bashrc = Path.home() / ".bashrc"
    content = bashrc.read_text() if bashrc.exists() else ""

    if XDG_MARKER_START not in content:
        block = f"""
{XDG_MARKER_START}
export XDG_RUNTIME_DIR="/tmp/blender-runtime-$USER"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
{XDG_MARKER_END}
"""
        bashrc.open("a").write(block)

    # Create it immediately as well, rather than waiting for a new shell.
    runtime_dir = Path(f"/tmp/blender-runtime-{Path.home().name}")
    runtime_dir.mkdir(mode=0o700, exist_ok=True)
    runtime_dir.chmod(0o700)

    print(f"Configured {bashrc}")
    print(f"Runtime directory: {runtime_dir}")


def check_xauth():
    xauth = shutil.which("xauth")

    if xauth:
        print(f"xauth found: {xauth}")
    else:
        print("WARNING: xauth is not installed; X11 forwarding may not work.")


def main():
    print("=== X11 / Remote GUI setup ===")
    setup_x11()
    setup_xdg()
    check_xauth()
    print("\n=== setup complete ===")
    print("Open a new shell or run: source ~/.bashrc")


if __name__ == "__main__":
    main()
