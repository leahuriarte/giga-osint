from __future__ import annotations
from typing import List, Dict, Any
from models.llm import generate
from config.settings import settings

VERIFY_SYS = """
you are a fact-checking assistant for osint briefs. you will verify EACH bullet in a brief
strictly against the provided numbered sources. do not use outside knowledge.
return JSON only, no prose.
schema:
{
  "overall_confidence": "high|medium|low",
  "notes": "short caveats if any",
  "bullets": [
    {
      "idx": 1,
      "supported": true,
      "support_sources": [1,3],
      "issues": "if unsupported or partially supported, say why in <=12 words"
    }
  ]
}
rules:
- a claim is SUPPORTED if at least one cited source contains that specific info.
- if a bullet cites [n] numbers, check those first; you may also use other listed sources if needed.
- if uncertain, mark supported=false and add a short 'issues' note.
- be strict about WHO/WHAT/WHEN details; vague overlaps are not sufficient.
"""

def _sources_json_block(srcs: List[Dict[str,Any]]) -> str:
    # compact json-like lines for the model
    lines = []
    for s in srcs:
        lines.append(f'[{s["n"]}] {s.get("title","")} :: {s.get("url","")} :: {s.get("snippet","")}')
    return "\n".join(lines)

def verify_brief(text: str, srcs: List[Dict[str,Any]]) -> Dict[str,Any]:
    if not text or not srcs:
        return {"overall_confidence":"low", "notes":"no text or sources", "bullets":[]}
    prompt = f"""{VERIFY_SYS}

brief:
{text}

sources:
{_sources_json_block(srcs)}

return ONLY the JSON object per the schema."""
    out = generate(prompt)
    # best-effort parse (model returns code block sometimes)
    import json, re
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0)) if m else {"overall_confidence":"low","notes":"parse-fail","bullets":[]}
    except Exception:
        return {"overall_confidence":"low","notes":"parse-exc","bullets":[]}
