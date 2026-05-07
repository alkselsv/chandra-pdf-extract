#!/usr/bin/env bash
set -euo pipefail

IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.17.0}"
MODEL="${VLLM_MODEL:-datalab-to/chandra-ocr-2}"
SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-chandra}"
PORT="${VLLM_PORT:-8000}"
HOST_PORT="${VLLM_HOST_PORT:-8000}"
GPU_DEVICE="${VLLM_GPU_DEVICE:-0}"
DTYPE="${VLLM_DTYPE:-half}"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-18000}"
MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-32}"
MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-4096}"
GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.85}"
HF_CACHE_DIR="${VLLM_HF_CACHE_DIR:-$HOME/.cache/huggingface}"

echo "Starting vLLM:"
echo "  image=$IMAGE"
echo "  model=$MODEL"
echo "  served_model_name=$SERVED_MODEL_NAME"
echo "  dtype=$DTYPE"
echo "  host_port=$HOST_PORT container_port=$PORT"
echo "  gpu_device=$GPU_DEVICE"

sudo docker run --rm \
  --runtime nvidia \
  --gpus "device=${GPU_DEVICE}" \
  -v "${HF_CACHE_DIR}:/root/.cache/huggingface" \
  -p "${HOST_PORT}:${PORT}" \
  --ipc=host \
  "${IMAGE}" \
  --model "${MODEL}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --max-num-seqs "${MAX_NUM_SEQS}" \
  --max_num_batched_tokens "${MAX_NUM_BATCHED_TOKENS}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --enable-prefix-caching \
  --mm-processor-kwargs '{"min_pixels":3136,"max_pixels":6291456}' \
  --served-model-name "${SERVED_MODEL_NAME}"
