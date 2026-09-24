import subprocess

subprocess.run(["sudo", "apt", "update"], check=True)
subprocess.run(["sudo", "apt", "install", "nano", "-y"], check=True)


