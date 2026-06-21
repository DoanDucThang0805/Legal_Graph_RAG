.PHONY: help vllm-up vllm-down vllm-restart vllm-logs vllm-status vllm-health neo4j-up neo4j-down

help:
	@echo "Các lệnh:"
	@echo "  make vllm-up       Bật vLLM (Qwen3-14B)"
	@echo "  make vllm-down     Tắt vLLM"
	@echo "  make vllm-restart  Khởi động lại vLLM"
	@echo "  make vllm-logs     Xem log vLLM (Ctrl-C để thoát)"
	@echo "  make vllm-status   Trạng thái container vLLM"
	@echo "  make vllm-health   Kiểm tra API đã sẵn sàng chưa"
	@echo "  make neo4j-up      Bật Neo4j"
	@echo "  make neo4j-down    Tắt Neo4j"

# ----- vLLM (profile llm) -----
vllm-up:
	docker compose --profile llm up vllm
	@echo "→ vLLM đang khởi động. Lần đầu cần tải + load model 14B (vài phút)."
	@echo "  Theo dõi: make vllm-logs   |   Kiểm tra: make vllm-health"

vllm-down:
	docker compose --profile llm down vllm

vllm-restart:
	docker compose --profile llm restart vllm

# ----- vLLM control (start/stop) -----

vllm-start:
	docker compose --profile llm start vllm
	@echo "→ vLLM container started (không reload model nếu đã load trước đó)"

vllm-stop:
	docker compose --profile llm stop vllm
	@echo "→ vLLM container stopped (giữ state, không xoá container)"
	
vllm-logs:
	docker compose --profile llm logs -f vllm

vllm-status:
	docker compose --profile llm ps vllm

vllm-health:
	@curl -fsS http://localhost:$${VLLM_PORT:-8000}/health \
		&& echo "✓ vLLM READY (http://localhost:$${VLLM_PORT:-8000}/v1)" \
		|| echo "✗ vLLM CHƯA sẵn sàng (đang load model hoặc chưa bật)."

# ----- Neo4j (mặc định) -----
neo4j-up:
	docker compose up -d neo4j

neo4j-down:
	docker compose down neo4j
