"""
Entity & Relation Extractor
===========================

Mục tiêu: Trích xuất Node (Thực thể) và Edge (Quan hệ) từ các chunks
để chuẩn bị đổ vào Graph Database (Neo4j / NetworkX).

Chiến lược Lai (Hybrid):
1. Metadata-based: Dựa vào metadata có sẵn trong dataset (chính xác 100%)
2. Rule-based: Dùng Regex để bắt các thực thể chuẩn (VBPL, Điều, Khung hình phạt)

Nodes schema:
- id: str
- label: str (CHUNK, ARTICLE, AN_LE, ENTITY)
- properties: str (JSON string)

Edges schema:
- source_id: str
- target_id: str
- type: str (BELONGS_TO, APPLIES_ARTICLE, CITES, MENTIONS)
- properties: str (JSON string)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

# --- REGEX PATTERNS LỚP 2 ---
# Bắt VBPL: "Luật số 15/2012/QH13", "Nghị định 15/2020/NĐ-CP", "Bộ luật Hình sự năm 2015"
VBPL_PATTERN = re.compile(
    r'(?:Bộ luật|Luật|Nghị định|Thông tư|Quyết định|Pháp lệnh)(?:\s+số)?\s+[\w/-]+(?:\s+năm\s+\d{4})?|Bộ luật\s+[A-Z][\w\s]+(?:năm\s+\d{4})?',
    re.IGNORECASE
)

# Bắt Điều luật: "Điều 173", "khoản 2 Điều 15"
DIEU_PATTERN = re.compile(r'(?:khoản\s+\d+[a-z]?\s+)?Điều\s+\d+[a-z]?', re.IGNORECASE)

# Bắt Khung hình phạt (Cơ bản)
PHAT_PATTERN = re.compile(r'(?:phạt\s+)?(?:tù|cải tạo không giam giữ|cảnh cáo|phạt tiền)[\s\w]+(?:năm|tháng|triệu|tỷ)', re.IGNORECASE)


class EntityExtractor:
    def __init__(
        self,
        phapdien_path: str | Path | None = None,
        anle_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        sample_size: int | None = None,
    ):
        base_dir = Path(__file__).resolve().parents[2] / "knowlegde_data"
        self.phapdien_path = Path(phapdien_path) if phapdien_path else base_dir / "phapdien/phapdien_chunks.parquet"
        self.anle_path = Path(anle_path) if anle_path else base_dir / "anle/anle_chunks.parquet"
        self.output_dir = Path(output_dir) if output_dir else base_dir / "graph"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.sample_size = sample_size

        # In-memory graph builder
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    def add_node(self, node_id: str, label: str, properties: dict[str, Any] | None = None) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "label": label,
                "properties": properties or {}
            }

    def add_edge(self, source_id: str, target_id: str, rel_type: str, properties: dict[str, Any] | None = None) -> None:
        self.edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "type": rel_type,
            "properties": properties or {}
        })

    def extract_entities_regex(self, text: str) -> list[tuple[str, str]]:
        """Dùng Regex (Rule-based) để tìm các thực thể cơ bản."""
        entities = []
        if not text:
            return entities
            
        # VBPL
        for match in VBPL_PATTERN.finditer(text):
            entities.append((match.group(0).strip(), "VBPL"))
            
        # DIEU
        for match in DIEU_PATTERN.finditer(text):
            entities.append((match.group(0).strip(), "DIEU"))
            
        # KHUNG HINH PHAT
        for match in PHAT_PATTERN.finditer(text):
            entities.append((match.group(0).strip(), "KHUNG_HINH_PHAT"))
            
        # Có thể thêm thuật toán khử trùng lặp (dedup) ở đây
        return list(set(entities))

    def process_phapdien(self) -> None:
        logger.info("Processing Phapdien chunks...")
        if not self.phapdien_path.exists():
            logger.warning(f"File not found: {self.phapdien_path}")
            return
            
        df = pd.read_parquet(self.phapdien_path)
        if self.sample_size:
            df = df.head(self.sample_size)
            
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Phapdien Graph"):
            chunk_id = str(row['chunk_id'])
            doc_id = str(row.get('doc_id', ''))
            article_id = str(row.get('article_id', ''))
            
            # 1. Thêm Node Chunk
            self.add_node(chunk_id, "CHUNK", {
                "text": row.get('chunk_text', ''),
                "embed_text": row.get('embed_text', ''),
                "chunk_type": row.get('chunk_type', ''),
                "source": "phapdien"
            })
            
            # 2. Thêm Node Article & Relation
            if article_id:
                self.add_node(article_id, "ARTICLE", {
                    "doc_id": doc_id,
                    "title": row.get('article_title', ''),
                    "chapter": row.get('chapter_title', ''),
                    "topic": row.get('topic_title_vi', ''),
                    "subject": row.get('subject_title_vi', '')
                })
                # Edge: Chunk -> BELONGS_TO -> Article
                self.add_edge(chunk_id, article_id, "BELONGS_TO")
            
            # 3. Trích xuất Thực thể bằng Regex
            text = row.get('chunk_text', '')
            extracted = self.extract_entities_regex(text)
            for ent_name, ent_type in extracted:
                ent_id = f"ENT::{ent_type}::{ent_name.lower()}"
                self.add_node(ent_id, "ENTITY", {"name": ent_name, "entity_type": ent_type})
                self.add_edge(chunk_id, ent_id, "MENTIONS")

    def process_anle(self) -> None:
        logger.info("Processing Anle chunks...")
        if not self.anle_path.exists():
            logger.warning(f"File not found: {self.anle_path}")
            return
            
        df = pd.read_parquet(self.anle_path)
        if self.sample_size:
            df = df.head(self.sample_size)
            
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Anle Graph"):
            chunk_id = str(row['chunk_id'])
            doc_id = str(row.get('doc_id', ''))
            
            # 1. Thêm Node Chunk
            self.add_node(chunk_id, "CHUNK", {
                "text": row.get('chunk_text', ''),
                "embed_text": row.get('embed_text', ''),
                "chunk_type": row.get('chunk_type', ''),
                "source": "anle"
            })
            
            # 2. Thêm Node An Le & Relation
            if doc_id:
                self.add_node(doc_id, "AN_LE", {
                    "title": row.get('title', ''),
                    "case_type": row.get('case_type', ''),
                    "year": int(row.get('year', 0) if pd.notna(row.get('year')) else 0)
                })
                # Edge: Chunk -> BELONGS_TO -> An Le
                self.add_edge(chunk_id, doc_id, "BELONGS_TO")
                
                # 3. Quan hệ An Le -> Pháp Điển (Áp dụng Điều luật - Metadata Layer)
                applied_article_number = str(row.get('applied_article_number', ''))
                if applied_article_number and applied_article_number != '0' and applied_article_number.lower() != 'nan':
                    # Tạo Node Entity DIEU để nối
                    art_name = f"Điều {applied_article_number}"
                    ent_id = f"ENT::DIEU::{art_name.lower()}"
                    self.add_node(ent_id, "ENTITY", {"name": art_name, "entity_type": "DIEU"})
                    self.add_edge(doc_id, ent_id, "APPLIES_ARTICLE")

            # 4. Trích xuất Thực thể bằng Regex
            text = row.get('chunk_text', '')
            extracted = self.extract_entities_regex(text)
            for ent_name, ent_type in extracted:
                ent_id = f"ENT::{ent_type}::{ent_name.lower()}"
                self.add_node(ent_id, "ENTITY", {"name": ent_name, "entity_type": ent_type})
                self.add_edge(chunk_id, ent_id, "MENTIONS")

    def save(self) -> None:
        logger.info(f"Saving {len(self.nodes):,} nodes and {len(self.edges):,} edges...")
        
        # Format Nodes properties as JSON strings
        nodes_list = []
        for n in self.nodes.values():
            flat = {"id": n["id"], "label": n["label"]}
            flat["properties"] = json.dumps(n["properties"], ensure_ascii=False)
            nodes_list.append(flat)
            
        nodes_df = pd.DataFrame(nodes_list)
        edges_df = pd.DataFrame(self.edges)
        
        # Format Edges properties as JSON strings
        if not edges_df.empty:
            edges_df['properties'] = edges_df['properties'].apply(lambda x: json.dumps(x, ensure_ascii=False))

        nodes_df.to_parquet(self.output_dir / "nodes.parquet", index=False)
        edges_df.to_parquet(self.output_dir / "edges.parquet", index=False)
        logger.info(f"✅ Saved to {self.output_dir}")

    def run(self) -> None:
        self.process_phapdien()
        self.process_anle()
        self.save()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Chạy thử trên sample 2000 chunks để xác minh regex
    extractor = EntityExtractor(sample_size=2000)
    extractor.run()
