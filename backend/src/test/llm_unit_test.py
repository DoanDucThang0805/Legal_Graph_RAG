import time
from openai import OpenAI

BASE_URL = "http://localhost:8000/v1"
MODEL_NAME = "qwen3-14b"

client = OpenAI(
    api_key="dummy",
    base_url=BASE_URL,
)


def health_check():
    print("=" * 60)
    print("Checking model list...")

    models = client.models.list()
    for model in models.data:
        print(f"Found model: {model.id}")

    print("✓ Server is healthy\n")


def test_chat_tps():
    print("=" * 60)
    print("Testing chat + tokens/s...")

    prompt = "Hãy giới thiệu ngắn gọn về Việt Nam trong 100 từ."

    start = time.time()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Bạn là trợ lý AI hữu ích."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=256,
    )

    end = time.time()

    latency = end - start
    output_text = response.choices[0].message.content

    # token stats từ vLLM
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens

    tokens_per_sec = completion_tokens / latency if latency > 0 else 0

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(output_text)
    print("-" * 60)

    print(f"Latency: {latency:.3f} sec")
    print(f"Prompt tokens: {prompt_tokens}")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Total tokens: {total_tokens}")
    print(f"🔥 Throughput: {tokens_per_sec:.2f} tokens/sec")

    print("✓ Chat completion successful\n")


if __name__ == "__main__":
    try:
        health_check()
        test_chat_tps()

        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)

    except Exception as e:
        print("=" * 60)
        print("TEST FAILED")
        print("=" * 60)
        print(type(e).__name__)
        print(e)
