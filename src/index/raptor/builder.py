from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid
from config.settings import settings
from index.vectorstore.chroma_store import ChromaStore
from models.embeddings import embed_texts
from models.llm import generate
from index.raptor.utils import choose_k, kmeans_labels, top_by_len

RAPTOR_COLLECTION = "osint_raptor_nodes"

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _summarize_node(topic: str, texts: List[str], sources: List[Dict[str,Any]]) -> str:
    src_lines = "\n".join([f"- {s.get('title') or s.get('host') or s.get('url')} ({s.get('url')})" for s in sources[:8]])
    prompt = f"""
you are an osint analyst. summarize the cluster below into 4–6 crisp bullets (who/what/when/where), no fluff.
include ONE short 'why it matters' line at the end. do not fabricate; only use info in the cluster.

topic: {topic}

cluster texts (snippets):
{top_by_len(texts, max_chars=2400)}

cluster sources (subset):
{src_lines}
"""
    return generate(prompt)

class RaptorBuilder:
    def __init__(self, main_collection: str | None = None, node_collection: str | None = None):
        self.main = ChromaStore(collection=main_collection)   # None → versioned default
        self.nodes = ChromaStore(collection=node_collection or "osint_raptor_nodes")

    def build_nodes(self, topic_hint: str = "", min_docs: int = 200, max_docs: int = 2000):
        # pull everything (ok for a few hundred docs)
        data = self.main.fetch_all(limit=max_docs)
        texts = data.get("documents") or []
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []

        # filter trash
        items = [(i,t,m) for i,(t,m) in enumerate(zip(texts, metas)) if t and len(t) > 60]
        if len(items) < min_docs:
            # still allow building; just warn in caller
            pass

        # emb (re-embed; simpler than fetching embeddings)
        chunk_texts = [t for (_,t,_) in items]
        chunk_metas = [m for (_,_,m) in items]
        embs = embed_texts(chunk_texts)

        # cluster
        k = choose_k(len(chunk_texts), target_sz=24, k_max=60)
        labels = kmeans_labels(embs, k=k)

        # group by label
        groups: Dict[int, Dict[str,Any]] = {}
        for (text, meta, lab) in zip(chunk_texts, chunk_metas, labels):
            g = groups.setdefault(lab, {"texts": [], "metas": []})
            g["texts"].append(text)
            g["metas"].append(meta)

        # summarize each group to a node
        node_ids, node_texts, node_embs, node_metas = [], [], [], []
        for lab, bundle in groups.items():
            srcs = bundle["metas"]
            summary = _summarize_node(topic_hint or "security/osint", bundle["texts"], srcs)
            nid = f"node::{uuid.uuid4().hex}"
            # store: node text = summary; meta includes representative sources list
            # keep 8 sources for provenance
            src_meta = []
            for s in srcs[:8]:
                src_meta.append({
                    "url": s.get("url"),
                    "host": s.get("host"),
                    "title": s.get("title"),
                    "published_at": s.get("published_at"),
                    "doc_id": s.get("doc_id")
                })
            node_ids.append(nid)
            node_texts.append(summary)
            node_metas.append({
                "kind": "raptor_node",
                "built_at": _now_iso(),
                "k_group": int(lab),
                "topic_hint": topic_hint,
                "sources": src_meta
            })
            node_embs.append(embed_texts([summary])[0])

        if node_ids:
            self.nodes.upsert(ids=node_ids, texts=node_texts, embeddings=node_embs, metadatas=node_metas)

def query_nodes(q: str, k: int = 6, collection: str = RAPTOR_COLLECTION):
    store = ChromaStore(collection=collection)
    q_emb = embed_texts([q])
    res = store.query(query_embeddings=q_emb, k=k)
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    out = []
    for did, doc, meta in zip(ids, docs, metas):
        out.append({"id": did, "text": doc, "meta": meta})
    return out
