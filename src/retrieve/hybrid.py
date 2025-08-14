from typing import Dict, Any, List, Tuple
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store
from retrieve.bm25 import BM25Index
from retrieve.rerank import rerank
from retrieve.temporal import temporal_weight
from retrieve.snippets import best_snippet
from preprocess.ner import extract_entities
from index.graph.graph_store import graph_store
from config.settings import settings

def _vector_candidates(q: str, k: int = 40) -> Dict[str, Dict[str, Any]]:
    q_emb = embed_texts([q])
    res = store.query(query_embeddings=q_emb, k=k)
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    out: Dict[str, Dict[str, Any]] = {}
    for did, doc, meta in zip(ids, docs, metas):
        out[did] = {"text": doc or "", "meta": meta or {}, "score_v": 1.0, "score_b": 0.0, "score_g": 0.0}
    return out

def _bm25_candidates(q: str, k: int = 200) -> List[Tuple[str, str, Dict[str, Any]]]:
    all_docs = store.fetch_all()
    docs = all_docs.get("documents") or []
    ids  = all_docs.get("ids") or []
    metas= all_docs.get("metadatas") or [{} for _ in ids]
    if not docs:
        return []
    bm = BM25Index(docs)
    idxs = bm.query(q, k=min(k, len(docs)))
    return [(ids[i], docs[i] or "", metas[i] or {}) for i in idxs]

def hybrid_search(q: str, k: int = 10) -> List[Dict[str, Any]]:
    # union candidates
    vec = _vector_candidates(q, k=60)
    for did, doc, meta in _bm25_candidates(q, k=200):
        if did in vec:
            vec[did]["score_b"] += 1.0
        else:
            vec[did] = {"text": doc, "meta": meta, "score_v": 0.0, "score_b": 1.0, "score_g": 0.0}

    # graph bias based on query entities
    if settings.use_graph_bias:
        ents = extract_entities(q) or []
        boosts = graph_store.doc_boosts(ents, k=300)
        for did, data in list(vec.items()):
            doc_id = data["meta"].get("doc_id")
            if doc_id and doc_id in boosts:
                data["score_g"] = data.get("score_g", 0.0) + boosts[doc_id]

    # prelim rank → take top N for rerank
    prelim = sorted(
        vec.items(),
        key=lambda kv: (kv[1]["score_v"] + kv[1]["score_b"] + 0.8*kv[1]["score_g"]),
        reverse=True
    )[:80]

    # reshape for reranker + temporal
    cands: List[Tuple[str, str, dict]] = []
    for did, data in prelim:
        meta = data["meta"] or {}
        meta["_temp_w"] = temporal_weight(meta, q, default_days=settings.default_recent_days)
        meta["_graph_w"] = 1.0 + min(1.0, data.get("score_g", 0.0))  # mild multiplier
        cands.append((did, data["text"], meta))

    ranked = rerank(q, cands)

    # combine rerank score with temporal + graph weights
    final = sorted(
        ranked,
        key=lambda tup: tup[3] * (tup[2].get("_temp_w", 1.0)) * (tup[2].get("_graph_w", 1.0)),
        reverse=True
    )[:k]

    hits: List[Dict[str, Any]] = []
    for did, text, meta, score in final:
        # compute snippet/span for citations
        snip, s, e = best_snippet(q, text)
        meta["snippet"] = snip
        meta["snippet_start"] = s
        meta["snippet_end"] = e
        meta.pop("_temp_w", None)
        meta.pop("_graph_w", None)
        hits.append({
            "id": did,
            "text": text,
            "meta": meta,
            "score": float(score)
        })
    return hits
