import os
import re
import signal
import subprocess
import time

ps = subprocess.check_output(
    ["ps", "-eo", "pid=,ppid=,user=,args="], text=True
)

listener = None
sessions = []

for line in ps.splitlines():
    line = line.strip()

    # sshd listener
    m = re.match(r"(\d+)\s+(\d+)\s+(\S+)\s+sshd: /usr/sbin/sshd \[listener\].*", line)
    if m:
        listener = (int(m.group(1)), int(m.group(2)), m.group(3))
        continue

    # Interactive SSH sessions
    m = re.match(r"(\d+)\s+(\d+)\s+(\S+)\s+sshd:\s+(.+@pts/\d+)", line)
    if m:
        sessions.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)))

print("\n=== SSH SERVER ===")
if listener:
    print(f"Listener: PID={listener[0]} PPID={listener[1]} USER={listener[2]}")
else:
    print("WARNING: sshd listener not found!")

print("\n=== SSH SESSIONS ===")
if sessions:
    for pid, ppid, user, session in sessions:
        print(f"PID={pid} PPID={ppid} USER={user} SESSION={session}")
else:
    print("No interactive SSH sessions found.")

if sessions:
    print("\nThese session processes will be terminated.")
    answer = input("Continue? [y/N]: ").strip().lower()

    if answer == "y":
        for pid, _, _, _ in sessions:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        time.sleep(1)

        for pid, _, _, _ in sessions:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        print("\nSSH sessions cleared.")
        if listener:
            print(f"sshd listener remains running (PID {listener[0]}).")
    else:
        print("Aborted; no SSH sessions were terminated.")
