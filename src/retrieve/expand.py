from __future__ import annotations
from typing import List, Dict, Any, Set
from preprocess.ner import extract_entities
from retrieve.hybrid import hybrid_search

_GENERIC = {"today","yesterday","last week","last month","security","attack","breach"}

def expand_via_entities(q: str, hits: List[Dict[str,Any]], per_entity_k: int = 3, max_entities: int = 5) -> List[Dict[str,Any]]:
    # collect candidate entities from top hits’ snippets
    ents: List[str] = []
    for h in hits:
        txt = (h.get("meta") or {}).get("snippet") or h.get("text") or ""
        ents.extend(extract_entities(txt))
    # rank by frequency
    freq = {}
    for e in ents:
        if not e or e.lower() in _GENERIC or len(e) < 3: 
            continue
        freq[e] = freq.get(e, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:max_entities]
    # spawn sub-queries and merge results
    merged: List[Dict[str,Any]] = []
    seen: Set[str] = set()
    for e,_ in ranked:
        subq = f"{q} {e}"
        subhits = hybrid_search(subq, k=per_entity_k)
        for sh in subhits:
            doc_id = (sh.get("meta") or {}).get("doc_id") or sh.get("id")
            if doc_id in seen: 
                continue
            seen.add(doc_id)
            merged.append(sh)
    return merged
