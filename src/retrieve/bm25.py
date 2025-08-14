from typing import List
from rank_bm25 import BM25Okapi
import re

_token = re.compile(r"[A-Za-z0-9_]+")

def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _token.findall(text)]

class BM25Index:
    def __init__(self, docs: List[str]):
        self.tokens = [tokenize(d) for d in docs]
        self.bm25 = BM25Okapi(self.tokens)

    def query(self, q: str, k: int = 10) -> List[int]:
        toks = tokenize(q)
        scores = self.bm25.get_scores(toks)
        # return indices sorted by score desc
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
