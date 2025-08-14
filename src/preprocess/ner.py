from typing import List, Tuple
import re

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None

# which labels we care about for osint graphs
_ALLOWED = {"PERSON","ORG","GPE","LOC","EVENT","PRODUCT","NORP","FAC","LAW","WORK_OF_ART"}

_ws = re.compile(r"\s+")

def normalize_ent(t: str) -> str:
    t = t.strip().strip('"\'')

    # collapse whitespace, lowercase but keep acronyms
    t = _ws.sub(" ", t)
    if len(t) <= 4 and t.isupper():
        return t  # keep acronyms like FBI, NSA
    return t.lower()

def extract_entities(text: str) -> List[str]:
    if not text:
        return []
    if _nlp is None:
        # naive fallback: capitalized tokens that look like orgs/people (crude)
        import re
        cands = re.findall(r"\b([A-Z][A-Za-z0-9\-]{2,}(?:\s+[A-Z][A-Za-z0-9\-]{1,}){0,3})\b", text)
        ents = [normalize_ent(c) for c in cands]
        return list({e for e in ents if len(e) >= 3})
    doc = _nlp(text)
    ents = [normalize_ent(e.text) for e in doc.ents if e.label_ in _ALLOWED]
    # dedup but keep short list
    uniq = []
    seen = set()
    for e in ents:
        if e not in seen:
            uniq.append(e); seen.add(e)
    return uniq

def co_mentions(ents: List[str], max_pairs: int = 15) -> List[Tuple[str, str]]:
    ents = [e for e in ents if e]
    pairs = []
    for i in range(len(ents)):
        for j in range(i+1, len(ents)):
            if ents[i] == ents[j]:
                continue
            a,b = sorted((ents[i], ents[j]))
            pairs.append((a,b))
            if len(pairs) >= max_pairs:
                return pairs
    return pairs
