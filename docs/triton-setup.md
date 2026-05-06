# Triton Inference Server Setup

Guide for deploying NVIDIA Triton Inference Server for code generation models.

## Architecture Overview

```
┌─────────────┐     ┌───────────────────┐     ┌──────────────┐
│   Clients   │────▶│  Triton Server    │◀────│  GPU Memory  │
│ (IDE/CLI)   │     │  (Model Serving)  │     │  (A100/H100) │
└─────────────┘     └───────────────────┘     └──────────────┘
```

## Directory Structure

```
models/
└── codellama_engine/
    ├── config.pbtxt
    └── 1/
        └── model.plan  (TensorRT engine)
```

## Installation

### Option 1: Docker (Recommended)

```bash
docker run --gpus all -it --rm \
  -p 8000:8000 \
  -p 8001:8001 \
  -p 8002:8002 \
  -v $(pwd)/models:/models \
  nvcr.io/nvidia/tritonserver:23.12-py3 \
  tritonserver --model-repository=/models
```

### Option 2: Native Installation

```bash
# Add NVIDIA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt-get update

# Install Triton Server
apt-get install -y tritonserver
```

## Configuration

### Basic config.pbtxt

```pbtxt
name: codellama_engine
platform: "tensorrt-llm"
max_batch_size: 128

input [
  { name: "input_ids", data_type: TYPE_INT32, dims: [-1] }
]

output [
  { name: "output_ids", data_type: TYPE_INT32, dims: [-1] }
]

instance_group [{ kind: KIND_GPU }]

dynamic_batching {
  preferred_batch_size: [1, 2, 4, 8, 16, 32, 64, 128]
  max_queue_delay_microseconds: 10000
}
```

### Advanced Configuration (Multi-GPU)

```pbtxt
name: codellama_70b
platform: "tensorrt-llm"
max_batch_size: 64

instance_group [
  {
    kind: KIND_GPU
    gpus: [0, 1, 2, 3]
    count: 1
  }
]

parameters {
  key: "tensor_parallelism"
  value: { string_value: "4" }
}
```

## Running Triton Server

### Start Server

```bash
tritonserver \
  --model-repository=/path/to/models \
  --http-port=8000 \
  --grpc-port=8001 \
  --metrics-port=8002 \
  --log-verbose=1
```

### Verify Models Loaded

```bash
curl localhost:8000/v2/repository/index
```

Expected output:
```json
[
  {
    "name": "codellama_engine",
    "version": "1",
    "state": "READY"
  }
]
```

## Making Inference Requests

### HTTP API

```bash
curl -X POST http://localhost:8000/v2/models/codellama_engine/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text_input": "def fibonacci(n):",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

### gRPC Client (Python)

```python
import tritonclient.grpc as grpcclient

client = grpcclient.InferenceServerClient("localhost:8001")

inputs = grpcclient.InferInput(
    "input_ids", 
    [1, 50], 
    "INT32"
)

results = client.infer(
    model_name="codellama_engine",
    inputs=[inputs]
)

print(results.as_numpy("output_ids"))
```

## Performance Tuning

### 1. Enable CUDA Graphs

Reduces kernel launch overhead:

```pbtxt
parameters {
  key: "cuda_graph_mode"
  value: { string_value: "enabled" }
}
```

### 2. Optimize Batching

Adjust based on your workload:

```pbtxt
dynamic_batching {
  preferred_batch_size: [1, 2, 4, 8]
  max_queue_delay_microseconds: 50000  # 50ms
}
```

### 3. Memory Management

Pre-allocate GPU memory:

```pbtxt
parameters {
  key: "gpu_memory_fraction"
  value: { string_value: "0.9" }
}
```

## Monitoring

### Metrics Endpoint

```bash
curl localhost:8002/metrics
```

Key metrics:
- `nv_inference_request_duration_us`: Request latency
- `nv_inference_queue_duration_us`: Queue wait time
- `nv_gpu_memory_total_bytes`: GPU memory usage

### Prometheus Integration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'triton'
    static_configs:
      - targets: ['triton-server:8002']
```

## High Availability

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triton-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: triton
  template:
    spec:
      containers:
      - name: triton
        image: nvcr.io/nvidia/tritonserver:23.12-py3
        ports:
        - containerPort: 8000
        - containerPort: 8001
        resources:
          limits:
            nvidia.com/gpu: 1
```

### Load Balancing

Use NGINX or HAProxy to distribute requests across multiple Triton instances.

## Security

### Enable Authentication

```pbtxt
parameters {
  key: "auth_token"
  value: { string_value: "your-secret-token" }
}
```

### TLS/SSL

```bash
tritonserver \
  --ssl-https-cert-file=/path/to/cert.pem \
  --ssl-https-key-file=/path/to/key.pem
```

## Troubleshooting

### Model Not Loading

Check logs:
```bash
docker logs <container_id> | grep -i error
```

Common issues:
- Missing TensorRT engine
- Insufficient GPU memory
- Version mismatch

### Slow Inference

1. Check GPU utilization: `nvidia-smi`
2. Monitor batch sizes in metrics
3. Verify dynamic batching is enabled
4. Consider using FP8 precision

### Connection Refused

Ensure ports are exposed:
```bash
docker port <container_id>
```

## Next Steps

- [Model Optimization Guide](model-optimization.md)
- [VS Code Plugin Development](vscode-plugin.md)
- [Security & Compliance](security.md)
