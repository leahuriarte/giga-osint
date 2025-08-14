from __future__ import annotations
from typing import Dict, Any, List

def brief_to_markdown(payload: Dict[str,Any]) -> str:
    title = f"osint brief: {payload.get('query','').strip()}"
    summary = payload.get("summary","").strip()
    sources: List[Dict[str,Any]] = payload.get("sources",[])
    ver = payload.get("verification",{})
    lines = [f"# {title}\n", summary, "\n---\n## sources"]
    for s in sources:
        stamp = f" ({s.get('published_at')})" if s.get("published_at") else ""
        lines.append(f"- [{s.get('title')}]({s.get('url')}){stamp}")
    if ver:
        lines.append("\n---\n## verification")
        lines.append(f"- overall: **{ver.get('overall_confidence','unknown')}**")
        if ver.get("notes"):
            lines.append(f"- notes: {ver['notes']}")
        if ver.get("bullets"):
            lines.append("\n### bullet checks")
            for b in ver["bullets"]:
                ok = "✅" if b.get("supported") else "⚠️"
                srcs = ",".join(str(x) for x in (b.get("support_sources") or []))
                issue = b.get("issues") or ""
                lines.append(f"- {ok} #{b.get('idx')}: sources [{srcs}] {('- ' + issue) if issue else ''}")
    return "\n".join(lines).strip() + "\n"
