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

Pipeline chính:

```text
Knowledge Data
      │
      ▼
Knowledge Processing
      │
      ▼
Embedding Model
      │
      ▼
Neo4j Vector Database
      │
      ▼
Hybrid Retrieval
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
│   │   └── Chứa các API endpoint của hệ thống
│   │
│   ├── config/
│   │   └── config.yaml
│   │       Chứa các cấu hình dùng chung cho toàn bộ pipeline
│   │
│   ├── infrastructures/
│   │   │
│   │   ├── database/
│   │   │   └── neo4j_db/
│   │   │       Kết nối và thao tác với Neo4j
│   │   │
│   │   ├── embedding_models/
│   │   │   Chứa các mô hình embedding
│   │   │
│   │   └── gen_llm_models/
│   │       Chứa các mô hình sinh văn bản (LLM)
│   │
│   ├── knowledge_processing/
│   │   Xử lý dữ liệu tri thức
│   │   (chunking, cleaning, entity extraction,
│   │    graph building, indexing,...)
│   │
│   ├── knowledge_data/
│   │   Kho dữ liệu pháp lý đầu vào
│   │
│   └── retrieval/
│       └── hybrid_retrieval.py
│       Thành phần truy xuất dữ liệu
│       từ Vector Search và Graph Search
│
├── frontend/
│   Giao diện người dùng
│
├── .env
│   Biến môi trường của dự án
│
├── docker-compose.yml
│   Khởi tạo Neo4j và các service liên quan
│
└── README.md
```

---

## 4. Chức năng các module

### Config

Quản lý toàn bộ cấu hình của hệ thống:

* Neo4j
* Embedding Model
* LLM
* Retrieval Parameters
* Pipeline Settings

### Knowledge Data

Lưu trữ dữ liệu pháp lý:

* Luật
* Nghị định
* Thông tư
* Án lệ
* Văn bản hướng dẫn

### Knowledge Processing

Chịu trách nhiệm chuyển đổi dữ liệu thô thành dữ liệu có thể truy xuất:

* Đọc tài liệu
* Tiền xử lý văn bản
* Chunking
* Sinh embedding
* Trích xuất thực thể
* Xây dựng Knowledge Graph
* Index dữ liệu vào Neo4j

### Database

Tầng kết nối cơ sở dữ liệu.

Hiện tại:

* Neo4j Graph Database
* Neo4j Vector Index

### Embedding Models

Quản lý các mô hình embedding:

Ví dụ:

* BGE
* E5
* GTE
* Nomic

### Gen LLM Models

Quản lý các mô hình sinh phản hồi:

Ví dụ:

* GPT
* Gemini
* Qwen
* Llama

### Retrieval

Truy xuất tri thức phục vụ chatbot.

Bao gồm:

* Vector Retrieval
* Graph Retrieval
* Hybrid Retrieval

### API

Cung cấp endpoint cho frontend và các service bên ngoài.

```
POST /chat
POST /ingest
GET /health
```

---

## 5. Database

Neo4j được sử dụng đồng thời cho:

* Graph Database
* Vector Database

Thông tin kết nối được cấu hình trong file `.env`.

Truy cập Neo4j Browser:

```text
http://localhost:7474
```
