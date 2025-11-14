from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import AsyncOpenAI
import asyncio
import os
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize OpenRouter client
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Available models for initial prompts (verified working with :online web search)
AVAILABLE_MODELS = [
    "openai/gpt-4o:online",
    "anthropic/claude-sonnet-4.5:online",
    "perplexity/sonar-pro",  # Already has built-in web search
    "x-ai/grok-4:online",
    "meta-llama/llama-3.1-70b-instruct:online"
]

# Available aggregator models (can use DeepSeek for synthesis only)
AGGREGATOR_MODELS = AVAILABLE_MODELS + ["deepseek/deepseek-chat:online"]

# Aggregation model (default with web search enabled)
AGGREGATOR_MODEL = "anthropic/claude-sonnet-4.5:online"

class ChatRequest(BaseModel):
    prompt: str
    models: List[str]
    aggregator: str = "anthropic/claude-sonnet-4.5"  # Default aggregator

class OptimizeRequest(BaseModel):
    prompt: str

class ModelResponse(BaseModel):
    model: str
    response: str
    tokens: int

class ChatResponse(BaseModel):
    aggregated: str
    individual: List[ModelResponse]

async def query_model(model: str, prompt: str) -> Dict:
    """Query a single model with timeout and error handling"""
    # Grok models need more time for X/Twitter search integration
    timeout = 120.0 if "grok" in model.lower() else 60.0

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,  # Increased for full, quality responses
                timeout=timeout
            ),
            timeout=timeout
        )

        # Get token count with validation (OpenRouter sometimes returns inflated values)
        tokens = 0
        if response.usage:
            # Use completion_tokens for actual output size
            tokens = response.usage.completion_tokens
            # Fallback to total_tokens if completion not available, but cap at max_tokens
            if not tokens:
                tokens = min(response.usage.total_tokens, 4000)

        return {
            "model": model,
            "response": response.choices[0].message.content,
            "tokens": tokens,
            "error": None
        }
    except asyncio.TimeoutError:
        return {
            "model": model,
            "response": "",
            "tokens": 0,
            "error": f"Request timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "model": model,
            "response": "",
            "tokens": 0,
            "error": str(e)
        }

