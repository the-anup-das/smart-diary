#!/usr/bin/env bash
# Serve a fine-tuned GGUF with llama.cpp's OpenAI-compatible server, on CPU or GPU.
#
#   ./scripts/serve_llama.sh                       # output/model_qwen_gguf/*.Q4_K_M.gguf on CPU
#   ./scripts/serve_llama.sh --gpu                 # offload every layer to the GPU
#   ./scripts/serve_llama.sh path/to/model.gguf --port 8080 --alias smart-diary-slm
#
# Needs llama-server on PATH (https://github.com/ggml-org/llama.cpp/releases) or `pip install llama-cpp-python[server]`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$HERE/../output"
MODEL=""
PORT="${LOCAL_LLM_PORT:-8080}"
ALIAS="${LOCAL_LLM_MODEL:-smart-diary-slm}"
CTX="${LOCAL_LLM_CTX:-8192}"
GPU_LAYERS=0
PARALLEL="${LOCAL_LLM_PARALLEL:-2}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpu) GPU_LAYERS=99; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --alias) ALIAS="$2"; shift 2 ;;
    --ctx) CTX="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) MODEL="$1"; shift ;;
  esac
done

if [[ -z "$MODEL" ]]; then
  MODEL="$(ls -1 "$OUTPUT_DIR"/model_*_gguf/*Q4_K_M*.gguf 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$MODEL" || ! -f "$MODEL" ]]; then
  echo "No GGUF found. Pass a path, or run scripts/finetune.py --export gguf first (expected under $OUTPUT_DIR/model_<name>_gguf/)." >&2
  exit 1
fi
if ! command -v llama-server >/dev/null 2>&1; then
  echo "llama-server is not on PATH. Install a llama.cpp release or: pip install 'llama-cpp-python[server]'" >&2
  exit 1
fi

echo "Serving $MODEL as '$ALIAS' on http://0.0.0.0:$PORT/v1 (ctx $CTX, gpu layers $GPU_LAYERS, parallel $PARALLEL)"
echo "Smoke test in another shell: python scripts/smoke_endpoint.py --base-url http://localhost:$PORT/v1 --model $ALIAS"
exec llama-server \
  -m "$MODEL" \
  --host 0.0.0.0 --port "$PORT" \
  --alias "$ALIAS" \
  -c "$CTX" -np "$PARALLEL" \
  -ngl "$GPU_LAYERS" \
  --jinja \
  --cache-reuse 256
