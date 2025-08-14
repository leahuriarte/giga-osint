from typing import List, Dict, Any
from datetime import datetime
from dateutil.parser import parse as dparse
from retrieve.hybrid import hybrid_search
from models.llm import generate

def _norm_date(val) -> str | None:
    if not val: return None
    try:
        dt = dparse(val)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def make_timeline(q: str, k: int = 30) -> Dict[str,Any]:
    hits = hybrid_search(q, k=k)
    if not hits:
        return {"timeline_raw": [], "timeline_text": "", "query": q}
    rows = []
    for h in hits:
        m = h.get("meta") or {}
        d = _norm_date(m.get("published_at"))
        if not d: continue
        rows.append({
            "date": d,
            "title": m.get("title") or m.get("host") or m.get("url"),
            "url": m.get("url"),
            "snippet": (h.get("text") or "")[:220]
        })
    # sort + dedupe by (date,url)
    seen = set()
    uniq = []
    for r in sorted(rows, key=lambda r: r["date"]):
        key = (r["date"], r["url"])
        if key in seen: continue
        seen.add(key); uniq.append(r)
    # optional: ask llm to tighten phrasing per row (cheap)
    bullets = "\n".join([f"{r['date']}: {r['title']} — {r['snippet']}" for r in uniq[:20]])
    improved = generate(f"condense each line to 'YYYY-MM-DD — concise event (<12 words)'.\n\n{bullets}")
    if not improved or improved.startswith("(generator_error:"):
        # fallback: simple join
        improved = "\n".join([f"{r['date']} — {r['title']}" for r in uniq[:20]])
    return {"timeline_raw": uniq[:20], "timeline_text": improved, "query": q}
