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

class QueryResult(BaseModel):
    hits: List[Hit]
