# Agent-on-Query Usage Example

## Before: Static Corpus Query

Previously, when a user asked "what's up with university data breaches?", the system would only search existing corpus data:

```bash
curl -X POST http://localhost:8000/api/brief \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What'\''s up with university data breaches?",
    "k": 8,
    "expand": false
  }'
```

**Response**: Limited to whatever was already in the knowledge base, potentially missing recent incidents.

## After: Agent-on-Query with Auto-Ingest

Now the same query triggers automatic content discovery and ingestion:

```bash
curl -X POST http://localhost:8000/api/brief \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What'\''s up with university data breaches?",
    "k": 8,
    "auto_ingest": true,
    "recent_days": 14,
    "max_urls": 100
  }'
```

**What happens automatically:**

1. **Seed Expansion**: System derives entities ("university", "data breach") and selects relevant RSS feeds (education + security sources)

2. **Fresh Content Discovery**: Pulls recent items from:
   - Inside Higher Ed, Chronicle of Higher Education (education feeds)
   - Krebs on Security, BleepingComputer (security feeds)  
   - Google News searches for "university data breach"
   - Web search for entity combinations

3. **Auto-Ingest**: Fetches full articles, cleans/chunks content, embeds and stores in vector DB

4. **Smart RAPTOR Rebuild**: If significant new content (>10 docs), rebuilds summary nodes

5. **Fresh Brief**: Generates brief using updated corpus with recent incidents

**Enhanced Response:**
```json
{
  "summary": "Recent university data breaches include...",
  "sources": [
    {
      "n": 1,
      "url": "https://www.insidehighered.com/news/2024/01/15/university-x-breach",
      "title": "University X Reports Major Data Breach",
      "published_at": "2024-01-15T10:30:00"
    }
  ],
  "corpus_update": {
    "seeds": {
      "entities": ["University", "Data Breach"],
      "feeds": ["https://www.insidehighered.com/rss.xml", "..."]
    },
    "fresh_items_found": 25,
    "ingested": {
      "docs": 12,
      "chunks": 48
    },
    "raptor_rebuilt": true
  }
}
```

## Key Benefits

### 1. Always Fresh Intelligence
- No more stale briefings on breaking incidents
- Automatic discovery of latest developments
- Real-time corpus updates

### 2. Intelligent Source Selection  
- Query-aware RSS feed selection
- Entity-driven web searches
- Comprehensive coverage across domains

### 3. Minimal Latency Impact
- Bounded operations (max URLs, recent days)
- Incremental RAPTOR rebuilds only when needed
- Fallback to existing corpus if discovery fails

### 4. Zero Infrastructure Changes
- Uses existing vector store, embeddings, LLM
- No new services or databases required
- Backward compatible with existing queries

## Configuration Examples

### High-Frequency Monitoring
For breaking news scenarios:
```json
{
  "q": "latest ransomware attacks",
  "auto_ingest": true,
  "recent_days": 3,
  "max_urls": 50
}
```

### Deep Investigation  
For comprehensive research:
```json
{
  "q": "healthcare cybersecurity incidents 2024",
  "auto_ingest": true,
  "recent_days": 30,
  "max_urls": 300,
  "expand": true
}
```

### Legacy Mode
Disable auto-ingest for existing workflows:
```json
{
  "q": "historical analysis of data breaches",
  "auto_ingest": false,
  "expand": true
}
```

## Performance Characteristics

- **Discovery**: 2-5 seconds for RSS + web search
- **Ingestion**: ~1 second per 10 articles  
- **RAPTOR Rebuild**: 10-30 seconds (only when needed)
- **Total Overhead**: 5-45 seconds depending on fresh content volume

The system is designed to provide fresh intelligence while maintaining reasonable response times for interactive use.