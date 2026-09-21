import subprocess

settings = {
    "AllowTcpForwarding": "yes",
    "X11Forwarding": "yes",
    "X11DisplayOffset": "10",
    "X11UseLocalhost": "yes",
}

script = ""
for key, value in settings.items():
    script += f"""
grep -qE '^[[:space:]]*{key}[[:space:]]+{value}[[:space:]]*$' /etc/ssh/sshd_config || {{
    sed -i -E '/^[[:space:]]*#?[[:space:]]*{key}[[:space:]]+/d' /etc/ssh/sshd_config
    echo '{key} {value}' >> /etc/ssh/sshd_config
}}
"""
script += "\nprintf '\\n--- /etc/ssh/sshd_config ---\\n'; cat /etc/ssh/sshd_config\n"

subprocess.run(["sudo", "sh", "-c", script], check=True)

ret = subprocess.run(["which", "xauth"], capture_output=True)
print("XAUTH Status")
print(ret)
print("\n")

ret = subprocess.run(["echo", "$DISPLAY"])
print("Display")
print(ret)


