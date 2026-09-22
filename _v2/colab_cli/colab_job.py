"""Colab Job Orchestration Module.

Provisions a Google Cloud VM, executes a script, downloads results, and cleans up.
Converted from incomplete_run_colab_job.sh to Python.
Can be run independently or imported as a module.
"""

import argparse
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ColabJobConfig:
    """Configuration for a Colab job."""
    script_path: str
    gpu_type: str = "T4"
    high_mem: bool = False
    log_dir: str = "./logs"
    session_name: str = ""
    remote_files: list[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class ColabJob:
    """Orchestrates a Colab VM job lifecycle."""
    config: ColabJobConfig
    start_time: float = field(default_factory=time.time)
    session_name: str = ""

    def __post_init__(self):
        if not self.session_name:
            self.session_name = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:5]}"

    def format_duration(self, total_sec: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        total_sec = int(total_sec)
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        return f"{h:02d}h:{m:02d}m:{s:02d}s ({total_sec}s)"

    def run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a command with logging."""
        print(f"Running: {' '.join(cmd)}")
        if self.config.dry_run:
            print("[DRY RUN] Skipping execution")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def setup_logging(self) -> tuple[Path, Path]:
        """Set up log directory and files."""
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = log_dir / f"{self.session_name}_stdout.log"
        stderr_log = log_dir / f"{self.session_name}_stderr.log"

        return stdout_log, stderr_log

    def provision_vm(self) -> str:
        """Provision the Colab VM. Returns the session ID."""
        # This would use gcloud or Colab API to provision
        # For now, return a placeholder
        print(f"Provisioning VM: {self.session_name} (GPU: {self.config.gpu_type})")
        if self.config.dry_run:
            return "dry-run-session-id"

        # TODO: Implement actual VM provisioning via gcloud/Colab API
        raise NotImplementedError("VM provisioning not yet implemented - use gcloud directly")

    def upload_script(self, session_id: str) -> None:
        """Upload the script to the VM."""
        print(f"Uploading {self.config.script_path} to {session_id}")
        # TODO: Implement via gcloud compute scp

    def execute_script(self, session_id: str) -> int:
        """Execute the script on the VM. Returns exit code."""
        print(f"Executing script on {session_id}")
        # TODO: Implement via gcloud compute ssh
        raise NotImplementedError("Remote execution not yet implemented")

    def download_files(self, session_id: str) -> None:
        """Download result files from the VM."""
        for remote_file in self.config.remote_files:
            print(f"Downloading {remote_file} from {session_id}")
            # TODO: Implement via gcloud compute scp

    def cleanup_vm(self, session_id: str) -> None:
        """Clean up the VM."""
        print(f"Cleaning up VM: {session_id}")
        # TODO: Implement via gcloud compute instances delete

    def run(self) -> int:
        """Run the complete job lifecycle."""
        print(f"=== Starting Colab Job: {self.session_name} ===")
        print(f"Script: {self.config.script_path}")
        print(f"GPU: {self.config.gpu_type}")
        print(f"High Memory: {self.config.high_mem}")
        print(f"Log Dir: {self.config.log_dir}")

        stdout_log, stderr_log = self.setup_logging()
        print(f"Logs: {stdout_log}, {stderr_log}")

        session_id = ""
        exit_code = 1

        try:
            session_id = self.provision_vm()
            self.upload_script(session_id)
            exit_code = self.execute_script(session_id)

            if exit_code == 0 and self.config.remote_files:
                self.download_files(session_id)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            exit_code = 1

        finally:
            if session_id and not self.config.dry_run:
                self.cleanup_vm(session_id)

        duration = time.time() - self.start_time
        print(f"=== Job Complete: {self.session_name} ===")
        print(f"Duration: {self.format_duration(duration)}")
        print(f"Exit Code: {exit_code}")

        return exit_code


def main() -> int:
    """Entry point when run as a script."""
    parser = argparse.ArgumentParser(
        description="Run a Python script on a Google Cloud Colab VM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s", "--script",
        required=True,
        help="Path to local Python script to execute",
    )
    parser.add_argument(
        "-f", "--file",
        action="append",
        default=[],
        help="Remote file to download upon success (repeatable)",
    )
    parser.add_argument(
        "-g", "--gpu",
        default="T4",
        help="GPU type (default: T4; options: T4, L4, A100, etc.)",
    )
    parser.add_argument(
        "--high-mem",
        action="store_true",
        help="Request high-RAM machine shape (requires Pro/Pro+)",
    )
    parser.add_argument(
        "-l", "--log-dir",
        default="./logs",
        help="Directory to store local execution logs",
    )
    parser.add_argument(
        "-n", "--name",
        default="",
        help="Custom Colab session name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing",
    )

    args = parser.parse_args()

    config = ColabJobConfig(
        script_path=args.script,
        gpu_type=args.gpu,
        high_mem=args.high_mem,
        log_dir=args.log_dir,
        session_name=args.name,
        remote_files=args.file,
        dry_run=args.dry_run,
    )

    job = ColabJob(config)
    return job.run()


if __name__ == "__main__":
    sys.exit(main())