async def aggregate_responses(query: str, responses: List[Dict], aggregator_model: str) -> str:
    """Use specified model to aggregate all model responses"""

    # Strip :online suffix from aggregator to prevent it from doing its own web search
    # The aggregator should ONLY synthesize the responses, not search independently
    aggregator_model_clean = aggregator_model.replace(':online', '')

    # Format individual responses for the aggregation prompt
    # Add context hints for models with special capabilities
    model_notes = {
        "anthropic/claude-sonnet-4.5:online": " (strong reasoning, detailed analysis)",
        "x-ai/grok-4:online": " (real-time X/Twitter access)",
        "perplexity/sonar-pro": " (native web search with citations)"
    }

    formatted_responses = ""
    for idx, resp in enumerate(responses, 1):
        model_name = resp['model']
        model_note = model_notes.get(model_name, "")

        if resp["error"]:
            formatted_responses += f"\n{idx}. **{model_name}**{model_note}: [ERROR: {resp['error']}]\n"
        else:
            formatted_responses += f"\n{idx}. **{model_name}**{model_note}:\n{resp['response']}\n"

    aggregation_prompt = f"""You are synthesizing responses from multiple AI models that already performed web searches.

DO NOT perform any web searches yourself.
DO NOT include meta-commentary about your process (e.g., "I need to search...", "Now let me...", "Based on my searches...").
Present ONLY the final synthesis in the format below.

Original Query: {query}

Model Responses (already web-searched):
{formatted_responses}

Provide a structured synthesis following this exact format:

## KEY CONSENSUS
Facts and findings that 3+ models agree on. Include specific numbers, dates, and names where applicable. Cite sources.

## UNIQUE INSIGHTS
Information found by ONLY 1-2 models that adds unique value:
- Exclusive data points, statistics, or sources not mentioned by others
- Unique URLs, documents, or social media posts (especially X/Twitter from Grok)
- Novel angles or perspectives others missed
DO NOT repeat information already covered in Key Consensus.

## CONTRADICTIONS
Where models disagree on facts, predictions, or interpretations. Explain which models disagree and what evidence each provides.

## ACTIONABLE INTELLIGENCE
Concrete, specific takeaways:
- Immediate next steps (24-72 hour timeline)
- Key decision points to monitor
- Business/planning implications
- Specific people, organizations, or events to track

CRITICAL RULES:
- Work ONLY with the model responses provided above
- Do NOT search the web - the models already did that
- Do NOT include any process commentary or explanations about what you're doing
- Start directly with "## KEY CONSENSUS" (no preamble)
- Do not repeat the same facts across multiple sections
- Prioritize specificity (dates, names, numbers) and source citations from the model responses"""

    try:
        response = await client.chat.completions.create(
            model=aggregator_model_clean,  # Use cleaned model name without :online
            messages=[{"role": "user", "content": aggregation_prompt}],
            max_tokens=5000  # Increased for comprehensive synthesis
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error during aggregation: {str(e)}"

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint that queries multiple models in parallel
    and aggregates their responses
    """

    # Validate models
    invalid_models = [m for m in request.models if m not in AVAILABLE_MODELS]
    if invalid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid models: {invalid_models}"
        )

    if not request.models:
        raise HTTPException(
            status_code=400,
            detail="At least one model must be selected"
        )

    # Query all models in parallel
    tasks = [query_model(model, request.prompt) for model in request.models]
    raw_responses = await asyncio.gather(*tasks)

    # Filter out completely failed responses but keep partial data
    successful_responses = [r for r in raw_responses if not r["error"]]

    if not successful_responses:
        raise HTTPException(
            status_code=500,
            detail="All model queries failed"
        )

    # Aggregate responses using selected aggregator model
    aggregated = await aggregate_responses(request.prompt, raw_responses, request.aggregator)

    # Format individual responses for the frontend
    individual = [
        ModelResponse(
            model=r["model"],
            response=r["response"] if not r["error"] else f"Error: {r['error']}",
            tokens=r["tokens"]
        )
        for r in raw_responses
    ]

    # Log the full query for comparison/debugging
    import json
    from pathlib import Path
    from datetime import datetime
    log_file = Path("query_log.json")

    try:
        logs = json.loads(log_file.read_text()) if log_file.exists() else []
    except:
        logs = []

    logs.append({
        "timestamp": datetime.now().isoformat(),
        "user_prompt": request.prompt,
        "models_used": request.models,
        "aggregator": request.aggregator,
        "individual_responses": [
            {
                "model": r["model"],
                "response": r["response"],
                "tokens": r["tokens"],
                "error": r["error"]
            }
            for r in raw_responses
        ],
        "aggregated_response": aggregated,
        "total_tokens": sum(r["tokens"] for r in raw_responses)
    })

    log_file.write_text(json.dumps(logs, indent=2))

    return ChatResponse(
        aggregated=aggregated,
        individual=individual
    )

@app.post("/api/optimize")
async def optimize_prompt(request: OptimizeRequest):
    """
    Optimize a user's prompt for better research results.
    Uses Claude Haiku (offline) with system date injection - NO web search needed.
    """
    from datetime import datetime
    today = datetime.now().strftime("%B %d, %Y")  # e.g., "November 10, 2025"

    optimization_prompt = f"""You are a prompt optimization assistant for a multi-model AI research tool. The tool queries 5 AI models in parallel (with web search enabled) and synthesizes their responses.

IMPORTANT CONTEXT:
- Today's actual date is: {today}
- The research models will do web searches, not you
- Your job is to optimize the prompt structure, not to search for information

USER'S ORIGINAL PROMPT:
{request.prompt}

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
        response = await client.chat.completions.create(
            model="anthropic/claude-3.5-haiku",  # NO :online suffix - we don't need web search
            messages=[{"role": "user", "content": optimization_prompt}],
            max_tokens=600,  # Slightly increased for complex prompts
            temperature=0.5  # Lower temperature for more consistent format
        )

        optimized = response.choices[0].message.content.strip()

        # Clean up any explanatory preambles that slip through
        # Remove common patterns like "I'll first..." or "Based on..."
        lines = optimized.split('\n')
        cleaned_lines = []
        skip_mode = False

        for line in lines:
            # Skip lines that are meta-commentary
            if any(phrase in line.lower() for phrase in [
                "i'll first", "i'll optimize", "based on", "rationale for",
                "here's the optimized", "here's an optimized", "the prompt provides"
            ]):
                skip_mode = True
                continue
            # If we hit actual content after skip mode, start collecting
            if skip_mode and line.strip() and not line.startswith(' '):
                skip_mode = False
            if not skip_mode:
                cleaned_lines.append(line)

        optimized = '\n'.join(cleaned_lines).strip()

        # Log the optimization for comparison/debugging
        import json
        from pathlib import Path
        log_file = Path("optimization_log.json")

        try:
            logs = json.loads(log_file.read_text()) if log_file.exists() else []
        except:
            logs = []

        logs.append({
            "timestamp": datetime.now().isoformat(),
            "original": request.prompt,
            "optimized": optimized,
            "model": "anthropic/claude-3.5-haiku",
            "tokens": response.usage.total_tokens if response.usage else 0
        })

        log_file.write_text(json.dumps(logs, indent=2))

        return {"optimized": optimized}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {str(e)}"
        )

@app.get("/")
async def root():
    """Redirect to static index.html"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
