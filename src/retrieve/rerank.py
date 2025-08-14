# src/retrieve/rerank.py
from __future__ import annotations
from typing import List, Tuple
from functools import lru_cache
from config.settings import settings
from models.embeddings import embed_texts

_USE_CE = True  # can be toggled off dynamically if CE fails

@lru_cache(maxsize=1)
def _load_ce():
    from sentence_transformers import CrossEncoder  # import inside to avoid import-time failures
    # force cpu on mac; meta-tensor bug appears when device auto-detects
    return CrossEncoder(settings.cross_encoder_model, device="cpu")

def _ce_scores(query: str, texts: List[str]):
    ce = _load_ce()
    pairs = [(query, t) for t in texts]
    return ce.predict(pairs).tolist()

def _embed_scores(query: str, texts: List[str]):
    # cosine on normalized embeddings (our embedder already normalizes)
    qv = embed_texts([query])[0]
    dvs = embed_texts(texts)
    scores = []
    for dv in dvs:
      scores.append(sum(q*d for q, d in zip(qv, dv)))
    return scores

def rerank(query: str, candidates: List[Tuple[str, str, dict]]) -> List[Tuple[str, str, dict, float]]:
    """
    candidates: [(id, text, meta)]
    returns: [(id, text, meta, score)] desc
    """
    if not candidates:
        return []
    texts = [c[1] for c in candidates]
    global _USE_CE
    scores = []
    if _USE_CE:
        try:
            scores = _ce_scores(query, texts)
        except Exception as e:
            # degrade gracefully; stick a note for logs (in meta) so we can see it downstream if needed
            _USE_CE = False
            scores = _embed_scores(query, texts)
            for c in candidates:
                (c[2] or {}).update({"_rerank_fallback":"embed"})
    else:
        scores = _embed_scores(query, texts)
        for c in candidates:
            (c[2] or {}).update({"_rerank_fallback":"embed"})
    out = [(c[0], c[1], c[2], float(s)) for c, s in zip(candidates, scores)]
    out.sort(key=lambda x: x[3], reverse=True)
    return out
