from typing import List, Dict, Any
from retrieve.hybrid import hybrid_search
from models.llm import generate
from index.raptor.builder import query_nodes
from retrieve.expand import expand_via_entities


SYS_GUIDE = """
you are an osint brief-writer. write concise bullets with *grounded* citations.
rules:
- cite sources with bracketed numbers like [1], [2] that refer to the provided sources list.
- never invent sources; only cite from the provided list.
- be specific (who/what/when/where). prefer recent info.
- include a micro-timeline if relevant (dated bullets).
- keep to 6-8 bullets max.
"""

def build_sources(hits: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    srcs = []
    for i,h in enumerate(hits, start=1):
        m = h.get("meta") or {}
        snippet = m.get("snippet") or (h.get("text") or "")[:260]
        srcs.append({
            "n": i,
            "url": m.get("url"),
            "title": (m.get("title") or m.get("host") or m.get("url") or "")[:180],
            "host": m.get("host"),
            "published_at": m.get("published_at"),
            "snippet": snippet
        })
    return srcs

def sources_block(srcs: List[Dict[str,Any]]) -> str:
    lines = []
    for s in srcs:
        stamp = f" · {s['published_at']}" if s.get("published_at") else ""
        title = s["title"] or s["host"] or s["url"]
        lines.append(f"[{s['n']}] {title}{stamp}\n{ s['url'] }")
    return "\n".join(lines)

def _flatten_raptor_nodes(nodes: List[Dict[str,Any]], take_sources: int = 1) -> List[Dict[str,Any]]:
    # turn raptor nodes into pseudo-hits by pointing to their 1st underlying source
    flat = []
    for n in nodes:
        meta = n.get("meta") or {}
        srcs = meta.get("sources") or []
        url = (srcs[0]["url"] if srcs else None)
        host = (srcs[0]["host"] if srcs else None)
        title = (srcs[0]["title"] if srcs else "raptor node")
        flat.append({
            "id": n["id"],
            "text": n["text"],
            "meta": {
                "url": url,
                "host": host,
                "title": f"{title} (summary node)",
                "published_at": (srcs[0].get("published_at") if srcs else None)
            }
        })
    return flat


def make_brief(q: str, k: int = 12, expand: bool = False) -> Dict[str,Any]:
    nodes = query_nodes(q, k=max(4, k // 2))
    raw   = hybrid_search(q, k=max(6, k // 2))

    expanded = expand_via_entities(q, raw, per_entity_k=2, max_entities=5) if expand else []

    # dedup by doc_id, preserve order: nodes -> raw -> expanded
    def _docid(h):
        m = h.get("meta") or {}
        return m.get("doc_id") or h.get("id")
    seen = set()
    mixed = []
    for h in ( _flatten_raptor_nodes(nodes) + raw + expanded ):
        did = _docid(h)
        if did in seen: 
            continue
        seen.add(did)
        mixed.append(h)
    if not mixed:
        return {"summary":"no evidence found.", "sources": [], "query": q}

    mixed = mixed[:k]
    srcs = build_sources(mixed)
    prompt = f"""{SYS_GUIDE}

topic: {q}

sources (numbered):
{sources_block(srcs)}

write the brief now. use [n] citations inline that map to the sources above. end with a one-line 'assessment' about confidence."""
    txt = generate(prompt)

    if not txt or txt.startswith("(generator_error:"):
        # extractive fallback: list top sources with snippets (still useful)
        bullets = []
        for i,s in enumerate(srcs[:8], start=1):
            stamp = f" — {s.get('published_at')}" if s.get("published_at") else ""
            bullets.append(f"* [{i}] {s.get('title')}{stamp}: {s.get('snippet')}")
        bullets.append("\nassessment: LOW confidence (extractive fallback).")
        txt = "\n".join(bullets)
    return {"summary": txt, "sources": srcs, "query": q}

