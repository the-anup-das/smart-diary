#!/usr/bin/env bash
# Serve the merged fp16 export with vLLM (NVIDIA GPU), OpenAI-compatible, with guided JSON decoding.
#
#   ./scripts/serve_vllm.sh                       # output/model_qwen_merged
#   ./scripts/serve_vllm.sh path/to/merged --port 8080 --alias smart-diary-slm
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:-$HERE/../output/model_qwen_merged}"
PORT="${LOCAL_LLM_PORT:-8080}"
ALIAS="${LOCAL_LLM_MODEL:-smart-diary-slm}"
CTX="${LOCAL_LLM_CTX:-8192}"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --alias) ALIAS="$2"; shift 2 ;;
    --ctx) CTX="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [[ ! -d "$MODEL" ]]; then
  echo "No merged model directory at $MODEL. Run scripts/finetune.py --export merged first." >&2
  exit 1
fi
echo "Serving $MODEL as '$ALIAS' on http://0.0.0.0:$PORT/v1"
exec python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" --served-model-name "$ALIAS" \
  --host 0.0.0.0 --port "$PORT" \
  --max-model-len "$CTX" \
  --guided-decoding-backend xgrammar
