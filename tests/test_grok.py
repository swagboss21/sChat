"""Quick test of correct Grok models"""
import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

TEST_MODELS = [
    "x-ai/grok-4",
    "x-ai/grok-4-fast",
]

async def test_model(client, model):
    print(f"\n🧪 Testing {model}...")
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'Hello' in one word."}],
                max_tokens=10
            ),
            timeout=30.0
        )
        print(f"✅ {model} - SUCCESS")
        return {"model": model, "status": "success"}
    except Exception as e:
        print(f"❌ {model} - ERROR: {str(e)[:100]}")
        return {"model": model, "status": "error"}

async def main():
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    results = await asyncio.gather(*[test_model(client, m) for m in TEST_MODELS])

    successful = [r for r in results if r["status"] == "success"]
    print(f"\n✅ Working: {[r['model'] for r in successful]}")

asyncio.run(main())
