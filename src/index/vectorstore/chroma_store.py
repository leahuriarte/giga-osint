import re
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import settings

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

class ChromaStore:
    """
    resilient chroma wrapper:
    - disables telemetry (chroma 0.5 is noisy)
    - versioned collection names by embedding model (prevents dim mismatches)
    - auto-heals if collection storage is corrupted (dimensionality/metadata errors)
    """
    def __init__(self, collection: Optional[str] = None):
        name = collection or f"osint_chunks_{_slug(settings.embedding_model)}"
        self.collection_name = name
        self.client = chromadb.PersistentClient(
            path=settings.chroma_dir,
            settings=ChromaSettings(
                allow_reset=True,
                anonymized_telemetry=False  # <- stop telemetry
            )
        )
        self.col = self._create_collection()

    def _create_collection(self):
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": settings.embedding_model,
                "schema": "v1",
            },
        )

    def _reset_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            # ignore if missing
            pass
        return self._create_collection()

    def upsert(
        self,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        try:
            self.col.upsert(
                ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
            )
        except Exception as e:
            # if the store is borked, reset and try once
            msg = str(e)
            if "dimensionality" in msg or "HNSW" in msg:
                self.col = self._reset_collection()
                self.col.upsert(
                    ids=ids,
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
            else:
                raise

    def query(self, query_embeddings, k: int = 5, where=None):
        kwargs = {
            "query_embeddings": query_embeddings,
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        try:
            return self.col.query(**kwargs)
        except Exception as e:
            # heal on persisted-index schema/dimensionality issues
            msg = str(e)
            if "dimensionality" in msg or "HNSW" in msg or "persist" in msg:
                self.col = self._reset_collection()
                # return empty results after repair to avoid 500s; caller can degrade gracefully
                return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            raise

    def fetch_all(self, limit: Optional[int] = None):
        try:
            return self.col.get(limit=limit, include=["documents", "metadatas"])
        except Exception as e:
            if "dimensionality" in str(e) or "persist" in str(e):
                self.col = self._reset_collection()
                return {"ids": [], "documents": [], "metadatas": []}
            raise

    def reset(self):
        # nuke everything under the client path
        self.client.reset()

# singleton (keeps the versioned collection name)
store_singleton = ChromaStore()
