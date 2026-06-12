# AI Guru - Chatbot Pháp Lý sử dụng GraphRAG

## 1. Khởi động hệ thống

### Khởi động Neo4j

Từ thư mục gốc của dự án:

```bash
docker compose up
```

Hoặc chạy nền:

```bash
docker compose up -d
```

### Dừng Neo4j

```bash
docker compose stop
```

### Khởi động lại sau khi stop

```bash
docker compose start
```

### Xóa container

```bash
docker compose down
```

### Xóa toàn bộ dữ liệu Neo4j

```bash
docker compose down -v
```

---

## 2. Kiến trúc tổng quan

Hệ thống được xây dựng theo kiến trúc GraphRAG cho bài toán hỏi đáp pháp lý.

Pipeline xử lý tri thức:

```text
Knowledge Data
      │
      ▼
Document Loading
      │
      ▼
Chunking
      │
      ▼
Entity Extraction
      │
      ▼
Graph Construction
      │
      ▼
Embedding Generation
      │
      ▼
Neo4j Graph + Vector Database
```

Pipeline hỏi đáp:

```text
User Question
      │
      ▼
Embedding
      │
      ▼
Hybrid Retrieval
      ├── Vector Retrieval
      └── Graph Retrieval
      │
      ▼
Context Building
      │
      ▼
LLM Generation
      │
      ▼
Answer
```

---

## 3. Cấu trúc thư mục

```text
AIGURU/
│
├── backend/
│   │
│   ├── api/
│   │   └── API endpoints
│   │
│   ├── config/
│   │   └── config.yaml
│   │
│   ├── infrastructures/
│   │   │
│   │   ├── database/
│   │   │   └── neo4j_db/
│   │   │
│   │   ├── embedding_models/
│   │   │
│   │   └── gen_llm_models/
│   │
│   ├── models/
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── entity.py
│   │   └── relation.py
│   │
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── ingest.py
│   │   └── retrieval.py
│   │
│   ├── knowledge_processing/
│   │   ├── document_loader.py
│   │   ├── chunker.py
│   │   ├── entity_extractor.py
│   │   ├── graph_builder.py
│   │   ├── embedder.py
│   │   └── index_builder.py
│   │
│   ├── knowledge_data/
│   │
│   └── retrieval/
│       ├── vector_retrieval.py
│       ├── graph_retrieval.py
│       └── hybrid_retrieval.py
│
├── frontend/
│
├── .env
│
├── docker-compose.yml
│
└── README.md
```

---

## 4. Chức năng các module

### Config

Quản lý cấu hình của toàn bộ hệ thống:

* Neo4j
* Embedding Models
* LLM Models
* Retrieval Parameters
* GraphRAG Parameters

---

### Knowledge Data

Kho dữ liệu pháp lý đầu vào:

* Luật
* Nghị định
* Thông tư
* Án lệ
* Văn bản hướng dẫn

---

### Models

Định nghĩa các thực thể (domain models) của Knowledge Graph.

Ví dụ:

* Document
* Chunk
* Entity
* Relation

Các model này mô tả cấu trúc dữ liệu được lưu trong Neo4j.

Ví dụ:

```text
(Document)
(Chunk)
(Entity)
(Relation)
```

---

### Schemas

Định nghĩa dữ liệu trao đổi qua API.

Ví dụ:

* ChatRequest
* ChatResponse
* IngestRequest
* RetrievalResponse

Sử dụng Pydantic để validate dữ liệu đầu vào và đầu ra.

---

### Knowledge Processing

Pipeline xây dựng kho tri thức.

Bao gồm:

* Đọc tài liệu
* Tiền xử lý văn bản
* Chunking
* Trích xuất thực thể
* Xây dựng Knowledge Graph
* Sinh embedding
* Tạo Vector Index
* Lưu dữ liệu vào Neo4j

---

### Database

Tầng kết nối cơ sở dữ liệu.

Hiện tại sử dụng:

* Neo4j Graph Database
* Neo4j Vector Index

---

### Embedding Models

Quản lý các mô hình embedding.

Ví dụ:

* BGE
* E5
* GTE
* Nomic

---

### Gen LLM Models

Quản lý các mô hình sinh phản hồi.

Ví dụ:

* GPT
* Gemini
* Qwen
* Llama

---

### Retrieval

Truy xuất tri thức phục vụ chatbot.

Bao gồm:

#### Vector Retrieval

Tìm kiếm ngữ nghĩa dựa trên embedding.

#### Graph Retrieval

Tìm kiếm theo quan hệ trong Knowledge Graph.

#### Hybrid Retrieval

Kết hợp Vector Search và Graph Traversal để xây dựng context tối ưu cho LLM.

---

### API

Cung cấp endpoint cho frontend và các service bên ngoài.

```http
POST /chat
POST /ingest
GET /health
```

---

## 5. Graph Schema (Draft)

Schema ban đầu của hệ thống:

```text
(Document)
      │
      └── HAS_CHUNK
                │
                ▼
             (Chunk)
                │
                └── MENTIONS
                          │
                          ▼
                       (Entity)
```

Ví dụ:

```text
Document
├── id
├── title
└── source

Chunk
├── id
├── content
├── embedding
└── chunk_index

Entity
├── id
├── name
└── entity_type
```

---

## 6. Database

Neo4j được sử dụng đồng thời cho:

* Graph Database
* Vector Database

Truy cập Neo4j Browser:

```text
http://localhost:7474
```

Thông tin kết nối được cấu hình trong file `.env`.
