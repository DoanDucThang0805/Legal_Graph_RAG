"""
Entity & Relation Extractor (Phase 3)
=====================================

Trích xuất Node (Thực thể) và Edge (Quan hệ) từ chunks để chuẩn bị đổ vào
Graph Database (Neo4j).

Chiến lược Lai 3 Lớp:
  - Lớp 1 (Rule-based / Regex): bắt VBPL, Điều, Khung hình phạt từ text.
  - Lớp 2 (LLM / Qwen3-14B self-host qua vLLM): trích quan hệ phức tạp (SUA_DOI,
    HUONG_DAN...) qua guided JSON. Bật bằng ``use_llm=True``. Xem ``llm_extractor.py``.
  - Lớp 3 (Metadata / source_links): mỗi Điều Pháp điển có ``source_links_json``
    trỏ tới VBPL gốc (vbpl.vn) → tạo quan hệ ``Article -THUOC-> VBPL`` chính xác.

Nodes schema: {id, label (CHUNK|ARTICLE|AN_LE|ENTITY), properties (JSON str)}
Edges schema: {source_id, target_id, type, properties (JSON str)}

Output: knowlegde_data/graph/nodes.parquet & edges.parquet
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

# --- LỚP 1: REGEX PATTERNS ---
# Chỉ bắt VBPL có SỐ HIỆU rõ ràng (VD: "Luật số 32/2004/QH11",
# "Nghị định 43/2014/NĐ-CP"). Tránh pattern lỏng vớ phải "Luật này", "luật của".
# VBPL có tên (vd "Bộ luật Hình sự 2015") để Lớp 3 (source_links) + Lớp 2 (LLM) phủ.
VBPL_PATTERN = re.compile(
    r'(?:Bộ luật|Luật|Nghị định|Nghị quyết|Pháp lệnh|Thông tư liên tịch|Thông tư|Quyết định)'
    r'\s+(?:số\s+)?\d+[\w.\-]*/[\w.\-/]+',
    re.IGNORECASE,
)
DIEU_PATTERN = re.compile(r'(?:khoản\s+\d+[a-z]?\s+)?Điều\s+\d+[a-z]?', re.IGNORECASE)
PHAT_PATTERN = re.compile(
    r'(?:phạt\s+)?(?:tù|cải tạo không giam giữ|cảnh cáo|phạt tiền)[\s\w]+(?:năm|tháng|triệu|tỷ)',
    re.IGNORECASE,
)

# --- LỚP 3: SOURCE_LINKS PARSING ---
# Tên VBPL trong text link, VD: "Luật số 32/2004/QH11", "Nghị định số 16/2006/NĐ-CP"
VBPL_NAME_RE = re.compile(
    r'(Bộ luật|Luật|Pháp lệnh|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư|Quyết định)\s+(?:số\s+)?([\w/.\-]+)',
    re.IGNORECASE,
)
# ItemID trong href → id ổn định của VBPL trên vbpl.vn
ITEMID_RE = re.compile(r'ItemID=(\d+)')


class EntityExtractor:
    def __init__(
        self,
        phapdien_path: Optional[Union[str, Path]] = None,
        anle_path: Optional[Union[str, Path]] = None,
        phapdien_unified_path: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        sample_size: Optional[int] = None,
        use_llm: bool = False,
        llm_model: str = "qwen3-14b",
        llm_sample_size: Optional[int] = None,
        llm_concurrency: int = 8,
        llm_only_with_signal: bool = True,
    ):
        base_dir = Path(__file__).resolve().parents[2] / "knowlegde_data"
        self.phapdien_path = Path(phapdien_path) if phapdien_path else base_dir / "phapdien/phapdien_chunks.parquet"
        self.anle_path = Path(anle_path) if anle_path else base_dir / "anle/anle_chunks.parquet"
        self.phapdien_unified_path = (
            Path(phapdien_unified_path)
            if phapdien_unified_path
            else base_dir / "phapdien/phapdien_unified.parquet"
        )
        self.output_dir = Path(output_dir) if output_dir else base_dir / "graph"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.sample_size = sample_size

        # Cấu hình Lớp 2 (LLM)
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.llm_sample_size = llm_sample_size
        self.llm_concurrency = llm_concurrency
        self.llm_only_with_signal = llm_only_with_signal

        # In-memory graph builder
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Graph primitives
    # ------------------------------------------------------------------

    def add_node(self, node_id: str, label: str, properties: dict[str, Any] | None = None) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = {"id": node_id, "label": label, "properties": properties or {}}

    def add_edge(self, source_id: str, target_id: str, rel_type: str, properties: dict[str, Any] | None = None) -> None:
        self.edges.append(
            {"source_id": source_id, "target_id": target_id, "type": rel_type, "properties": properties or {}}
        )

    @staticmethod
    def _ent_id(name: str, entity_type: str) -> str:
        """ID chuẩn hoá cho ENTITY node (dedup theo type + tên lowercase)."""
        return f"ENT::{entity_type}::{name.strip().lower()}"

    # ------------------------------------------------------------------
    # Lớp 1: Regex
    # ------------------------------------------------------------------

    def extract_entities_regex(self, text: str) -> list[tuple[str, str]]:
        """Dùng Regex (Rule-based) tìm các thực thể cơ bản."""
        entities: list[tuple[str, str]] = []
        if not text:
            return entities
        # strip dấu câu cuối để "NĐ-CP." và "NĐ-CP" không tách thành 2 entity
        clean = lambda s: s.strip().rstrip(" .,;:")
        for match in VBPL_PATTERN.finditer(text):
            entities.append((clean(match.group(0)), "VBPL"))
        for match in DIEU_PATTERN.finditer(text):
            entities.append((clean(match.group(0)), "DIEU"))
        for match in PHAT_PATTERN.finditer(text):
            entities.append((clean(match.group(0)), "KHUNG_HINH_PHAT"))
        return list(set(entities))

    def _add_regex_entities(self, chunk_id: str, text: str) -> None:
        for ent_name, ent_type in self.extract_entities_regex(text):
            ent_id = self._ent_id(ent_name, ent_type)
            self.add_node(ent_id, "ENTITY", {"name": ent_name, "entity_type": ent_type, "source": "regex"})
            self.add_edge(chunk_id, ent_id, "MENTIONS")

    # ------------------------------------------------------------------
    # Pháp điển & Án lệ (metadata-based nodes)
    # ------------------------------------------------------------------

    def process_phapdien(self) -> None:
        logger.info("Processing Phapdien chunks...")
        if not self.phapdien_path.exists():
            logger.warning(f"File not found: {self.phapdien_path}")
            return

        df = pd.read_parquet(self.phapdien_path)
        if self.sample_size:
            df = df.head(self.sample_size)

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Phapdien Graph"):
            chunk_id = str(row["chunk_id"])
            doc_id = str(row.get("doc_id", ""))

            self.add_node(chunk_id, "CHUNK", {
                "text": row.get("chunk_text", ""),
                "embed_text": row.get("embed_text", ""),
                "chunk_type": row.get("chunk_type", ""),
                "source": "phapdien",
            })

            # ARTICLE node keyed bằng doc_id (1:1 với Điều, unique — xem audit).
            if doc_id:
                self.add_node(doc_id, "ARTICLE", {
                    "article_id": str(row.get("article_id", "")),
                    "title": row.get("article_title", ""),
                    "chapter": row.get("chapter_title", ""),
                    "topic": row.get("topic_title_vi", ""),
                    "subject": row.get("subject_title_vi", ""),
                })
                self.add_edge(chunk_id, doc_id, "BELONGS_TO")

            self._add_regex_entities(chunk_id, row.get("chunk_text", ""))

    def process_anle(self) -> None:
        logger.info("Processing Anle chunks...")
        if not self.anle_path.exists():
            logger.warning(f"File not found: {self.anle_path}")
            return

        df = pd.read_parquet(self.anle_path)
        if self.sample_size:
            df = df.head(self.sample_size)

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Anle Graph"):
            chunk_id = str(row["chunk_id"])
            doc_id = str(row.get("doc_id", ""))

            self.add_node(chunk_id, "CHUNK", {
                "text": row.get("chunk_text", ""),
                "embed_text": row.get("embed_text", ""),
                "chunk_type": row.get("chunk_type", ""),
                "source": "anle",
            })

            if doc_id:
                self.add_node(doc_id, "AN_LE", {
                    "title": row.get("title", ""),
                    "case_type": row.get("case_type", ""),
                    "year": int(row.get("year", 0) if pd.notna(row.get("year")) else 0),
                })
                self.add_edge(chunk_id, doc_id, "BELONGS_TO")

                # AnLe áp dụng Điều luật (metadata). LƯU Ý: applied_article_code
                # gần như rỗng nên node DIEU chỉ là "Điều N" trần (mơ hồ) — chưa
                # resolve được sang Article cụ thể. Xem cảnh báo Phase 4 trong doc.
                applied_num = str(row.get("applied_article_number", ""))
                if applied_num and applied_num not in ("0", "nan", ""):
                    art_name = f"Điều {applied_num}"
                    ent_id = self._ent_id(art_name, "DIEU")
                    self.add_node(ent_id, "ENTITY", {"name": art_name, "entity_type": "DIEU", "source": "metadata"})
                    self.add_edge(doc_id, ent_id, "APPLIES_ARTICLE")

            self._add_regex_entities(chunk_id, row.get("chunk_text", ""))

    # ------------------------------------------------------------------
    # Lớp 3: source_links → VBPL + THUOC
    # ------------------------------------------------------------------

    def process_source_links(self) -> None:
        """Trích VBPL gốc từ ``source_links_json`` của mỗi Điều (phủ ~100%)."""
        logger.info("Processing source_links (Lớp 3)...")
        if not self.phapdien_unified_path.exists():
            logger.warning(f"Unified file not found: {self.phapdien_unified_path}")
            return

        df = pd.read_parquet(self.phapdien_unified_path)
        if self.sample_size:
            df = df.head(self.sample_size)

        added = 0
        for _, row in tqdm(df.iterrows(), total=len(df), desc="SourceLinks"):
            doc_id = str(row.get("doc_id", ""))
            raw = row.get("source_links_json", "")
            if not doc_id or not raw or str(raw) in ("nan", "[]", "{}", ""):
                continue
            try:
                links = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(links, list):
                continue

            for link in links:
                text = str(link.get("text", "") if isinstance(link, dict) else "")
                href = str(link.get("href", "") if isinstance(link, dict) else "")
                item = ITEMID_RE.search(href)
                name_m = VBPL_NAME_RE.search(text)
                if not item or not name_m:
                    continue
                vbpl_id = f"VBPL::{item.group(1)}"
                vbpl_name = f"{name_m.group(1)} số {name_m.group(2)}".strip()
                self.add_node(vbpl_id, "ENTITY", {
                    "name": vbpl_name, "entity_type": "VBPL", "source": "source_links", "url": href,
                })
                # Article (doc_id) THUOC VBPL gốc
                self.add_edge(doc_id, vbpl_id, "THUOC", {"via": "source_links"})
                added += 1

        logger.info("source_links: thêm %d quan hệ THUOC.", added)

    # ------------------------------------------------------------------
    # Lớp 2: LLM
    # ------------------------------------------------------------------

    def _apply_llm_results(self, results: dict[str, dict[str, Any]]) -> None:
        """Gắn entity/relation do LLM trích vào graph."""
        for chunk_id, res in results.items():
            name2id: dict[str, str] = {}
            for ent in res.get("entities", []):
                name, etype = ent.get("name", ""), ent.get("type", "")
                if not name or not etype:
                    continue
                ent_id = self._ent_id(name, etype)
                self.add_node(ent_id, "ENTITY", {"name": name, "entity_type": etype, "source": "llm"})
                self.add_edge(chunk_id, ent_id, "MENTIONS")
                name2id[name.strip().lower()] = ent_id

            for rel in res.get("relations", []):
                s = name2id.get(str(rel.get("source", "")).strip().lower())
                t = name2id.get(str(rel.get("target", "")).strip().lower())
                rtype = rel.get("type", "")
                if s and t and rtype:
                    self.add_edge(s, t, rtype, {"source": "llm", "from_chunk": chunk_id})

    def _run_llm_layer(self) -> None:
        logger.info("Running LLM layer (Lớp 2) model=%s ...", self.llm_model)
        from .llm_extractor import LLMExtractor

        extractor = LLMExtractor(
            model=self.llm_model,
            concurrency=self.llm_concurrency,
            checkpoint_path=self.output_dir / "llm_extract_checkpoint.jsonl",
        )
        for path, name in [(self.phapdien_path, "phapdien"), (self.anle_path, "anle")]:
            if not path.exists():
                continue
            df = pd.read_parquet(path)
            if self.sample_size:
                df = df.head(self.sample_size)
            results = extractor.run(
                df,
                sample_size=self.llm_sample_size,
                only_with_signal=self.llm_only_with_signal,
            )
            self._apply_llm_results(results)
            logger.info("LLM layer áp dụng xong cho %s (%d chunk).", name, len(results))

    # ------------------------------------------------------------------
    # Save / Run
    # ------------------------------------------------------------------

    def save(self) -> None:
        logger.info("Saving %d nodes and %d edges...", len(self.nodes), len(self.edges))

        nodes_list = []
        for n in self.nodes.values():
            nodes_list.append({
                "id": n["id"],
                "label": n["label"],
                "properties": json.dumps(n["properties"], ensure_ascii=False),
            })

        nodes_df = pd.DataFrame(nodes_list)
        edges_df = pd.DataFrame(self.edges)
        if not edges_df.empty:
            edges_df["properties"] = edges_df["properties"].apply(
                lambda x: json.dumps(x, ensure_ascii=False)
            )

        nodes_df.to_parquet(self.output_dir / "nodes.parquet", index=False)
        edges_df.to_parquet(self.output_dir / "edges.parquet", index=False)

        # Thống kê nhanh theo label / loại edge
        if not nodes_df.empty:
            logger.info("Node labels: %s", nodes_df["label"].value_counts().to_dict())
        if not edges_df.empty:
            logger.info("Edge types: %s", edges_df["type"].value_counts().to_dict())
        logger.info("✅ Saved to %s", self.output_dir)

    def run(self) -> None:
        self.process_phapdien()
        self.process_anle()
        self.process_source_links()
        if self.use_llm:
            self._run_llm_layer()
        self.save()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # FULL corpus + cả 3 lớp:
    #   Lớp 1 (regex) + Lớp 3 (source_links): vài phút.
    #   Lớp 2 (LLM/vLLM): job dài, có checkpoint → dừng/chạy lại an toàn.
    # Yêu cầu: vLLM đang chạy (make vllm-health). Resume: chạy lại file này.
    extractor = EntityExtractor(use_llm=True, llm_concurrency=32)
    extractor.run()
