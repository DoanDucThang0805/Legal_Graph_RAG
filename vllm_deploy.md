# vLLM — Qwen3-14B Serving (Docker)

Đóng gói self-host **Qwen/Qwen3-14B** bằng vLLM (OpenAI-compatible API) cho Lớp 2
trích xuất entity/quan hệ (Phase 3). Bật/tắt độc lập với Neo4j qua profile `llm`.

## Bật / Tắt nhanh

```bash
make vllm-up        # bật  (docker compose --profile llm up -d vllm)
make vllm-health    # kiểm tra API sẵn sàng chưa
make vllm-logs      # xem log (lần đầu: tải + load model)
make vllm-down      # tắt
```

Không dùng make thì:
```bash
docker compose --profile llm up -d vllm
docker compose --profile llm down vllm
```

> Profile `llm` nghĩa là `docker compose up` thường (cho Neo4j) **không** tự bật vLLM.
> Chỉ bật khi thêm `--profile llm`.

## Cấu hình (`.env` ở repo root)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `VLLM_IMAGE` | `vllm/vllm-openai:latest` | Image vLLM (**xem cảnh báo GB10 bên dưới**) |
| `VLLM_MODEL` | `Qwen/Qwen3-14B` | Model HF |
| `VLLM_SERVED_NAME` | `qwen3-14b` | Tên model gọi qua API |
| `VLLM_PORT` | `8000` | Cổng host |
| `VLLM_MAX_MODEL_LEN` | `8192` | Context tối đa (đủ cho extraction) |
| `VLLM_GPU_UTIL` | `0.65` | Tỷ lệ VRAM cấp cho vLLM |
| `HF_CACHE_DIR` | `/home/minhht/.cache/huggingface` | HF cache host (mount để khỏi tải lại) |
| `HF_TOKEN` | (trống) | Token HF nếu model gated (Qwen3 public, có thể để trống) |

## ⚠️ QUAN TRỌNG — máy GB10 (Grace Blackwell, aarch64, sm_120)

Image `vllm/vllm-openai:latest` chủ yếu build cho **x86_64**; trên **ARM64 + Blackwell**
nó có thể không có manifest hoặc thiếu kernel `sm_120`/NVFP4. Nếu `make vllm-up` báo lỗi
manifest hoặc CUDA arch, hãy đổi `VLLM_IMAGE` sang image **ARM64 + Blackwell** do NVIDIA
cung cấp cho DGX Spark (NGC), rồi chạy lại:

```bash
# ví dụ — thay bằng tag NVIDIA xác nhận cho DGX Spark / GB10:
VLLM_IMAGE=nvcr.io/nvidia/<vllm-arm64-blackwell-tag>
```

Kiểm tra image có chạy ARM64 không trước khi pull:
```bash
docker manifest inspect <image> | grep -i arm64
```

## Tối ưu cho GB10 (sau khi chạy được)

- **Bandwidth-bound**: GB10 nhiều RAM (128GB) nhưng băng thông LPDDR5X thấp → để tăng
  tốc độ sinh token, dùng **NVFP4** (Blackwell native): trỏ `VLLM_MODEL` tới checkpoint
  NVFP4 hoặc thêm `--quantization modelopt` vào `command` trong `docker-compose.yml`.
- `--enable-prefix-caching` đã bật sẵn → tái dùng phần prompt cố định (instruction) giữa
  các lần gọi, tăng throughput khi trích xuất hàng loạt.
- Qwen3 mặc định bật "thinking" → khi tích hợp code sẽ tắt (`enable_thinking=false`) để
  guided-JSON không bị hỏng và chạy nhanh hơn.

## Kiểm thử nhanh sau khi READY

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen3-14b",
  "messages": [{"role":"user","content":"Xin chào, bạn là model gì?"}],
  "max_tokens": 64
}'
```
