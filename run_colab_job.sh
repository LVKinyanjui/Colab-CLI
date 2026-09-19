#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration Defaults
# -----------------------------------------------------------------------------
GPU_TYPE="T4"
HIGH_MEM=false
LOG_DIR="./logs"
SESSION_NAME="job-$(date +%Y%m%d-%H%M%S)-$RANDOM"
SCRIPT_PATH=""
REMOTE_FILES=()

# -----------------------------------------------------------------------------
# Help & Usage
# -----------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") -s <script.py> [options]

Options:
  -s, --script <path>        Path to local Python script to execute (Required)
  -f, --file <remote_path>   Remote file to download upon success (can be passed multiple times)
  -g, --gpu <type>           GPU type (default: T4; options: T4, L4, A100, etc.)
  --high-mem                 Request high-RAM machine shape (requires Pro/Pro+)
  -l, --log-dir <path>       Directory to store local execution logs (default: ./logs)
  -n, --name <name>          Custom Colab session name
  -h, --help                 Show this help message

Example:
  $(basename "$0") -s train.py -f checkpoint.pt -f results.csv
EOF
  exit 1
}

# -----------------------------------------------------------------------------
# Argument Parsing
# -----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--script)
      SCRIPT_PATH="$2"
      shift 2
      ;;
    -f|--file)
      REMOTE_FILES+=("$2")
      shift 2
      ;;
    -g|--gpu)
      GPU_TYPE="$2"
      shift 2
      ;;
    --high-mem)
      HIGH_MEM=true
      shift 1
      ;;
    -l|--log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    -n|--name)
      SESSION_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ -z "$SCRIPT_PATH" ]]; then
  echo "[ERROR] Missing required -s / --script argument." >&2
  usage
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "[ERROR] Script file not found: $SCRIPT_PATH" >&2
  exit 1
fi

# Ensure log directory exists
mkdir -p "$LOG_DIR"

SESSION_LOG="${LOG_DIR}/${SESSION_NAME}_stdout.log"
ERR_LOG="${LOG_DIR}/${SESSION_NAME}_stderr.log"
COLAB_HIST_LOG="${LOG_DIR}/${SESSION_NAME}_colab_history.txt"

# -----------------------------------------------------------------------------
# Teardown & Cleanup Handler (Guarantees VM stop)
# -----------------------------------------------------------------------------
SESSION_CREATED=false

cleanup() {
  local exit_code=$?
  echo ""
  echo "=================================================="
  if [[ "$SESSION_CREATED" == true ]]; then
    echo "[INFO] Attempting to export session history before termination..."
    colab log -s "$SESSION_NAME" -o "$COLAB_HIST_LOG" 2>/dev/null || true

    echo "[INFO] Stopping remote Colab session: ${SESSION_NAME}..."
    if colab stop -s "$SESSION_NAME" >/dev/null 2>&1; then
      echo "[INFO] Session ${SESSION_NAME} stopped successfully."
    else
      echo "[WARNING] Failed to cleanly stop session ${SESSION_NAME} via CLI." >&2
    fi
  fi

  if [[ $exit_code -ne 0 ]]; then
    echo "[FAIL] Job exited with status code $exit_code." >&2
    echo "[FAIL] Check error log: $ERR_LOG" >&2
  else
    echo "[SUCCESS] Job completed successfully."
  fi
  echo "=================================================="
}
trap cleanup EXIT INT TERM

# -----------------------------------------------------------------------------
# 1. Provision VM Runtime
# -----------------------------------------------------------------------------
echo "[1/4] Provisioning Colab VM (Session: $SESSION_NAME, GPU: $GPU_TYPE)..."

NEW_CMD=("colab" "new" "-s" "$SESSION_NAME" "--gpu" "$GPU_TYPE")
if [[ "$HIGH_MEM" == true ]]; then
  NEW_CMD+=("--high-mem")
fi

if ! "${NEW_CMD[@]}" 2> >(tee -a "$ERR_LOG" >&2); then
  echo "[ERROR] Failed to allocate Colab runtime. See $ERR_LOG for details." >&2
  exit 1
fi
SESSION_CREATED=true

# -----------------------------------------------------------------------------
# 2. Execute Script & Stream Logs
# -----------------------------------------------------------------------------
echo "[2/4] Executing $SCRIPT_PATH on session $SESSION_NAME..."
echo "[INFO] Live stdout logging to: $SESSION_LOG"
echo "[INFO] Live stderr logging to: $ERR_LOG"
echo "--- Remote Output Start ---"

# colab exec transmits local script content to remote kernel directly
# Uses tee so verbose output is streamed to console and persisted to disk
if ! colab exec -s "$SESSION_NAME" -f "$SCRIPT_PATH" \
      2> >(tee -a "$ERR_LOG" >&2) \
      | tee -a "$SESSION_LOG"; then
  echo "--- Remote Output End ---"
  echo "[ERROR] Remote script execution failed!" >&2
  exit 2
fi

echo "--- Remote Output End ---"
echo "[INFO] Script execution finished successfully."

# -----------------------------------------------------------------------------
# 3. Retrieve Remote Files
# -----------------------------------------------------------------------------
if [[ ${#REMOTE_FILES[@]} -gt 0 ]]; then
  echo "[3/4] Downloading generated artifacts to local directory ($(pwd))..."
  for remote_file in "${REMOTE_FILES[@]}"; do
    local_target="./$(basename "$remote_file")"
    echo "  -> Downloading remote '$remote_file' to '$local_target'..."
    if ! colab download -s "$SESSION_NAME" "$remote_file" "$local_target" 2> >(tee -a "$ERR_LOG" >&2); then
      echo "[ERROR] Failed to download file: $remote_file" >&2
      exit 3
    fi
  done
else
  echo "[3/4] No download files specified (-f/--file). Skipping download."
fi

# -----------------------------------------------------------------------------
# 4. Finalizing
# -----------------------------------------------------------------------------
echo "[4/4] All steps succeeded. Preparing to tear down compute resources..."
