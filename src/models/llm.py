import google.generativeai as genai
from config.settings import settings

def _model():
    genai.configure(api_key=settings.gemini_api_key)
    # permissive (avoid oversafe blocks for cybersecurity topics)
    safety = {
        "HARASSMENT": "BLOCK_NONE",
        "HATE_SPEECH": "BLOCK_NONE",
        "SEXUAL": "BLOCK_NONE",
        "DANGEROUS": "BLOCK_NONE",
    }
    try:
        return genai.GenerativeModel(settings.gemini_model, safety_settings=safety)
    except TypeError:
        # older client versions: no safety_settings kw
        return genai.GenerativeModel(settings.gemini_model)

def generate(markdown_prompt: str) -> str:
    try:
        m = _model()
        r = m.generate_content(markdown_prompt)
        # prefer .text; fallback to candidates
        txt = getattr(r, "text", "") or ""
        if not txt and getattr(r, "candidates", None):
            parts = []
            for c in r.candidates:
                for p in getattr(c.content, "parts", []) or []:
                    val = getattr(p, "text", None) or getattr(p, "raw_text", None)
                    if val:
                        parts.append(val)
            txt = "\n".join(parts).strip()
        return (txt or "").strip()
    except Exception as e:
        # last ditch: return the error so caller can degrade gracefully
        return f"(generator_error: {e})"
