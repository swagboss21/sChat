#!/usr/bin/env python3
"""
Final test: No web search, system date injection
"""
import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

async def test_optimization():
    today = datetime.now().strftime("%B %d, %Y")

    test_prompt = "top news about the us govenrment shutdown and the faa layoffs imapcting travel and how this decline will effect the stock prices of major airlines"

    print("=" * 80)
    print("FINAL TEST: System Date Injection (NO WEB SEARCH)")
    print("=" * 80)
    print(f"\n📅 System date: {today}")
    print(f"\n📝 ORIGINAL PROMPT:")
    print(f'"{test_prompt}"')
    print("\n" + "=" * 80)

    optimization_prompt = f"""You are a prompt optimization assistant for a multi-model AI research tool. The tool queries 5 AI models in parallel (with web search enabled) and synthesizes their responses.

IMPORTANT CONTEXT:
- Today's actual date is: {today}
- The research models will do web searches, not you
- Your job is to optimize the prompt structure, not to search for information

USER'S ORIGINAL PROMPT:
{test_prompt}

TASK: Rewrite this prompt to get maximum value from web-enabled AI models. Apply these principles:

1. FIX ERRORS: Correct any typos or grammatical mistakes

2. ADD STRUCTURE: Break complex queries into numbered sections (e.g., 1. X, 2. Y, 3. Z)

3. INCREASE SPECIFICITY:
   - For CURRENT EVENTS (e.g., "latest", "current", "today", "recent news", ongoing situations):
     Add "as of {today}" to the prompt
   - For HISTORICAL QUERIES (e.g., "2008 crisis", "World War II", queries about past events with dates):
     Keep the historical timeframe, DO NOT add current dates
   - For queries asking to "compare past to present", add {today} only for the present-day portion
   - Name specific companies, people, metrics instead of generic terms
   - Request quantifiable data (percentages, dollar amounts, counts)

4. DEMAND SOURCES: Add "Cite sources with links" or "Provide specific sources"

5. GUIDE OUTPUT: Specify what format/details you want (timelines, predictions, comparisons)

CRITICAL RULES:
- Determine if this is current/historical based on keywords in the prompt (don't search, just analyze the text)
- Only add {today} for genuinely current/ongoing events
- Keep the core intent and topic the same
- Don't make it overly long (aim for 3-8 lines for simple queries, longer OK for complex multi-part questions)
- Don't add unnecessary complexity if the original is already clear
- If the original is already well-structured, make minimal changes

OUTPUT: Return ONLY the optimized prompt text, no explanations or meta-commentary.

EXAMPLE BAD OUTPUT (do NOT do this):
"I'll analyze this prompt... Based on the keywords, here's the optimized version: [prompt]"

EXAMPLE GOOD OUTPUT (do this):
"[Just the optimized prompt with no preamble or explanation]"
"""

    try:
        print("⏳ Calling Claude Haiku (NO :online, using system date)...\n")

        response = await client.chat.completions.create(
            model="anthropic/claude-3.5-haiku",  # NO :online
            messages=[{"role": "user", "content": optimization_prompt}],
            max_tokens=600,
            temperature=0.5
        )

        optimized = response.choices[0].message.content.strip()

        print("✅ OPTIMIZED PROMPT:")
        print(f"{optimized}")
        print("\n" + "=" * 80)

        # Check if correct date is used
        if today in optimized:
            print(f"\n✅ SUCCESS: Uses correct system date ({today})")
        else:
            print(f"\n⚠️  WARNING: Expected date '{today}' not found in output")
            if "November 7" in optimized or "November 8" in optimized:
                print(f"❌ FAIL: Found wrong date (web search was used despite NO :online)")
            elif "as of today" in optimized.lower():
                print(f"✅ ACCEPTABLE: Uses 'as of today' (lets research models determine date)")

        print(f"\n💰 Cost: ~$0.003-0.005 (cheaper, no web search!)")
        print("⚡ Speed: ~1-2 seconds (faster, no web search!)")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(test_optimization())
    exit(0 if success else 1)
