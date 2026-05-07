#!/usr/bin/env bash
set -euo pipefail

IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.17.0}"
MODEL="${VLLM_MODEL:-datalab-to/chandra-ocr-2}"
SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-chandra}"
PORT="${VLLM_PORT:-8000}"
HOST_PORT="${VLLM_HOST_PORT:-8000}"
GPU_DEVICE="${VLLM_GPU_DEVICE:-0}"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-18000}"
HF_CACHE_DIR="${VLLM_HF_CACHE_DIR:-$HOME/.cache/huggingface}"

GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | sed -n '1p' || true)"
PROFILE="generic"
default_dtype="half"
default_max_num_seqs="32"
default_max_num_batched_tokens="4096"
default_gpu_memory_utilization="0.85"

if echo "$GPU_NAME" | grep -qi "H100"; then
  PROFILE="h100"
  default_dtype="bfloat16"
  default_max_num_seqs="96"
  default_max_num_batched_tokens="8192"
  default_gpu_memory_utilization="0.85"
elif echo "$GPU_NAME" | grep -qi "V100"; then
  PROFILE="v100"
  default_dtype="half"
  default_max_num_seqs="32"
  default_max_num_batched_tokens="4096"
  default_gpu_memory_utilization="0.85"
fi

DTYPE="${VLLM_DTYPE:-$default_dtype}"
MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-$default_max_num_seqs}"
MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-$default_max_num_batched_tokens}"
GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-$default_gpu_memory_utilization}"

echo "Starting vLLM:"
echo "  gpu_name=${GPU_NAME:-unknown}"
echo "  profile=$PROFILE"
echo "  image=$IMAGE"
echo "  model=$MODEL"
echo "  served_model_name=$SERVED_MODEL_NAME"
echo "  dtype=$DTYPE"
echo "  max_num_seqs=$MAX_NUM_SEQS"
echo "  max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
echo "  gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
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
