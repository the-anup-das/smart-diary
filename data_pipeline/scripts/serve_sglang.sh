#!/bin/bash
# Script to launch the SGLang OpenAI-compatible server for Phase 3 Inference

# Default to Qwen if no model is specified
MODEL_KEY=${1:-"qwen"}
MODEL_PATH="../output/model_${MODEL_KEY}_q4_k_m/unsloth.Q4_K_M.gguf"

# Ensure the model exists
if [ ! -d "$MODEL_PATH" ] && [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Error: Model not found at $MODEL_PATH"
    echo "Did you run 'python scripts/finetune.py --model $MODEL_KEY' first?"
    exit 1
fi

echo "🚀 Starting SGLang Inference Engine on Port 30000"
echo "📦 Model: $MODEL_PATH"
echo "🧠 Features: RadixAttention enabled, Guided JSON decoding active"
echo "------------------------------------------------------------"

# Launch SGLang Server
# --model-path: Points to our exported GGUF or merged HF model
# --port: 30000 (OpenAI compatible endpoint will be at http://localhost:30000/v1)
# --chat-template: Uses the chatml template for Qwen, or corresponding templates for others

TEMPLATE="chatml"
if [ "$MODEL_KEY" == "phi" ]; then
    TEMPLATE="phi-3"
elif [ "$MODEL_KEY" == "llama" ]; then
    TEMPLATE="llama-3"
fi

python3 -m sglang.launch_server \
    --model-path "$MODEL_PATH" \
    --port 30000 \
    --chat-template "$TEMPLATE" \
    --host 0.0.0.0
