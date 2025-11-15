# Multi-Model AI Research Tool

FastAPI web application that queries multiple AI models in parallel via OpenRouter, synthesizing their responses into actionable intelligence. All models have real-time web search enabled.

## Quick Start

### Installation
1. Clone repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file with your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-[your-key-here]
   ```

3. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

4. Visit `http://localhost:8000` in your browser

## Models

### Query Models (5 parallel)
- **Claude Sonnet 4.5:online** - Best reasoning, detailed analysis
- **GPT-4o:online** - OpenAI flagship model
- **Perplexity Sonar Pro** - Native web search + citations
- **Grok 4:online** - Real-time X/Twitter access
- **Gemini 2.0 Flash:online** - Google's latest multimodal model

### Aggregator (6 options, default: Claude Sonnet 4.5)
Same as above, plus **DeepSeek Chat:online** for cost-effective synthesis

## Features

- **Parallel querying**: 5 models queried simultaneously (120s timeout)
- **Real-time web search**: All models have live web access via `:online` suffix
- **Real-time status tracking**: See each model's progress with live elapsed times
- **Structured synthesis**:
  - Key consensus points (3+ models agree)
  - Unique insights (found by only 1-2 models)
  - Contradictions identified
  - Actionable intelligence with timelines
- **Customizable**: Select models and aggregator
- **Prompt optimization**: Built-in prompt enhancement via `/api/optimize`
- **Developer logging**: Query and optimization history for analysis

## Architecture

**Backend**: FastAPI with async/await and background tasks
- Main endpoints: `POST /api/chat`, `GET /api/status/{request_id}`, `GET /api/result/{request_id}`
- Request: `{prompt, models[], aggregator}`
- Response: `{aggregated, individual[], request_id}`
- Timeout: 120s for all models (most complete in ~10 seconds)

**Frontend**: Vanilla HTML/CSS/JavaScript
- Dark theme UI
- Real-time status grid with live progress tracking
- Collapsible individual responses
- One-click prompt optimization

## Cost

**~$0.32 per request** (5 models + aggregation)
- Individual models: 4,000 max_tokens
- Aggregator: 5,000 max_tokens
- Breakdown: $10 = ~31 requests, $25 = ~78 requests

## Configuration

Token limits and timeouts configured in `main.py`:
- Individual models: 4,000 tokens
- Aggregator: 5,000 tokens
- Timeout: 120s for all models (most complete in ~10 seconds)

See `CLAUDE.md` for:
- Design decisions and rationale
- Testing results and performance analysis
- Known issues and workarounds
- Future optimization options

## Testing

Run tests from `tests/` directory:
```bash
python tests/test_models.py        # Verify model availability
python tests/test_web_search.py    # Test web search capability
python tests/test_grok.py          # Grok-specific testing
```

Developer logs stored in `logs/`:
- `query_log.json` - Full query history with responses
- `optimization_log.json` - Prompt optimization history

## Known Issues

- **Credits**: Add $5-10 to OpenRouter if seeing 402 errors ([openrouter.ai/settings/keys](https://openrouter.ai/settings/keys))
- **Log size**: `query_log.json` can grow large with heavy usage

## API Endpoints

### POST `/api/chat`
Main research endpoint - returns request_id immediately and processes in background.

**Request**:
```json
{
  "prompt": "Your research question",
  "models": ["openai/gpt-4o:online", "perplexity/sonar-pro"],
  "aggregator": "anthropic/claude-sonnet-4.5:online"
}
```

**Response**:
```json
{
  "request_id": "f9c22396-69a0-4de0-98ee-c5a0d869e518"
}
```

Then poll:
- `GET /api/status/{request_id}` - Real-time progress (300ms polling)
- `GET /api/result/{request_id}` - Final results (500ms polling)

### POST `/api/optimize`
Optimize a prompt for better research results.

**Request**:
```json
{
  "prompt": "your original prompt"
}
```

**Response**:
```json
{
  "optimized": "Enhanced prompt with structure and specificity"
}
```

## Project Structure

```
/chatbot/
├── README.md              # This file
├── CLAUDE.md              # Full development log & decisions
├── main.py                # FastAPI backend
├── requirements.txt       # Python dependencies
├── .env                   # API key (gitignored)
├── .gitignore            # Git exclusions
├── static/
│   └── index.html        # Frontend UI
├── tests/                # Test scripts
│   ├── test_models.py
│   ├── test_web_search.py
│   └── ...
└── logs/                 # Developer logs (gitignored)
    ├── query_log.json
    └── optimization_log.json
```

## Next Steps

See "Recommended Next Steps" in `CLAUDE.md`:
1. Run diverse test queries to validate performance
2. Monitor model response quality and unique value contribution
3. Consider cost optimization (3-model vs 5-model setup)
4. Evaluate adding reasoning models for complex analytical queries

---

**Last Updated**: November 15, 2025
**Full Technical Details**: See `CLAUDE.md`
