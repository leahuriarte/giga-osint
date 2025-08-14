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

# Only filter out obvious filler words and common false positives
_STOPWORDS = {
    # Basic stopwords that commonly get picked up as entities
    "the", "this", "that", "these", "those", "and", "but", "for", "with", "from", "into", "during", "before", "after", "above", "below", "between", "through",
    # Common sentence starters/connectors
    "said", "says", "according", "reported", "sources", "officials", 
    # Generic descriptors
    "new", "old", "first", "last", "next", "previous", "recent", "latest", "current", "former", "major", "minor", "large", "small", "big", "little",
    # Time words (keep specific dates/months as they can be entities)
    "today", "yesterday", "tomorrow", "week", "month", "year", "time", "times", "day", "days", "hours", "minutes", "seconds",
    # Generic content words
    "news", "report", "reports", "article", "articles", "story", "stories", "post", "posts", "update", "updates", "information", "data", "details",
    # Very generic people terms
    "users", "user", "customers", "customer", "clients", "client", "people", "person", "individuals", "individual"
}

def extract_entities(text: str) -> List[str]:
    if not text:
        return []
    if _nlp is None:
        # naive fallback: capitalized tokens that look like orgs/people (crude)
        import re
        cands = re.findall(r"\b([A-Z][A-Za-z0-9\-]{2,}(?:\s+[A-Z][A-Za-z0-9\-]{1,}){0,3})\b", text)
        ents = []
        for c in cands:
            normalized = normalize_ent(c)
            # Filter out obvious stopwords and very short entities
            if len(normalized) >= 2 and normalized.lower() not in _STOPWORDS:
                # Skip if it looks like a sentence fragment (starts with common words)
                if not any(normalized.lower().startswith(starter) for starter in ["the ", "this ", "that ", "these ", "those ", "and ", "but "]):
                    ents.append(normalized)
        return list(set(ents))  # dedup
    
    doc = _nlp(text)
    ents = []
    for e in doc.ents:
        if e.label_ in _ALLOWED:
            normalized = normalize_ent(e.text)
            # Apply filtering to spacy entities (trust spacy more, so lighter filtering)
            if len(normalized) >= 2 and normalized.lower() not in _STOPWORDS:
                ents.append(normalized)
    
    # dedup but keep order
    uniq = []
    seen = set()
    for e in ents:
        if e not in seen:
            uniq.append(e)
            seen.add(e)
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
