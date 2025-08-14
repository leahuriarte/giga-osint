from typing import List, Tuple
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None

def _sentences(text: str) -> List[str]:
    if _nlp:
        return [s.text.strip() for s in _nlp(text).sents if s.text.strip()]
    # fallback: naive split
    import re
    return [s.strip() for s in re.split(r"(?<=[\.\?\!])\s+", text) if s.strip()]

def sentence_windows(text: str, win: int = 6, overlap: int = 2, max_chars: int = 1600) -> List[str]:
    sents = _sentences(text)
    chunks = []
    i = 0
    while i < len(sents):
        chunk = " ".join(sents[i:i+win])
        # cap insanely long chunks
        chunk = chunk[:max_chars]
        if chunk:
            chunks.append(chunk)
        i += max(1, win - overlap)
    return chunks

def chunk_with_meta(doc_id: str, text: str) -> List[Tuple[str, str, int]]:
    chunks = sentence_windows(text)
    out = []
    for idx, ch in enumerate(chunks):
        chunk_id = f"{doc_id}::c{idx:04d}"
        out.append((chunk_id, ch, idx))
    return out
