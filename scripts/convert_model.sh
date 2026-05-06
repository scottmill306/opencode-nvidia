#!/bin/bash
# Script to convert CodeLlama model to TensorRT-LLM format

set -e

MODEL_NAME=${1:-"CodeLlama-7B-Python-hf"}
OUTPUT_DIR=${2:-"trt_engine"}
DTYPE=${3:-"fp16"}
MAX_INPUT_LEN=${4:-4096}
MAX_OUTPUT_LEN=${5:-2048}

echo "🚀 Converting $MODEL_NAME to TensorRT-LLM format..."
echo "   Output directory: $OUTPUT_DIR"
echo "   Data type: $DTYPE"
echo "   Max input length: $MAX_INPUT_LEN"
echo "   Max output length: $MAX_OUTPUT_LEN"

# Build the TensorRT engine
trtllm-build --model_dir "$MODEL_NAME" \
             --dtype "$DTYPE" \
             --max_input_len "$MAX_INPUT_LEN" \
             --max_output_len "$MAX_OUTPUT_LEN" \
             --output_dir "$OUTPUT_DIR"

echo "✅ Model conversion complete!"
echo "   Engine saved to: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "1. Copy the engine to your Triton server"
echo "2. Update triton-config.pbtxt with the engine path"
echo "3. Start Triton Inference Server"
