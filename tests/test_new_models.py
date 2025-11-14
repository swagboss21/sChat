"""
Test Grok and find a 5th model
"""
import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Models to test
TEST_MODELS = [
    "x-ai/grok-beta",
    "meta-llama/llama-3.1-70b-instruct",  # Popular open source
    "google/gemini-flash-1.5",  # Cheaper Gemini
    "mistralai/mistral-large",  # Mistral's best
]

async def test_model(client: AsyncOpenAI, model: str) -> dict:
    """Test a single model"""
    print(f"\n🧪 Testing {model}...")

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'Hello, I work!' in one sentence."}],
                max_tokens=50
            ),
            timeout=30.0
        )

        result = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        print(f"✅ {model} - SUCCESS")
        print(f"   Response: {result}")
        print(f"   Tokens: {tokens}")

        return {"model": model, "status": "success", "response": result, "tokens": tokens}

    except Exception as e:
        error_msg = str(e)
        print(f"❌ {model} - ERROR: {error_msg}")
        return {"model": model, "status": "error", "error": error_msg}

async def main():
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY not found")
        return

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

    print("🚀 Testing New Models for 5-Model Setup")

    tasks = [test_model(client, model) for model in TEST_MODELS]
    results = await asyncio.gather(*tasks)

    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)

    successful = [r for r in results if r["status"] == "success"]

    print(f"\n✅ Successful: {len(successful)}/{len(TEST_MODELS)}")
    for r in successful:
        print(f"   - {r['model']}")

if __name__ == "__main__":
    asyncio.run(main())
