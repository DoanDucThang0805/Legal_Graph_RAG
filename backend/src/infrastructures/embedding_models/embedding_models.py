import logging
from typing import List

import torch

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except ImportError:
        HuggingFaceEmbeddings = None


logger = logging.getLogger(__name__)

# vnlegal-lal là model Qwen3-Embedding: 1024 chiều, last-token pooling,
# max 2048 token. Theo model card:
#   - QUERY  → BẮT BUỘC thêm instruction prefix dưới đây.
#   - PASSAGE/document → KHÔNG thêm prefix, encode raw text.
# Tham khảo: https://huggingface.co/darklethelong/vnlegal-lal
QUERY_INSTRUCTION = (
    "Instruct: Given a Vietnamese legal question, retrieve relevant legal "
    "passages that answer the question\nQuery: "
)
MAX_SEQ_LENGTH = 2048


class LegalEmbeddingModel:
    """
    Wrapper cho model embedding pháp lý tiếng Việt.

    Mặc định:
        darklethelong/vnlegal-lal (Qwen3-Embedding, 1024-dim, last-token pooling)

    Lưu ý quan trọng:
        - QUERY phải có instruction prefix (xem ``QUERY_INSTRUCTION``);
          ``embed_query`` tự động thêm. PASSAGE thì không.
        - Giới hạn 2048 token (tokenizer config báo nhầm 512 — bỏ qua).

    Tương thích:
        - LangChain
        - Neo4j Vector Index
        - Qdrant
        - Chroma
        - FAISS
    """

    def __init__(
        self,
        model_name: str = "darklethelong/vnlegal-lal",
        device: str | None = None,
        batch_size: int = 64,
        max_seq_length: int = MAX_SEQ_LENGTH,
    ):
        if HuggingFaceEmbeddings is None:
            raise ImportError(
                "Please install:\n"
                "pip install langchain-huggingface sentence-transformers"
            )

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            f"Loading embedding model={model_name}, "
            f"device={device}, "
            f"batch_size={batch_size}"
        )

        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={
                "device": device,
                "trust_remote_code": True,
            },
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": batch_size,
            },
        )

        # Ép max_seq_length = 2048 đúng model card (tokenizer config báo nhầm 512).
        try:
            self.embeddings.client.max_seq_length = max_seq_length
            logger.info(f"max_seq_length set = {max_seq_length}")
        except Exception as e:
            logger.warning(f"Không set được max_seq_length: {e}")

        # Kiểm tra dimension
        try:
            dim = len(self.embed_query("kiểm tra kích thước vector"))
            logger.info(f"Embedding dimension = {dim}")
        except Exception as e:
            logger.warning(f"Cannot determine embedding dimension: {e}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed danh sách document/chunk (passage).

        KHÔNG thêm instruction prefix — theo model card vnlegal-lal, passage
        được encode ở dạng raw text. Khi index chunk, truyền vào trường
        ``embed_text`` (đã chứa sẵn context prefix phân cấp).
        """
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        Embed câu hỏi người dùng.

        BẮT BUỘC thêm instruction prefix chuẩn Qwen3-Embedding:
        ``"Instruct: ...\\nQuery: <câu hỏi>"``. Thiếu prefix này chất lượng
        retrieval giảm rõ rệt (query và passage lệch không gian biểu diễn).
        """
        return self.embeddings.embed_query(f"{QUERY_INSTRUCTION}{text}")

    def embedding_dimension(self) -> int:
        """
        Trả về số chiều vector embedding.
        """
        return len(self.embed_query("dimension check"))


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    model = LegalEmbeddingModel()

    print("\n=== MODEL INFO ===")
    print(f"Embedding dimension: {model.embedding_dimension()}")

    query = (
        "Người lao động đơn phương chấm dứt hợp đồng lao động "
        "trái pháp luật phải bồi thường như thế nào?"
    )

    print("\n=== QUERY TEST ===")
    query_embedding = model.embed_query(query)

    print(f"Query: {query}")
    print(f"Vector dimension: {len(query_embedding)}")
    print(f"First 10 values: {query_embedding[:10]}")

    documents = [
        "Người lao động đơn phương chấm dứt hợp đồng trái pháp luật phải bồi thường cho người sử dụng lao động.",
        "Người lao động có quyền nghỉ việc nếu báo trước theo quy định của Bộ luật Lao động.",
        "Hợp đồng lao động là sự thỏa thuận giữa người lao động và người sử dụng lao động."
    ]

    print("\n=== DOCUMENT TEST ===")
    doc_embeddings = model.embed_documents(documents)

    print(f"Number of documents: {len(doc_embeddings)}")
    print(f"Embedding dimension: {len(doc_embeddings[0])}")

    for i, doc in enumerate(documents):
        print(f"\nDocument {i + 1}:")
        print(doc[:80] + "...")
        print(f"First 5 values: {doc_embeddings[i][:5]}")

    print("\n=== SUCCESS ===")
    print("Embedding model loaded and working correctly.")
