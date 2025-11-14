#!/usr/bin/env python3
"""Test different Gemini model IDs on OpenRouter to find the best one"""

import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Models to test
GEMINI_MODELS = [
    "google/gemini-2.0-flash-exp:free",  # Free experimental
    "google/gemini-2.0-flash-001",       # Stable paid ($0.10 input, $0.40 output)
    "google/gemini-flash-1.5-exp",       # 1.5 Flash experimental
]

async def test_model(model: str):
    """Test a single Gemini model"""
    print(f"\n{'='*60}")
    print(f"Testing: {model}")
    print('='*60)

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=f"{model}:online",  # Test with :online suffix
                messages=[{"role": "user", "content": "What is today's date? (Just give me the date)"}],
                max_tokens=100
            ),
            timeout=30.0
        )

        content = response.choices[0].message.content
        tokens = response.usage.completion_tokens if response.usage else 0

        print(f"✅ SUCCESS (with :online)")
        print(f"Response: {content}")
        print(f"Tokens: {tokens}")

        # Also test without :online suffix
        response2 = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,  # Without :online
                messages=[{"role": "user", "content": "What is 2+2?"}],
                max_tokens=50
            ),
            timeout=30.0
        )

        content2 = response2.choices[0].message.content
        print(f"✅ Also works without :online")
        print(f"Response: {content2}")

        return True

    except Exception as e:
        error_str = str(e)
        print(f"❌ FAILED")
        print(f"Error: {error_str}")

        # Try without :online suffix if :online failed
        if ":online" in error_str or "404" in error_str:
            try:
                print(f"\nRetrying WITHOUT :online suffix...")
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,  # Without :online
                        messages=[{"role": "user", "content": "What is 2+2?"}],
                        max_tokens=50
                    ),
                    timeout=30.0
                )

                content = response.choices[0].message.content
                tokens = response.usage.completion_tokens if response.usage else 0

                print(f"✅ SUCCESS (without :online)")
                print(f"Response: {content}")
                print(f"Tokens: {tokens}")
                print(f"⚠️  NOTE: This model does NOT support :online suffix for web search")

                return True

            except Exception as e2:
                print(f"❌ Also failed without :online: {e2}")
                return False

        return False

async def main():
    print("Testing Gemini Models on OpenRouter")
    print("="*60)

    results = {}

    for model in GEMINI_MODELS:
        success = await test_model(model)
        results[model] = success
        await asyncio.sleep(1)  # Rate limiting

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    working_models = [m for m, success in results.items() if success]

    if working_models:
        print(f"\n✅ Working Models ({len(working_models)}):")
        for model in working_models:
            print(f"  - {model}")

        print(f"\n🎯 RECOMMENDATION:")
        if "google/gemini-2.0-flash-exp:free" in working_models:
            print(f"  Use: google/gemini-2.0-flash-exp:free")
            print(f"  Reason: FREE and latest version (Gemini 2.0)")
        elif "google/gemini-2.0-flash-001" in working_models:
            print(f"  Use: google/gemini-2.0-flash-001")
            print(f"  Reason: Stable Gemini 2.0 ($0.10 input, $0.40 output - cheaper than 2.5)")
        elif "google/gemini-flash-1.5-exp" in working_models:
            print(f"  Use: google/gemini-flash-1.5-exp")
            print(f"  Reason: Experimental but working Gemini 1.5")
    else:
        print("\n❌ No working Gemini models found!")

    failed_models = [m for m, success in results.items() if not success]
    if failed_models:
        print(f"\n❌ Failed Models ({len(failed_models)}):")
        for model in failed_models:
            print(f"  - {model}")

if __name__ == "__main__":
    asyncio.run(main())
