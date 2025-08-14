from __future__ import annotations
from typing import List, Dict, Any, Tuple
import os
from pathlib import Path
import joblib
import networkx as nx
from community import community_louvain  # python-louvain
from config.settings import settings

class GraphStore:
    def __init__(self, path: str | None = None):
        self.path = path or settings.graph_path
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            try:
                self.G: nx.Graph = joblib.load(self.path)
            except Exception:
                self.G = nx.Graph()
        else:
            self.G = nx.Graph()

    def save(self):
        joblib.dump(self.G, self.path)

    def add_chunk(self, chunk_id: str, entities: List[str], meta: Dict[str, Any] | None = None):
        meta = meta or {}
        # ensure entity nodes
        for e in entities:
            if not self.G.has_node(e):
                self.G.add_node(e, kind="entity", count=0)
            self.G.nodes[e]["count"] = int(self.G.nodes[e].get("count", 0)) + 1

        # co-mention edges
        for i in range(len(entities)):
            for j in range(i+1, len(entities)):
                a, b = sorted((entities[i], entities[j]))
                w = self.G.edges[a,b]["w"] + 1 if self.G.has_edge(a,b) else 1
                self.G.add_edge(a,b, w=w)

        # track doc node (optional), link to entities for provenance
        doc = meta.get("doc_id") or meta.get("url")
        if doc:
            dnode = f"doc::{doc}"
            if not self.G.has_node(dnode):
                self.G.add_node(dnode, kind="doc", url=meta.get("url"), host=meta.get("host"))
            for e in entities:
                self.G.add_edge(dnode, e, w=1)

    def top_entities(self, n: int = 25) -> List[Tuple[str, Dict[str, Any]]]:
        # rank by degree * log(count+1) with quality filtering
        import math
        import re
        
        # Low-quality entity patterns to filter out (only obvious junk)
        low_quality_patterns = [
            r'^(the|this|that|these|those)$',
            r'^(and|but|for|with|from)$',
            r'^(said|says|according|reported)$',
            r'^(new|old|first|last|next)$',
            r'^\d+$',  # pure numbers
            r'^[a-z]{1,2}$',  # very short all-lowercase (like "a", "an", "is")
        ]
        
        def is_quality_entity(name: str) -> bool:
            name_lower = name.lower()
            # Check against low-quality patterns
            for pattern in low_quality_patterns:
                if re.match(pattern, name_lower):
                    return False
            # Allow entities with mixed case OR all caps (proper nouns and acronyms)
            has_upper = any(c.isupper() for c in name)
            has_lower = any(c.islower() for c in name)
            if not has_upper and not name.isupper():
                return False
            # Skip very short entities unless they're all caps (acronyms) or well-known patterns
            if len(name) < 2:
                return False
            return True
        
        ents = [(n, self.G.nodes[n]) for n in self.G.nodes if self.G.nodes[n].get("kind") == "entity"]
        scored = []
        for name, data in ents:
            # Apply quality filter
            if not is_quality_entity(name):
                continue
                
            deg = self.G.degree(name)
            c = int(data.get("count", 1))
            
            # Boost score for entities that appear in multiple documents (higher degree)
            # and penalize entities that appear too frequently (likely noise)
            base_score = deg * (1.0 + math.log1p(c))
            
            # Quality multipliers
            quality_multiplier = 1.0
            
            # Boost proper nouns (mixed case)
            if any(c.isupper() for c in name) and any(c.islower() for c in name):
                quality_multiplier *= 1.2
                
            # Boost multi-word entities (likely organizations/people)
            if ' ' in name:
                quality_multiplier *= 1.3
                
            # Boost acronyms (all caps, 2-5 chars)
            if name.isupper() and 2 <= len(name) <= 5:
                quality_multiplier *= 1.5
            
            final_score = base_score * quality_multiplier
            scored.append((name, {"score": final_score, "degree": deg, "count": c}))
            
        scored.sort(key=lambda x: x[1]["score"], reverse=True)
        return scored[:n]

    def communities(self, max_comms: int = 8) -> List[Dict[str, Any]]:
        # louvain partitions on entity-only subgraph
        H = self.G.subgraph([n for n,d in self.G.nodes(data=True) if d.get("kind")=="entity"]).copy()
        if H.number_of_nodes() == 0:
            return []
        part = community_louvain.best_partition(H, weight="w", resolution=1.0)
        comm2nodes: Dict[int, List[str]] = {}
        for node, cid in part.items():
            comm2nodes.setdefault(cid, []).append(node)

        # rank communities by total degree
        comms = []
        for cid, nodes in comm2nodes.items():
            sub = H.subgraph(nodes)
            deg_sum = sum(dict(sub.degree()).values())
            # choose top representative entities
            reps = sorted(nodes, key=lambda n: sub.degree(n), reverse=True)[:6]
            comms.append({"community_id": cid, "size": len(nodes), "deg_sum": deg_sum, "representatives": reps})
        comms.sort(key=lambda c: c["deg_sum"], reverse=True)
        return comms[:max_comms]
    
    def doc_boosts(self, query_entities: list[str], k: int = 200) -> dict[str, float]:
        """
        returns {doc_id -> weight} by counting edges from doc nodes to any query entity.
        """
        if not query_entities:
            return {}
        qset = set(query_entities)
        boosts: dict[str, float] = {}
        # doc nodes start with 'doc::'
        for doc_node, data in self.G.nodes(data=True):
            if data.get("kind") != "doc":
                continue
            # neighbors that are entities intersecting qset
            hits = 0
            for nb in self.G.neighbors(doc_node):
                if self.G.nodes[nb].get("kind") == "entity" and nb in qset:
                    hits += 1
            if hits > 0:
                # smoother boost: 1 + log(hits+1)
                import math
                doc_id = doc_node.split("doc::",1)[1]
                boosts[doc_id] = 1.0 + math.log1p(hits)
        # take top k
        if len(boosts) > k:
            boosts = dict(sorted(boosts.items(), key=lambda kv: kv[1], reverse=True)[:k])
        return boosts


# singleton
graph_store = GraphStore()
