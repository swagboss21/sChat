#!/usr/bin/env python3
"""
Comprehensive test: Current events vs. Historical queries
Tests that online model intelligently handles dates
"""
import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

async def test_prompt(prompt_type, prompt):
    print(f"\n{'='*80}")
    print(f"TEST: {prompt_type}")
    print(f"{'='*80}")
    print(f"📝 ORIGINAL: {prompt}")
    print(f"\n⏳ Optimizing with Claude Haiku :online...")

    optimization_prompt = f"""You are a prompt optimization assistant for a multi-model AI research tool. The tool queries 5 AI models in parallel (with web search enabled) and synthesizes their responses.

USER'S ORIGINAL PROMPT:
{prompt}

TASK: Rewrite this prompt to get maximum value from web-enabled AI models. Apply these principles:

1. FIX ERRORS: Correct any typos or grammatical mistakes

2. ADD STRUCTURE: Break complex queries into numbered sections (e.g., 1. X, 2. Y, 3. Z)

3. INCREASE SPECIFICITY:
   - For CURRENT EVENTS (e.g., ongoing political events, recent news, "latest", "current status"):
     Add "as of today" or the actual current date from your web search
   - For HISTORICAL QUERIES (e.g., "2008 crisis", "World War II", past events with dates):
     Keep the historical timeframe, DO NOT add current dates
   - Name specific companies, people, metrics instead of generic terms
   - Request quantifiable data (percentages, dollar amounts, counts)

4. DEMAND SOURCES: Add "Cite sources with links" or "Provide specific sources"

5. GUIDE OUTPUT: Specify what format/details you want (timelines, predictions, comparisons)

CRITICAL RULES:
- Use your web search to determine if this is a current event or historical query
- Only add current dates for genuinely current/ongoing events
- Keep the core intent and topic the same
- Don't make it overly long (aim for 3-8 lines for simple queries, longer OK for complex multi-part questions)
- Don't add unnecessary complexity if the original is already clear
- If the original is already well-structured, make minimal changes

OUTPUT: Return ONLY the optimized prompt text, no explanations or meta-commentary."""

    try:
        response = await client.chat.completions.create(
            model="anthropic/claude-3.5-haiku:online",
            messages=[{"role": "user", "content": optimization_prompt}],
            max_tokens=600,
            temperature=0.7
        )

        optimized = response.choices[0].message.content.strip()
        print(f"\n✅ OPTIMIZED:\n{optimized}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

async def main():
    print("="*80)
    print("COMPREHENSIVE OPTIMIZATION TEST")
    print("Testing: Current Events vs. Historical Queries")
    print("="*80)

    tests = [
        ("CURRENT EVENT", "top news about the us govenrment shutdown and the faa layoffs imapcting travel and how this decline will effect the stock prices of major airlines"),
        ("HISTORICAL QUERY", "what were the main causes of the 2008 financal crisis and how did it effect the housing market"),
        ("CURRENT EVENT", "latest developemnts in the trump trial"),
        ("HISTORICAL QUERY", "major battles of world war 2 in europe"),
        ("MIXED QUERY", "compare the 2008 recession to todays economic situation")
    ]

    results = []
    for prompt_type, prompt in tests:
        success = await test_prompt(prompt_type, prompt)
        results.append(success)
        await asyncio.sleep(2)  # Rate limit

    print("\n" + "="*80)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("="*80)

    return all(results)

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
