from __future__ import annotations
from typing import Tuple
import re
from models.embeddings import embed_texts
import math

_SENT_SPLIT = re.compile(r"(?<=[\.\?\!])\s+")

def best_snippet(query: str, text: str, max_chars: int = 260) -> Tuple[str, int, int]:
    """
    pick the most relevant sentence (or 2) to the query via cosine in embedding space.
    returns (snippet, start_idx, end_idx) within `text`.
    """
    if not text:
        return "", 0, 0
    sents = _SENT_SPLIT.split(text)
    if not sents:
        return text[:max_chars], 0, min(len(text), max_chars)
    # embed query and sentences
    qv = embed_texts([query])[0]
    svs = embed_texts(sents)
    # cosine similarity (vectors are normalized in our embedder)
    scores = [sum(qi*si for qi,si in zip(qv, sv)) for sv in svs]
    best = max(range(len(scores)), key=lambda i: scores[i])
    # maybe include next sentence if it’s short and increases coverage
    snippet = sents[best]
    if best+1 < len(sents) and len(snippet) < max_chars//2:
        snippet = snippet + " " + sents[best+1]
    snippet = snippet[:max_chars].strip()
    # find span
    start = (text.find(snippet) if snippet else 0)
    end = start + len(snippet)
    return snippet, max(start,0), max(end,0)
