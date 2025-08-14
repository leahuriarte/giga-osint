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
    """
    Create a summary without LLM calls - use extractive approach
    Takes the most representative chunks and combines them
    """
    # Sort texts by length (longer = more informative)
    sorted_texts = sorted(texts, key=len, reverse=True)
    
    # Take top 3-5 most informative chunks
    selected_chunks = sorted_texts[:min(5, len(sorted_texts))]
    
    # Create a simple extractive summary
    summary_parts = []
    
    # Add topic context if provided
    if topic:
        summary_parts.append(f"Topic: {topic}")
    
    # Add source information
    unique_hosts = set()
    for s in sources[:8]:
        host = s.get('host', '')
        if host and host not in unique_hosts:
            unique_hosts.add(host)
    
    if unique_hosts:
        summary_parts.append(f"Sources: {', '.join(list(unique_hosts)[:5])}")
    
    # Add the most informative chunks (truncated)
    for i, chunk in enumerate(selected_chunks):
        # Truncate each chunk to ~200 chars to keep summary manageable
        truncated = chunk[:200].strip()
        if len(chunk) > 200:
            truncated += "..."
        summary_parts.append(f"[{i+1}] {truncated}")
    
    # Join with double newlines for readability
    return "\n\n".join(summary_parts)

class RaptorBuilder:
    def __init__(self, main_collection: str | None = None, node_collection: str | None = None):
        self.main = ChromaStore(collection=main_collection)   # None → versioned default
        self.nodes = ChromaStore(collection=node_collection or "osint_raptor_nodes")

    def build_nodes(self, topic_hint: str = "", min_docs: int = 50, max_docs: int = 1000, incremental: bool = False):
        """
        Build RAPTOR nodes from chunks
        
        Args:
            topic_hint: Topic context for summarization
            min_docs: Minimum documents needed for building
            max_docs: Maximum documents to process
            incremental: If True, only rebuild if significant new content exists
        """
        
        # Check if incremental update is needed
        if incremental:
            existing_nodes = self.nodes.fetch_all(limit=1000)
            existing_node_count = len(existing_nodes.get("ids", []))
            
            # Get current chunk count
            current_data = self.main.fetch_all(limit=max_docs)
            current_chunk_count = len(current_data.get("documents", []))
            
            # Only rebuild if we have significantly more content
            # Estimate: ~50 chunks per node, rebuild if 25% growth
            expected_nodes = max(1, current_chunk_count // 50)
            growth_threshold = max(5, existing_node_count * 0.25)
            
            if existing_node_count > 0 and (expected_nodes - existing_node_count) < growth_threshold:
                print(f"Incremental update skipped: {existing_node_count} nodes exist, {current_chunk_count} chunks")
                return
            
            print(f"Incremental update triggered: {existing_node_count} → ~{expected_nodes} nodes")
        
        print(f"🌳 Starting RAPTOR build (max_docs={max_docs})...")
        
        # pull everything (ok for a few hundred docs)
        print("📄 Fetching documents...")
        data = self.main.fetch_all(limit=max_docs)
        texts = data.get("documents") or []
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        
        print(f"📊 Found {len(texts)} total documents")

        # filter trash
        items = [(i,t,m) for i,(t,m) in enumerate(zip(texts, metas)) if t and len(t) > 60]
        print(f"🧹 After filtering: {len(items)} valid chunks")
        
        if len(items) < min_docs and not incremental:
            print(f"⚠️ Only {len(items)} chunks (minimum {min_docs}), continuing anyway...")

        # emb (re-embed; simpler than fetching embeddings)
        chunk_texts = [t for (_,t,_) in items]
        chunk_metas = [m for (_,_,m) in items]
        
        if not chunk_texts:
            print("❌ No valid chunks found for RAPTOR building")
            return
        
        # Limit chunks to prevent hanging
        if len(chunk_texts) > 500:
            print(f"⚡ Limiting to 500 chunks (was {len(chunk_texts)}) for performance")
            chunk_texts = chunk_texts[:500]
            chunk_metas = chunk_metas[:500]
            
        print(f"🔢 Embedding {len(chunk_texts)} chunks...")
        try:
            embs = embed_texts(chunk_texts)
            print("✅ Embeddings complete")
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            return

        # cluster
        print("🎯 Clustering chunks...")
        k = choose_k(len(chunk_texts), target_sz=24, k_max=30)  # Reduced k_max
        print(f"📊 Using k={k} clusters")
        
        try:
            labels = kmeans_labels(embs, k=k)
            print("✅ Clustering complete")
        except Exception as e:
            print(f"❌ Clustering failed: {e}")
            return

        # group by label
        print("📋 Grouping by clusters...")
        groups: Dict[int, Dict[str,Any]] = {}
        for (text, meta, lab) in zip(chunk_texts, chunk_metas, labels):
            g = groups.setdefault(lab, {"texts": [], "metas": []})
            g["texts"].append(text)
            g["metas"].append(meta)
        
        print(f"📦 Created {len(groups)} groups")

        # summarize each group to a node (no LLM calls)
        print("📝 Creating extractive summaries...")
        node_ids, node_texts, node_embs, node_metas = [], [], [], []
        
        for i, (lab, bundle) in enumerate(groups.items()):
            print(f"📄 Processing cluster {i+1}/{len(groups)} (size: {len(bundle['texts'])})")
            
            try:
                srcs = bundle["metas"]
                summary = _summarize_node(topic_hint or "osint", bundle["texts"], srcs)
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
                # Convert sources list to string for ChromaDB compatibility
                sources_str = "; ".join([f"{s.get('host', 'unknown')}:{s.get('title', 'untitled')}" for s in src_meta[:5]])
                
                node_metas.append({
                    "kind": "raptor_node",
                    "built_at": _now_iso(),
                    "k_group": int(lab),
                    "topic_hint": topic_hint,
                    "sources_summary": sources_str,
                    "source_count": len(src_meta),
                    "incremental_build": incremental
                })
                
                # Embed the summary
                node_emb = embed_texts([summary])[0]
                node_embs.append(node_emb)
                
            except Exception as e:
                print(f"⚠️ Failed to process cluster {lab}: {e}")
                continue

        if node_ids:
            # For incremental updates, replace all nodes (full rebuild is simpler and more accurate)
            if incremental:
                print(f"Rebuilding RAPTOR nodes: {len(node_ids)} new nodes")
                # Reset and rebuild (ensures consistency)
                self.nodes.reset()
                
            self.nodes.upsert(ids=node_ids, texts=node_texts, embeddings=node_embs, metadatas=node_metas)
            print(f"RAPTOR build complete: {len(node_ids)} nodes created")

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
