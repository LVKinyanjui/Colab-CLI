import subprocess

ret = subprocess.run(["git", "clone", "https://github.com/LVKinyanjui/Colab-CLI"], check=True, capture_output=True)
print(ret)
