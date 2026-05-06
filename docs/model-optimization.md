# Model Optimization Guide

This guide explains how to optimize code LLMs for NVIDIA GPUs using TensorRT-LLM.

## Supported Models

| Model | Size | Use Case | Optimization Level |
|-------|------|----------|-------------------|
| CodeLlama | 7B/13B/34B | General code completion | High |
| StarCoder2 | 3B/7B/15B | Multi-language code gen | High |
| SecCoder | 7B | Security analysis | Medium |
| GraphCodeBERT | 125M | Code structure analysis | High |

## Prerequisites

- NVIDIA GPU (A100/H100 recommended)
- CUDA 12.x
- TensorRT-LLM 0.6+
- Python 3.10+

## Step 1: Download Model

```bash
# From Hugging Face
git lfs install
git clone https://huggingface.co/codellama/CodeLlama-7B-Python-hf

# Or from NGC Registry
docker pull nvcr.io/nvidia/nemo/codegen-starcoder:latest
```

## Step 2: Convert to TensorRT-LLM

Use the provided script:

```bash
cd scripts
./convert_model.sh CodeLlama-7B-Python-hf trt_engine fp16 4096 2048
```

### Parameters Explained

- `MODEL_NAME`: Path to the model directory
- `OUTPUT_DIR`: Where to save the optimized engine
- `DTYPE`: Data type (fp16, bf16, or fp8)
- `MAX_INPUT_LEN`: Maximum input sequence length
- `MAX_OUTPUT_LEN`: Maximum output sequence length

## Step 3: Configure Triton Server

Copy your engine to the models directory:

```bash
mkdir -p models/codellama_engine/1
cp -r trt_engine/* models/codellama_engine/1/
cp configs/triton-config.pbtxt models/codellama_engine/config.pbtxt
```

## Step 4: Benchmark Performance

Expected performance on A100 GPU:

| Model | Precision | Tokens/sec | Latency (1KB prompt) |
|-------|-----------|------------|---------------------|
| CodeLlama-7B | FP16 | 2,000 | <50ms |
| CodeLlama-13B | FP16 | 1,200 | <80ms |
| CodeLlama-34B | FP16 | 600 | <150ms |
| CodeLlama-7B | FP8 | 3,500 | <30ms |

## Optimization Tips

### 1. Use In-Flight Batching

Enable dynamic batching in Triton config:

```pbtxt
dynamic_batching {
  preferred_batch_size: [1, 2, 4, 8, 16, 32]
  max_queue_delay_microseconds: 10000
}
```

### 2. Optimize KV Cache

For long contexts, increase paged KV cache:

```pbtxt
parameters {
  key: "max_tokens_in_paged_kv_cache"
  value: { string_value: "8192" }
}
```

### 3. Multi-GPU Deployment

For models > 34B, use tensor parallelism:

```bash
trtllm-build --model_dir CodeLlama-70B \
             --tensor_parallelism 4 \
             --pipeline_parallelism 2
```

### 4. Use FP8 for H100 GPUs

H100 supports FP8 natively for 2x throughput:

```bash
./convert_model.sh CodeLlama-7B trt_engine_fp8 fp8 4096 2048
```

## Troubleshooting

### Out of Memory

- Reduce `max_input_len` and `max_output_len`
- Use lower precision (FP8 > BF16 > FP16)
- Enable paged attention

### Slow First Token

- Increase `max_queue_delay_microseconds`
- Use CUDA graphs
- Pre-allocate GPU memory

### Model Loading Fails

- Check TensorRT-LLM version compatibility
- Verify CUDA version matches
- Ensure sufficient GPU memory

## Next Steps

- [Triton Server Setup](triton-setup.md)
- [VS Code Plugin Development](vscode-plugin.md)
- [Security & Compliance](security.md)
