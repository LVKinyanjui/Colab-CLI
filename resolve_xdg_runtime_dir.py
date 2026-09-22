from pathlib import Path

bashrc = Path.home() / ".bashrc"

block = r'''
# --- XDG runtime directory for remote GUI applications ---
export XDG_RUNTIME_DIR="/tmp/blender-runtime-$USER"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
# --- end XDG runtime directory ---
'''

content = bashrc.read_text() if bashrc.exists() else ""

if "# --- XDG runtime directory for remote GUI applications ---" not in content:
    bashrc.open("a").write("\n" + block)

print(f"Configured {bashrc}")
print("Open a new terminal or run: source ~/.bashrc")
