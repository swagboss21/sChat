"""
Simple test script to verify OpenRouter models work
"""
import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Models to test based on research
TEST_MODELS = [
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",  # More stable than gpt-5-mini
    "perplexity/sonar-pro",
    "google/gemini-2.0-flash-exp",
    "deepseek/deepseek-chat"
]

async def test_model(client: AsyncOpenAI, model: str) -> dict:
    """Test a single model with a simple prompt"""
    print(f"\n🧪 Testing {model}...")

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'Hello, I am working!' in one sentence."}],
                max_tokens=50
            ),
            timeout=30.0
        )

        result = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        print(f"✅ {model} - SUCCESS")
        print(f"   Response: {result}")
        print(f"   Tokens: {tokens}")

        return {
            "model": model,
            "status": "success",
            "response": result,
            "tokens": tokens
        }

    except asyncio.TimeoutError:
        print(f"❌ {model} - TIMEOUT (>30s)")
        return {"model": model, "status": "timeout", "error": "Timeout after 30s"}

    except Exception as e:
        error_msg = str(e)
        print(f"❌ {model} - ERROR: {error_msg}")
        return {"model": model, "status": "error", "error": error_msg}

async def main():
    """Test all models"""

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY not found in .env file")
        print("\nPlease add your API key to .env:")
        print("OPENROUTER_API_KEY=your_key_here")
        return

    print("🚀 Testing OpenRouter Models")
    print(f"   API Key: {api_key[:20]}..." if len(api_key) > 20 else "   API Key found")

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

    # Test all models in parallel
    tasks = [test_model(client, model) for model in TEST_MODELS]
    results = await asyncio.gather(*tasks)

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    print(f"\n✅ Successful: {len(successful)}/{len(TEST_MODELS)}")
    for r in successful:
        print(f"   - {r['model']}")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(TEST_MODELS)}")
        for r in failed:
            print(f"   - {r['model']}: {r.get('error', 'Unknown error')}")

    print("\n" + "="*60)

    if len(successful) >= 3:
        print("✅ Enough models working! You can proceed.")
    else:
        print("⚠️  Not enough models working. Check your API key and credits.")

if __name__ == "__main__":
    asyncio.run(main())
