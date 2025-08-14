from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Any, Dict

class IngestRequest(BaseModel):
    urls: List[HttpUrl] = []
    rss_feeds: List[HttpUrl] = []

class IngestResult(BaseModel):
    docs: int
    chunks: int
    errors: int

class Hit(BaseModel):
    id: str
    text: str
    meta: Dict[str, Any]
    score: float

class QueryRequest(BaseModel):
    q: str
    k: int = 8
    expand: bool = False  # agentic expansion on/off
    discover: bool = False  # web discovery on/off (disabled by default)
    fast_mode: bool = True  # fast discovery mode (fewer URLs, faster)
    auto_ingest: bool = True  # auto-ingest fresh content before answering
    recent_days: int = 14  # how many days back to pull fresh content
    max_urls: int = 200  # max URLs to discover and ingest

class QueryResult(BaseModel):
    hits: List[Hit]
