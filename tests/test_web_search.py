"""Test that :online suffix enables web search"""
import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

async def test_web_search():
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

    print("🧪 Testing web search with :online models...")
    print("Query: 'What is today's date and top news story?'\n")

    # Test one model with web search
    model = "openai/gpt-4o:online"

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "What is today's date and what is the top news story today? Be specific about the date."}],
                max_tokens=500
            ),
            timeout=45.0
        )

        result = response.choices[0].message.content

        print(f"✅ {model}")
        print(f"\nResponse:\n{result}\n")

        # Check if it mentions current date (2025)
        if "2025" in result or "November" in result:
            print("✅ SUCCESS! Model accessed current web information!")
        else:
            print("⚠️  Model may not have searched the web (check response)")

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

asyncio.run(test_web_search())
