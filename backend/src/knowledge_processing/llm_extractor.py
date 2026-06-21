"""
LLM Entity & Relation Extractor — Lớp 2 (Phase 3)
=================================================

Trích xuất thực thể + quan hệ pháp lý phức tạp bằng **Qwen3-14B self-host qua
vLLM** (OpenAI-compatible API) với **guided JSON decoding** → output luôn đúng
schema ``ExtractionResult`` (gần như 0% lỗi parse).

Tối ưu chi phí/thời gian (vì ~270k chunk):
  1. Pre-filter: chỉ gọi LLM cho chunk có "dấu hiệu quan hệ".
  2. Async + Semaphore: gọi song song có giới hạn concurrency.
  3. Checkpoint/Resume: ghi từng kết quả ra JSONL; chạy lại bỏ qua chunk đã xong.
  4. sample_size: validate trên tập nhỏ trước khi chạy full.

Yêu cầu: vLLM đang chạy (xem docker-compose service ``vllm`` / ``make vllm-up``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from openai import AsyncOpenAI
from tqdm import tqdm

from schema.extraction_schema import ExtractionResult

logger = logging.getLogger(__name__)

# Dấu hiệu cho thấy đoạn văn có khả năng chứa QUAN HỆ → đáng gọi LLM.
RELATION_TRIGGERS = re.compile(
    r"sửa đổi|bổ sung|thay thế|bãi bỏ|hết hiệu lực|hướng dẫn thi hành|"
    r"quy định chi tiết|theo quy định tại|căn cứ\s|dẫn chiếu|được quy định tại",
    re.IGNORECASE,
)

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "entity_extraction_prompt.txt"
)

# vLLM OpenAI-compatible endpoint (khớp docker-compose service "vllm").
DEFAULT_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
DEFAULT_MODEL = os.getenv("VLLM_SERVED_NAME", "qwen3-14b")


class LLMExtractor:
    """Trích xuất entity/quan hệ bằng Qwen3-14B (vLLM) + guided JSON."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "EMPTY",
        concurrency: int = 8,
        prompt_path: Optional[Union[str, Path]] = None,
        checkpoint_path: Optional[Union[str, Path]] = None,
        max_text_chars: int = 4000,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        enable_thinking: bool = False,
    ) -> None:
        self.model = model
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

        prompt_path = Path(prompt_path) if prompt_path else DEFAULT_PROMPT_PATH
        self.prompt_template = prompt_path.read_text(encoding="utf-8")

        self.concurrency = concurrency
        self.max_text_chars = max_text_chars
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

        # Guided decoding: ép Qwen3 trả đúng schema ExtractionResult.
        self._response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "ExtractionResult",
                "schema": ExtractionResult.model_json_schema(),
            },
        }

    # ------------------------------------------------------------------
    # Filtering / checkpoint
    # ------------------------------------------------------------------

    @staticmethod
    def has_relation_signal(text: str) -> bool:
        return bool(text) and bool(RELATION_TRIGGERS.search(text))

    def _load_checkpoint(self) -> dict[str, dict[str, Any]]:
        """Đọc checkpoint → dict[chunk_id] = {entities, relations} đã trích trước đó.

        Resume: vừa để BỎ QUA chunk đã xong (khỏi gọi LLM lại), vừa để GỘP các
        kết quả cũ vào output cuối (tránh thiếu khi chạy nhiều lần).
        """
        done: dict[str, dict[str, Any]] = {}
        if self.checkpoint_path and self.checkpoint_path.exists():
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        cid = obj["chunk_id"]
                    except (json.JSONDecodeError, KeyError):
                        continue
                    done[cid] = {
                        "entities": obj.get("entities", []),
                        "relations": obj.get("relations", []),
                    }
            logger.info("Resume: đã có %d chunk trong checkpoint.", len(done))
        return done

    # ------------------------------------------------------------------
    # Async extraction
    # ------------------------------------------------------------------

    async def _extract_one(
        self, chunk_id: str, text: str, sem: asyncio.Semaphore
    ) -> tuple[str, Optional[dict[str, Any]]]:
        async with sem:
            prompt = self.prompt_template.format(chunk_text=text[: self.max_text_chars])
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format=self._response_format,
                    extra_body={"chat_template_kwargs": {"enable_thinking": self.enable_thinking}},
                )
                content = resp.choices[0].message.content
                result = ExtractionResult.model_validate_json(content)
                return chunk_id, result.model_dump()
            except Exception as e:  # noqa: BLE001
                logger.warning("LLM fail chunk_id=%s: %s", chunk_id, str(e)[:160])
                return chunk_id, None

    async def _run_async(
        self, items: list[tuple[str, str]]
    ) -> dict[str, dict[str, Any]]:
        sem = asyncio.Semaphore(self.concurrency)
        results: dict[str, dict[str, Any]] = {}

        ckpt_file = (
            open(self.checkpoint_path, "a", encoding="utf-8")
            if self.checkpoint_path
            else None
        )

        tasks = [asyncio.create_task(self._extract_one(cid, txt, sem)) for cid, txt in items]
        try:
            for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="LLM extract"):
                chunk_id, result = await coro
                if result is None:
                    continue
                results[chunk_id] = result
                if ckpt_file:
                    ckpt_file.write(
                        json.dumps({"chunk_id": chunk_id, **result}, ensure_ascii=False) + "\n"
                    )
                    ckpt_file.flush()
        finally:
            if ckpt_file:
                ckpt_file.close()

        return results

    # ------------------------------------------------------------------
    # Public runner
    # ------------------------------------------------------------------

    def run(
        self,
        df: pd.DataFrame,
        text_col: str = "chunk_text",
        id_col: str = "chunk_id",
        sample_size: Optional[int] = None,
        only_with_signal: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Chạy trích xuất LLM trên DataFrame chunks.

        Returns: dict[chunk_id] = {"entities": [...], "relations": [...]}
        """
        work = df.head(sample_size) if sample_size else df

        done = self._load_checkpoint()  # {chunk_id: {entities, relations}} đã có
        items: list[tuple[str, str]] = []
        skipped_signal = 0
        for _, row in work.iterrows():
            cid = str(row[id_col])
            if cid in done:
                continue
            text = str(row.get(text_col, "") or "")
            if only_with_signal and not self.has_relation_signal(text):
                skipped_signal += 1
                continue
            items.append((cid, text))

        logger.info(
            "Tổng %d chunk | bỏ qua (đã xong) %d | bỏ qua (no-signal) %d | gọi LLM %d",
            len(work), len(done), skipped_signal, len(items),
        )

        new_results = asyncio.run(self._run_async(items)) if items else {}
        logger.info(
            "LLM mới: %d chunk | tổng (gồm checkpoint cũ): %d chunk.",
            len(new_results), len(done) + len(new_results),
        )
        # GỘP checkpoint cũ + kết quả mới → output đầy đủ dù chạy nhiều lần.
        return {**done, **new_results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Smoke test trên sample nhỏ (cần vLLM đang chạy).
    base = Path(__file__).resolve().parents[2] / "knowlegde_data"
    df = pd.read_parquet(base / "phapdien" / "phapdien_chunks.parquet")

    extractor = LLMExtractor(
        concurrency=8,
        checkpoint_path=base / "graph" / "llm_extract_checkpoint.jsonl",
    )
    out = extractor.run(df, sample_size=100, only_with_signal=True)
    print(f"\nExtracted {len(out)} chunks. Mẫu:")
    for cid, res in list(out.items())[:3]:
        print(f"\n{cid}")
        print("  entities:", res["entities"][:5])
        print("  relations:", res["relations"][:5])
