#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration Defaults & Timers
# -----------------------------------------------------------------------------
JOB_START_TIME=$(date +%s)
EXEC_DURATION_STR="N/A (did not finish)"

GPU_TYPE="T4"
HIGH_MEM=false
LOG_DIR="./logs"
SESSION_NAME="job-$(date +%Y%m%d-%H%M%S)-$RANDOM"
SCRIPT_PATH=""
REMOTE_FILES=()

# Helper function to convert seconds into HH:MM:SS
format_duration() {
  local total_sec=$1
  local h=$((total_sec / 3600))
  local m=$(( (total_sec % 3600) / 60 ))
  local s=$((total_sec % 60))
  printf "%02dh:%02dm:%02ds (%ds)" "$h" "$m" "$s" "$total_sec"
}

# -----------------------------------------------------------------------------
# Help & Usage
# -----------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") -s <script.py> [options]

Options:
  -s, --script <path>        Path to local Python script to execute (Required)
  -f, --file <remote_path>   Remote file to download upon success (repeatable)
  -g, --gpu <type>           GPU type (default: T4; options: T4, L4, A100, etc.)
  --high-mem                 Request high-RAM machine shape (requires Pro/Pro+)
  -l, --log-dir <path>       Directory to store local execution logs (default: ./logs)
  -n, --name <name>          Custom Colab session name
  -h, --help                 Show this help message
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

mkdir -p "$LOG_DIR"
SESSION_LOG="${LOG_DIR}/${SESSION_NAME}_stdout.log"
ERR_LOG="${LOG_DIR}/${SESSION_NAME}_stderr.log"
COLAB_HIST_LOG="${LOG_DIR}/${SESSION_NAME}_colab_history.txt"

# -----------------------------------------------------------------------------
# Teardown & Summary Handler
# -----------------------------------------------------------------------------
SESSION_CREATED=false

cleanup() {
  local exit_code=$?
  local job_end_time
  job_end_time=$(date +%s)
  local total_duration=$((job_end_time - JOB_START_TIME))
  local total_duration_str
  total_duration_str=$(format_duration "$total_duration")

  echo ""
  echo "=================================================="
  echo "                EXECUTION SUMMARY                 "
  echo "=================================================="
  echo "[TIME] Script Run Duration : $EXEC_DURATION_STR"
  echo "[TIME] Total Job Duration  : $total_duration_str"

  # Log timings to the stdout log file as well
  {
    echo ""
    echo "=== Summary ==="
    echo "Script Run Duration : $EXEC_DURATION_STR"
    echo "Total Job Duration  : $total_duration_str"
  } >> "$SESSION_LOG" 2>/dev/null || true

  if [[ "$SESSION_CREATED" == true ]]; then
    echo "[INFO] Exporting session history..."
    colab log -s "$SESSION_NAME" -o "$COLAB_HIST_LOG" 2>/dev/null || true

    echo "[INFO] Stopping remote Colab session: ${SESSION_NAME}..."
    colab stop -s "$SESSION_NAME" >/dev/null 2>&1 || true
    echo "[INFO] Session stopped."
  fi

  if [[ $exit_code -ne 0 ]]; then
    echo "[FAIL] Job exited with error code $exit_code." >&2
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
  echo "[ERROR] Failed to allocate Colab runtime." >&2
  exit 1
fi
SESSION_CREATED=true

# -----------------------------------------------------------------------------
# 2. Execute Script & Measure Execution Time
# -----------------------------------------------------------------------------
echo "[2/4] Executing $SCRIPT_PATH on session $SESSION_NAME..."
echo "[INFO] Live stdout logging to: $SESSION_LOG"
echo "[INFO] Live stderr logging to: $ERR_LOG"
echo "--- Remote Output Start ---"

EXEC_START=$(date +%s)

# Run and stream logs
if ! colab exec -s "$SESSION_NAME" -f "$SCRIPT_PATH" \
      2> >(tee -a "$ERR_LOG" >&2) \
      | tee -a "$SESSION_LOG"; then
  EXEC_END=$(date +%s)
  EXEC_DURATION_STR=$(format_duration "$((EXEC_END - EXEC_START)) (FAILED)")
  echo "--- Remote Output End ---"
  echo "[ERROR] Remote script execution failed!" >&2
  exit 2
fi

EXEC_END=$(date +%s)
EXEC_DURATION_STR=$(format_duration "$((EXEC_END - EXEC_START))")

echo "--- Remote Output End ---"
echo "[INFO] Script execution finished in: $EXEC_DURATION_STR"

# -----------------------------------------------------------------------------
# 3. Retrieve Remote Files
# -----------------------------------------------------------------------------
if [[ ${#REMOTE_FILES[@]} -gt 0 ]]; then
  echo "[3/4] Downloading ${#REMOTE_FILES[@]} artifact(s)..."
  for remote_file in "${REMOTE_FILES[@]}"; do
    local_target="./$(basename "$remote_file")"
    echo "  -> Downloading '$remote_file' to '$local_target'..."
    if ! colab download -s "$SESSION_NAME" "$remote_file" "$local_target" 2> >(tee -a "$ERR_LOG" >&2); then
      echo "[ERROR] Failed to download: $remote_file" >&2
      exit 3
    fi
  done
else
  echo "[3/4] No download files specified (-f/--file). Skipping download."
fi

# -----------------------------------------------------------------------------
# 4. Finalizing
# -----------------------------------------------------------------------------
echo "[4/4] All tasks finished. Cleaning up..."
