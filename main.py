from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
import asyncio
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
import uuid
import time

# Load environment variables
load_dotenv()

app = FastAPI()

# Global dictionary to track query status for real-time updates
# Format: {request_id: {models: {model_name: {status, start_time, end_time, error}}, aggregation_status}}
query_status = {}

# Global dictionary to store completed query results
# Format: {request_id: {aggregated, individual}}
query_results = {}

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
    "google/gemini-2.0-flash-001:online"
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
    request_id: str  # For frontend to poll status

async def query_model(model: str, prompt: str, request_id: str = None) -> Dict:
    """Query a single model with timeout and error handling, tracking status in real-time"""
    # Grok and Claude need more time for X/Twitter search and deep reasoning
    timeout = 120.0 if "grok" in model.lower() or "claude" in model.lower() else 60.0

    start_time = time.time()

    # Update status to "querying" if request_id provided
    if request_id and request_id in query_status:
        query_status[request_id]["models"][model] = {
            "status": "querying",
            "start_time": start_time,
            "end_time": None,
            "error": None
        }

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Be concise and data-focused. Omit preambles, disclaimers, and process explanations. Start directly with key findings using bullet points. Cite sources inline (e.g., 'per ESPN') without full URLs. Target 300-500 words for simple queries, expand as needed for complex questions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,  # Safety net - models naturally stop when done
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

        end_time = time.time()

        # Update status to "completed"
        if request_id and request_id in query_status:
            query_status[request_id]["models"][model] = {
                "status": "completed",
                "start_time": start_time,
                "end_time": end_time,
                "error": None
            }

        return {
            "model": model,
            "response": response.choices[0].message.content,
            "tokens": tokens,
            "error": None
        }
    except asyncio.TimeoutError:
        end_time = time.time()
        error_msg = f"Request timed out after {timeout} seconds"

        # Update status to "timeout"
        if request_id and request_id in query_status:
            query_status[request_id]["models"][model] = {
                "status": "timeout",
                "start_time": start_time,
                "end_time": end_time,
                "error": error_msg
            }

        return {
            "model": model,
            "response": "",
            "tokens": 0,
            "error": error_msg
        }
    except Exception as e:
        end_time = time.time()
        error_msg = str(e)

        # Update status to "error"
        if request_id and request_id in query_status:
            query_status[request_id]["models"][model] = {
                "status": "error",
                "start_time": start_time,
                "end_time": end_time,
                "error": error_msg
            }

        return {
            "model": model,
            "response": "",
            "tokens": 0,
            "error": error_msg
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
        "perplexity/sonar-pro": " (native web search with citations)",
        "google/gemini-2.0-flash-001:online": " (multimodal capabilities, Google search)"
    }

    formatted_responses = ""
    for idx, resp in enumerate(responses, 1):
        model_name = resp['model']
        model_note = model_notes.get(model_name, "")

        if resp["error"]:
            formatted_responses += f"\n{idx}. **{model_name}**{model_note}: [ERROR: {resp['error']}]\n"
        else:
            formatted_responses += f"\n{idx}. **{model_name}**{model_note}:\n{resp['response']}\n"

    aggregation_prompt = f"""Synthesize these AI model responses. They already performed web searches - use only their findings.

Original Query: {query}

Model Responses:
{formatted_responses}

Output format:

## KEY CONSENSUS
2-3 bullet points max of baseline facts most models agree on. Include numbers, dates, names.

## UNIQUE INSIGHTS BY MODEL
What each model uniquely contributed (exclusive data, novel angles, sources only 1-2 models found):

**From GPT-4o (Model 1):** [List unique findings, or "No unique insights" if overlaps with others]

**From Claude (Model 2):** [List unique findings, prioritize detailed analysis and exclusive data points]

**From Perplexity (Model 3):** [List unique findings, prioritize citation quality and exclusive sources]

**From Grok (Model 4):** [List unique findings, prioritize X/Twitter posts and real-time social data]

**From Gemini (Model 5):** [List unique findings, prioritize Google search exclusives]

## WATCH FOR
**Next 24-72 Hours:**
- [Immediate developments, breaking news to monitor, upcoming announcements]
- [Specific events with dates/times]

**Next 1-4 Weeks:**
- [Short-term trends to track, upcoming decisions/votes/releases]
- [Key metrics or indicators to monitor]
- [People, organizations, or events to follow]

## SOURCES
Key sources cited above:
[1] Source name
[2] Source name

Rules: No preambles. Start with ## KEY CONSENSUS. Show model attribution to highlight each model's unique value."""

    try:
        response = await client.chat.completions.create(
            model=aggregator_model_clean,  # Use cleaned model name without :online
            messages=[{"role": "user", "content": aggregation_prompt}],
            max_tokens=5000  # Increased for comprehensive synthesis
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error during aggregation: {str(e)}"

@app.get("/api/status/{request_id}")
async def get_status(request_id: str):
    """
    Get real-time status of a query in progress
    Returns current state of all models and aggregation
    """
    if request_id not in query_status:
        raise HTTPException(status_code=404, detail="Request ID not found")

    status_data = query_status[request_id]
    current_time = time.time()

    # Build response with elapsed times
    models_status = {}
    for model, data in status_data["models"].items():
        elapsed = None
        if data["start_time"]:
            if data["end_time"]:
                elapsed = round(data["end_time"] - data["start_time"], 1)
            else:
                elapsed = round(current_time - data["start_time"], 1)

        models_status[model] = {
            "status": data["status"],
            "elapsed": elapsed,
            "error": data["error"]
        }

    return {
        "models": models_status,
        "aggregation_status": status_data["aggregation_status"]
    }

async def process_query_background(request_id: str, prompt: str, models: List[str], aggregator: str):
    """Background task to process the actual query"""
    try:
        # Query all models in parallel with request_id for status tracking
        tasks = [query_model(model, prompt, request_id) for model in models]
        raw_responses = await asyncio.gather(*tasks)

        # Filter out completely failed responses but keep partial data
        successful_responses = [r for r in raw_responses if not r["error"]]

        if not successful_responses:
            query_results[request_id] = {"error": "All model queries failed"}
            return

        # Update aggregation status to "running"
        query_status[request_id]["aggregation_status"] = "running"

        # Aggregate responses using selected aggregator model
        aggregated = await aggregate_responses(prompt, raw_responses, aggregator)

        # Update aggregation status to "completed"
        query_status[request_id]["aggregation_status"] = "completed"

        # Format individual responses
        individual = [
            {
                "model": r["model"],
                "response": r["response"] if not r["error"] else f"Error: {r['error']}",
                "tokens": r["tokens"]
            }
            for r in raw_responses
        ]

        # Store results
        query_results[request_id] = {
            "aggregated": aggregated,
            "individual": individual,
            "request_id": request_id
        }

        # Log the query
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
            "user_prompt": prompt,
            "models_used": models,
            "aggregator": aggregator,
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

    except Exception as e:
        query_results[request_id] = {"error": str(e)}

@app.post("/api/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main chat endpoint - returns request_id immediately and processes in background
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

    # Generate unique request ID for status tracking
    request_id = str(uuid.uuid4())

    # Initialize status tracking for this request
    query_status[request_id] = {
        "models": {model: {"status": "pending", "start_time": None, "end_time": None, "error": None}
                   for model in request.models},
        "aggregation_status": "pending"
    }

    # Start background processing
    background_tasks.add_task(process_query_background, request_id, request.prompt, request.models, request.aggregator)

    # Return request_id immediately so frontend can start polling
    return {"request_id": request_id}

@app.get("/api/result/{request_id}")
async def get_result(request_id: str):
    """
    Get the final result of a query (polls this until complete)
    """
    if request_id not in query_status:
        raise HTTPException(status_code=404, detail="Request ID not found")

    # Check if results are ready
    if request_id in query_results:
        result = query_results[request_id]
        # Clean up after returning (optional - could keep for caching)
        # del query_status[request_id]
        # del query_results[request_id]
        return result

    # Results not ready yet
    return {"status": "processing"}

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
