# Agent-on-Query Feature

## Overview

The agent-on-query feature enables automatic content discovery and ingestion when users ask questions like "what's up with X?". Instead of relying on existing corpus data, the system proactively:

1. **Expands seeds** - Derives entities and relevant RSS feeds from the query
2. **Ingests fresh content** - Pulls recent items and ingests them into the knowledge base  
3. **Rebuilds summaries** - Triggers bounded RAPTOR rebuild if significant new content is found
4. **Answers with fresh data** - Provides briefings using the updated corpus

## API Changes

### Extended Request Schema

The `/api/brief` endpoint now accepts these additional parameters:

```json
{
  "q": "What's up with university data breaches?",
  "k": 8,
  "expand": false,
  "auto_ingest": true,     // NEW: Enable auto-ingest (default: true)
  "recent_days": 14,       // NEW: How many days back to search (default: 14)
  "max_urls": 200          // NEW: Max URLs to discover and ingest (default: 200)
}
```

### Response Structure

When `auto_ingest=true`, the response includes a `corpus_update` field:

```json
{
  "summary": "Brief content...",
  "sources": [...],
  "verification": {...},
  "corpus_update": {
    "seeds": {
      "entities": ["University of X", "Data Breach"],
      "feeds": ["https://...", "https://..."]
    },
    "fresh_items_found": 25,
    "ingested": {
      "docs": 12,
      "chunks": 48
    },
    "raptor_rebuilt": true,
    "query": "What's up with university data breaches?"
  }
}
```

## How It Works

### 1. Seed Derivation

The planner analyzes the query to derive:
- **Entities**: Extracted using NER (Named Entity Recognition)
- **RSS Feeds**: Selected based on query keywords (security, university, healthcare, etc.)

Example for "university data breach":
- Entities: ["University", "Data Breach"] 
- Feeds: Education RSS feeds + Security RSS feeds + General news

### 2. Fresh Content Discovery

The system pulls recent content from:
- **RSS Feeds**: Topic-relevant feeds based on query analysis
- **Web Search**: Entity-based searches using available APIs (Exa, SerpAPI)
- **Recency Filter**: Only items from the last N days (configurable)

### 3. Intelligent Ingestion

Fresh items are:
- Fetched as full articles when possible (HTML extraction)
- Fallback to RSS summaries if extraction fails
- Cleaned, chunked, and embedded
- Stored in vector database with metadata
- Added to knowledge graph with entity relationships

### 4. Bounded RAPTOR Rebuild

RAPTOR summaries are rebuilt when:
- Fresh docs >= 10 documents, OR
- Last build was > 6 hours ago

The rebuild is incremental and bounded to prevent performance issues.

## Usage Examples

### Basic Auto-Ingest Query
```bash
curl -X POST http://localhost:8000/api/brief \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What'\''s up with hospital ransomware attacks?",
    "auto_ingest": true,
    "recent_days": 7,
    "max_urls": 50
  }'
```

### Disable Auto-Ingest (Legacy Mode)
```bash
curl -X POST http://localhost:8000/api/brief \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What'\''s up with hospital ransomware attacks?",
    "auto_ingest": false,
    "discover": true
  }'
```

## Configuration

### Environment Variables

The feature uses existing configuration:
- `EXA_API_KEY`: For high-quality web search
- `SERPAPI_API_KEY`: Fallback web search  
- `DEFAULT_RECENT_DAYS`: Default lookback period

### RSS Feed Selection

The system automatically selects relevant RSS feeds based on query content:

- **Security/Cyber**: Krebs, BleepingComputer, Dark Reading, etc.
- **Education**: Inside Higher Ed, Chronicle, Education Dive, etc.  
- **Healthcare**: Healthcare InfoSecurity, Modern Healthcare, etc.
- **Finance**: Bank InfoSecurity, American Banker, etc.
- **General**: Google News, Reuters, CNN, etc.

## Performance Considerations

### Bounded Operations
- Max URLs: Configurable limit (default: 200)
- Max entities: Limited to top 5 from query
- Max RSS feeds: Automatically selected, typically 10-15
- Incremental RAPTOR: Only rebuilds when needed

### Fallback Behavior
- If web search fails → Falls back to RSS only
- If RSS fails → Uses existing corpus
- If ingestion fails → Continues with current data
- If RAPTOR rebuild fails → Uses existing summaries

## Testing

### Run Demo Script
```bash
python demo_agent_query.py
```

### Test Individual Components
```bash
python test_agent_query.py
```

### Manual API Testing
```bash
# Start server
python -m uvicorn app.main:app --reload --port 8000

# Test with curl
curl -X POST http://localhost:8000/api/brief \
  -H "Content-Type: application/json" \
  -d '{"q": "university data breach", "auto_ingest": true}'
```

## Implementation Details

### Key Files
- `src/synth/planner.py`: Main planner logic
- `src/app/schemas.py`: Extended request schema  
- `src/app/api.py`: Updated brief endpoint
- `src/discover/websearch.py`: Web search integration
- `src/ingest/rss.py`: RSS feed processing

### Minimal Code Addition
This feature adds ~200 lines of code while reusing existing infrastructure:
- Vector store (ChromaDB)
- Embedding pipeline
- RAPTOR summarization
- Entity extraction
- Web search capabilities

The implementation keeps your existing stack with no new infrastructure requirements.