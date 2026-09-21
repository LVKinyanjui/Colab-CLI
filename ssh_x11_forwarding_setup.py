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

script += r"""
printf '\n--- /etc/ssh/sshd_config ---\n'
cat /etc/ssh/sshd_config

printf '\n--- validating config ---\n'
/usr/sbin/sshd -t -f /etc/ssh/sshd_config

printf '\n--- reloading sshd ---\n'
kill -HUP "$(cat /var/run/sshd.pid)"

printf '\n--- effective X11Forwarding ---\n'
/usr/sbin/sshd -T -f /etc/ssh/sshd_config | grep -E '^x11forwarding '
"""

subprocess.run(["sudo", "sh", "-c", script], check=True)


