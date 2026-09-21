import subprocess
import os

# Helper Command
# Allows quality of life additions to running the command
def run_command(cmd):
  ret = subprocess.run(cmd,
                capture_output=True,
                check = True,   # Allows error checking for non zero exit status
                text=True   # Sets text mode for stdin and stdout, rather than the default bytes
  )
  return ret

version = "blender-5.1.2-linux-x64"
version_file = f"{version}.tar.xz"

# Download
# NEXT STEPS
# Wrap with decorator to ensure future shell commands are executed with the same 'addons'
if not os.path.exists(version_file):
  run_command(["wget", f"https://download.blender.org/release/Blender5.1/{version_file}"])

# Extract
if not os.path.exists(version):
  run_command(['tar', '-xf', version_file])

# Symlinking
import subprocess

# Colab Path Dependency!
run_command(["ln", "-sf", f"/content/{version}/blender", "/usr/local/bin/blender"])

!blender --version
