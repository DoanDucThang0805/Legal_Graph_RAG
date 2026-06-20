import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
logger = logging.getLogger(__name__)


class GeminiLLM:
    """LangChain-compatible Gemini wrapper."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash",
        temperature: float = 0.0,
        max_retries: int = 3,
        api_key: Optional[str] = None,
    ):
        _api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not _api_key:
            raise ValueError("GOOGLE_API_KEY not set.")

        self.model_name = model_name
        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=_api_key,
            temperature=temperature,
            max_retries=max_retries,
        )
        logger.info("GeminiLLM initialized: model=%s", model_name)

    @property
    def client(self) -> ChatGoogleGenerativeAI:
        return self._llm

    def invoke(self, prompt: str) -> str:
        response = self._llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    async def ainvoke(self, prompt: str) -> str:
        response = await self._llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    llm = GeminiLLM()
    print("Model:", llm.model_name)

    # sync
    print("\n[sync]")
    print(llm.invoke("Hợp đồng lao động là gì? Trả lời ngắn gọn."))

    # async
    print("\n[async]")
    print(asyncio.run(llm.ainvoke("Hợp đồng lao động là gì? Trả lời ngắn gọn.")))
