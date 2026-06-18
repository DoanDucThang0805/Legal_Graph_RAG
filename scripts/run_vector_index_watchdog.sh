#!/usr/bin/env bash
set -euo pipefail

# Host-side helper for GX10. It keeps a persistent NVIDIA PyTorch container
# available and starts vector indexing inside a tmux session if not already
# running. Run this script from the repository root on the host.

CONTAINER_NAME="${CONTAINER_NAME:-legal-rag-gpu}"
IMAGE_NAME="${IMAGE_NAME:-nvcr.io/nvidia/pytorch:25.10-py3}"
REPO_DIR="${REPO_DIR:-$(pwd)}"
WORKDIR="/workspace/Legal_Graph_RAG"
TMUX_SESSION="${TMUX_SESSION:-vector-index}"
BATCH_SIZE="${BATCH_SIZE:-2048}"
MAX_LENGTH="${MAX_LENGTH:-512}"

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

ensure_container() {
  if container_running; then
    echo "Container is already running: $CONTAINER_NAME"
    return
  fi

  if container_exists; then
    echo "Starting existing container: $CONTAINER_NAME"
    docker start "$CONTAINER_NAME" >/dev/null
    return
  fi

  echo "Creating container: $CONTAINER_NAME"
  docker run -dit \
    --name "$CONTAINER_NAME" \
    --gpus all \
    --network host \
    -v "$REPO_DIR:$WORKDIR" \
    -w "$WORKDIR" \
    "$IMAGE_NAME" \
    bash >/dev/null
}

exec_in_container() {
  docker exec "$CONTAINER_NAME" bash -lc "$1"
}

ensure_container_dependencies() {
  echo "Ensuring tmux is installed..."
  exec_in_container "command -v tmux >/dev/null || (apt-get update && apt-get install -y tmux)"

  echo "Ensuring Python dependencies are installed..."
  exec_in_container "python - <<'PY' >/dev/null 2>&1
import polars
import qdrant_client
import transformers
import yaml
PY
  if [ \$? -ne 0 ]; then
    pip install \
      'transformers==4.51.3' \
      'huggingface-hub>=0.30,<1.0' \
      'fsspec[http]>=2023.1.0,<=2024.9.0' \
      'qdrant-client>=1.12,<2.0' \
      'polars>=1.18,<2.0' \
      pyarrow \
      tqdm \
      pyyaml
  fi
  pip uninstall -y apex >/dev/null 2>&1 || true"
}

tmux_session_exists() {
  docker exec "$CONTAINER_NAME" tmux has-session -t "$TMUX_SESSION" >/dev/null 2>&1
}

start_vector_index_session() {
  if tmux_session_exists; then
    echo "tmux session already exists: $TMUX_SESSION"
    echo "Attach with: docker exec -it $CONTAINER_NAME tmux attach -t $TMUX_SESSION"
    return
  fi

  echo "Starting vector indexing in tmux session: $TMUX_SESSION"
  docker exec "$CONTAINER_NAME" tmux new-session -d -s "$TMUX_SESSION" "cd '$WORKDIR' && python - <<'PY'
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
from backend.indexing.build_vector_index import build_all_vector_indexes

embedder = VNLegalLALEmbedder(
    device='cuda',
    batch_size=$BATCH_SIZE,
    max_length=$MAX_LENGTH,
)
build_all_vector_indexes(recreate=False, resume=True, embedder=embedder)
print('vector indexes resumed')
PY
read -p 'Vector indexing command finished. Press Enter to close tmux pane...'"

  echo "Attach with: docker exec -it $CONTAINER_NAME tmux attach -t $TMUX_SESSION"
}

main() {
  if [ ! -d "$REPO_DIR/.git" ]; then
    echo "ERROR: run this script from the repository root or set REPO_DIR." >&2
    exit 1
  fi

  ensure_container
  ensure_container_dependencies
  start_vector_index_session
}

main "$@"
