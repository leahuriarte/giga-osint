from __future__ import annotations
from typing import List, Tuple
from sklearn.cluster import KMeans
import numpy as np

def choose_k(n_points: int, target_sz: int = 20, k_max: int = 60) -> int:
    if n_points <= target_sz: return 1
    k = int(round(n_points / max(5, target_sz)))
    return max(1, min(k, k_max))

def kmeans_labels(embs: List[List[float]], k: int) -> List[int]:
    X = np.array(embs, dtype=np.float32)
    km = KMeans(n_clusters=k, n_init="auto", random_state=42)
    labels = km.fit_predict(X)
    return labels.tolist()

def top_by_len(texts: List[str], max_chars: int = 2800) -> str:
    # pick sentences/chunks until cap
    out, total = [], 0
    for t in texts:
        if not t: continue
        L = len(t)
        if total + L + 1 > max_chars: break
        out.append(t); total += L + 1
    return "\n".join(out)
