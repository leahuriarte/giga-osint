"""Knowledge base growth tracking and analytics"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from index.vectorstore.chroma_store import store_singleton as store
from index.graph.graph_store import graph_store

logger = logging.getLogger(__name__)

class KnowledgeTracker:
    """Track knowledge base growth and provide analytics"""
    
    def __init__(self, stats_file: str = ".knowledge_stats.json"):
        self.stats_file = Path(stats_file)
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict[str, Any]:
        """Load existing knowledge base statistics"""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load knowledge stats: {e}")
        
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_ingestions": 0,
            "total_documents": 0,
            "total_chunks": 0,
            "total_entities": 0,
            "ingestion_history": [],
            "entity_growth": [],
            "last_updated": None
        }
    
    def _save_stats(self):
        """Save knowledge base statistics"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge stats: {e}")
    
    def record_ingestion(self, discovery_result: Dict[str, Any]):
        """Record a new ingestion event"""
        try:
            # Get current knowledge base state
            current_stats = self.get_current_stats()
            
            # Record ingestion event
            ingestion_event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query": discovery_result.get("queries_used", ["unknown"])[0],
                "discovered_urls": discovery_result.get("discovered_urls", 0),
                "ingested_docs": discovery_result.get("ingested_docs", 0),
                "ingested_chunks": discovery_result.get("ingested_chunks", 0),
                "duration_seconds": discovery_result.get("duration_seconds", 0),
                "total_docs_after": current_stats["total_documents"],
                "total_chunks_after": current_stats["total_chunks"],
                "total_entities_after": current_stats["total_entities"]
            }
            
            # Update cumulative stats
            self.stats["total_ingestions"] += 1
            self.stats["total_documents"] = current_stats["total_documents"]
            self.stats["total_chunks"] = current_stats["total_chunks"]
            self.stats["total_entities"] = current_stats["total_entities"]
            self.stats["last_updated"] = ingestion_event["timestamp"]
            
            # Add to history (keep last 100 ingestions)
            self.stats["ingestion_history"].append(ingestion_event)
            if len(self.stats["ingestion_history"]) > 100:
                self.stats["ingestion_history"] = self.stats["ingestion_history"][-100:]
            
            # Track entity growth (sample every 10 ingestions)
            if self.stats["total_ingestions"] % 10 == 0:
                top_entities = graph_store.top_entities(n=20)
                entity_snapshot = {
                    "timestamp": ingestion_event["timestamp"],
                    "total_entities": current_stats["total_entities"],
                    "top_entities": [{"name": name, "score": meta["score"]} for name, meta in top_entities[:10]]
                }
                self.stats["entity_growth"].append(entity_snapshot)
                
                # Keep last 50 snapshots
                if len(self.stats["entity_growth"]) > 50:
                    self.stats["entity_growth"] = self.stats["entity_growth"][-50:]
            
            self._save_stats()
            
            logger.info(f"Knowledge growth recorded: +{ingestion_event['ingested_chunks']} chunks, "
                       f"total: {current_stats['total_chunks']} chunks, {current_stats['total_entities']} entities")
            
        except Exception as e:
            logger.error(f"Failed to record ingestion: {e}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current knowledge base statistics"""
        try:
            # Count documents in vector store
            all_docs = store.fetch_all(limit=10000)
            doc_urls = set()
            total_chunks = len(all_docs.get("documents", []))
            
            for meta in all_docs.get("metadatas", []):
                if meta and "url" in meta:
                    doc_urls.add(meta["url"])
            
            # Count entities in graph
            total_entities = len([n for n, d in graph_store.G.nodes(data=True) 
                                if d.get("kind") == "entity"])
            
            return {
                "total_documents": len(doc_urls),
                "total_chunks": total_chunks,
                "total_entities": total_entities,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get current stats: {e}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "total_entities": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_growth_summary(self) -> Dict[str, Any]:
        """Get a summary of knowledge base growth"""
        current = self.get_current_stats()
        
        # Calculate growth rates
        recent_ingestions = self.stats["ingestion_history"][-10:] if self.stats["ingestion_history"] else []
        
        total_recent_chunks = sum(ing.get("ingested_chunks", 0) for ing in recent_ingestions)
        avg_chunks_per_ingestion = total_recent_chunks / max(1, len(recent_ingestions))
        
        # Get top growing entities
        top_entities = graph_store.top_entities(n=10)
        
        return {
            "current_state": current,
            "total_ingestions": self.stats["total_ingestions"],
            "avg_chunks_per_ingestion": round(avg_chunks_per_ingestion, 1),
            "top_entities": [{"name": name, "score": meta["score"], "degree": meta["degree"]} 
                           for name, meta in top_entities],
            "knowledge_base_age_days": self._get_age_days(),
            "growth_velocity": self._calculate_growth_velocity()
        }
    
    def _get_age_days(self) -> float:
        """Calculate knowledge base age in days"""
        try:
            created = datetime.fromisoformat(self.stats["created_at"].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return (now - created).total_seconds() / 86400
        except:
            return 0.0
    
    def _calculate_growth_velocity(self) -> Dict[str, float]:
        """Calculate growth velocity metrics"""
        try:
            age_days = self._get_age_days()
            if age_days < 0.1:  # Less than ~2 hours
                return {"chunks_per_day": 0.0, "docs_per_day": 0.0, "entities_per_day": 0.0}
            
            return {
                "chunks_per_day": round(self.stats["total_chunks"] / age_days, 1),
                "docs_per_day": round(self.stats["total_documents"] / age_days, 1),
                "entities_per_day": round(self.stats["total_entities"] / age_days, 1)
            }
        except:
            return {"chunks_per_day": 0.0, "docs_per_day": 0.0, "entities_per_day": 0.0}

# Singleton
knowledge_tracker = KnowledgeTracker()