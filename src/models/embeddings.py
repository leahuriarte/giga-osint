from typing import List
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from config.settings import settings

@lru_cache(maxsize=1)
def _load_model():
    return SentenceTransformer(settings.embedding_model)

def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    if not texts:
        return []
    model = _load_model()
    embs = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,   # <-- key change
        show_progress_bar=False,
    )
    return embs.tolist()
