"""Discovery orchestrator - coordinates web search, filtering, and ingestion"""

import asyncio
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from .websearch import web_searcher
from .expand import expand_discovery_queries
from .filters import filter_discovered_urls, dedupe_by_content_similarity, get_existing_urls_from_store
from .knowledge_tracker import knowledge_tracker
from ingest.html_fetch import fetch_article
from preprocess.clean import clean_text, is_trash
from preprocess.chunk import chunk_with_meta
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store
from preprocess.ner import extract_entities
from index.graph.graph_store import graph_store

logger = logging.getLogger(__name__)

class DiscoveryOrchestrator:
    def __init__(self, 
                 max_urls_per_query: int = 5,  # Reduced from 8
                 max_total_urls: int = 15,     # Reduced from 40
                 fetch_timeout: int = 20,      # Reduced from 60
                 max_concurrent_fetches: int = 3):  # Reduced from 5
        self.max_urls_per_query = max_urls_per_query
        self.max_total_urls = max_total_urls
        self.fetch_timeout = fetch_timeout
        self.max_concurrent_fetches = max_concurrent_fetches
    
    async def discover_and_ingest(self, query: str, expand_queries: bool = True, fast_mode: bool = True) -> Dict[str, Any]:
        """
        Main discovery flow:
        1. Generate subqueries (if enabled)
        2. Search for URLs
        3. Filter and dedupe
        4. Fetch and extract content
        5. Ingest into vector store and graph
        
        Returns summary of discovery results
        """
        start_time = datetime.now()
        
        # Step 1: Generate queries (adjust for fast mode)
        if fast_mode:
            # Fast mode: single query only
            queries = [query]
            max_urls = min(self.max_total_urls, 8)
        else:
            # Full mode: expand queries
            if expand_queries:
                queries = expand_discovery_queries(query, max_total_queries=3)
            else:
                queries = [query]
            max_urls = self.max_total_urls
        
        logger.info(f"🔍 Discovering content for {len(queries)} queries (fast_mode={fast_mode})")
        
        # Step 2: Concurrent web search
        all_discovered = []
        search_tasks = []
        
        for q in queries:
            task = web_searcher.discover(q, max_results=self.max_urls_per_query)
            search_tasks.append(task)
        
        try:
            search_results = await asyncio.wait_for(
                asyncio.gather(*search_tasks, return_exceptions=True),
                timeout=15.0  # Reduced from 30s
            )
            
            successful_searches = 0
            for i, result in enumerate(search_results):
                if isinstance(result, Exception):
                    logger.error(f"Search task {i+1} failed: {result}")
                    continue
                if result:  # Not empty
                    all_discovered.extend(result)
                    successful_searches += 1
                    
            logger.info(f"Completed {successful_searches}/{len(search_tasks)} search tasks")
                
        except asyncio.TimeoutError:
            logger.warning("Search timeout, proceeding with partial results")
        
        logger.info(f"📡 Found {len(all_discovered)} total URLs from search")
        
        # Step 3: Filter and dedupe
        existing_urls = get_existing_urls_from_store()
        filtered_urls = filter_discovered_urls(
            all_discovered, 
            existing_urls=existing_urls,
            max_per_domain=3
        )
        
        # Skip content similarity deduplication for speed (URL dedup is enough)
        # filtered_urls = dedupe_by_content_similarity(filtered_urls)
        
        # Limit total URLs based on mode
        filtered_urls = filtered_urls[:max_urls]
        
        if not filtered_urls:
            logger.warning("No URLs passed filtering")
            return {
                "discovered_urls": 0,
                "ingested_docs": 0,
                "ingested_chunks": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "errors": ["No URLs passed filtering"]
            }
        
        logger.info(f"✅ Proceeding with {len(filtered_urls)} filtered URLs")
        
        # Step 4: Concurrent fetch and extract
        fetch_tasks = []
        semaphore = asyncio.Semaphore(self.max_concurrent_fetches)
        
        for url_info in filtered_urls:
            task = self._fetch_with_semaphore(semaphore, url_info)
            fetch_tasks.append(task)
        
        try:
            fetch_results = await asyncio.wait_for(
                asyncio.gather(*fetch_tasks, return_exceptions=True),
                timeout=self.fetch_timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Fetch timeout, proceeding with partial results")
            fetch_results = []
        
        # Step 5: Process successful fetches
        successful_docs = []
        for result in fetch_results:
            if isinstance(result, Exception):
                logger.error(f"Fetch task failed: {result}")
                continue
            if result:  # Not None
                successful_docs.append(result)
        
        logger.info(f"📄 Successfully fetched {len(successful_docs)} documents")
        
        # Step 6: Ingest into vector store and graph
        ingested_chunks = 0
        errors = []
        
        for doc in successful_docs:
            try:
                chunks_added = await self._ingest_document(doc)
                ingested_chunks += chunks_added
            except Exception as e:
                logger.error(f"Failed to ingest {doc.get('url', 'unknown')}: {e}")
                errors.append(str(e))
        
        # Save graph updates and trigger knowledge expansion
        if ingested_chunks > 0:
            try:
                graph_store.save()
                logger.info(f"Graph updated with {ingested_chunks} new chunks")
                
                # Trigger incremental RAPTOR rebuild if significant new content
                if ingested_chunks >= 20:  # Threshold for RAPTOR update
                    try:
                        await self._trigger_incremental_raptor_update()
                    except Exception as e:
                        logger.warning(f"RAPTOR incremental update failed: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to save graph: {e}")
                errors.append(f"Graph save failed: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "discovered_urls": len(all_discovered),
            "filtered_urls": len(filtered_urls),
            "ingested_docs": len(successful_docs),
            "ingested_chunks": ingested_chunks,
            "duration_seconds": duration,
            "errors": errors,
            "queries_used": queries,
            "knowledge_growth": {
                "new_chunks": ingested_chunks,
                "total_docs_estimate": len(get_existing_urls_from_store()) if ingested_chunks > 0 else None
            }
        }
        
        # Record knowledge growth
        if ingested_chunks > 0:
            try:
                knowledge_tracker.record_ingestion(result)
            except Exception as e:
                logger.warning(f"Failed to record knowledge growth: {e}")
        
        logger.info(f"Discovery completed: {result}")
        return result
    
    async def _fetch_with_semaphore(self, semaphore: asyncio.Semaphore, url_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch a single URL with concurrency control and timeout"""
        async with semaphore:
            try:
                url = url_info["url"]
                logger.debug(f"🌐 Fetching {url[:60]}...")
                
                # Use existing fetch_article function with individual timeout
                article = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, fetch_article, url),
                    timeout=10.0  # 10s per URL max
                )
                
                if not article:
                    logger.debug(f"❌ No content from {url[:40]}...")
                    return None
                
                # Clean and validate
                clean_content = clean_text(article["text"])
                if is_trash(clean_content):
                    logger.debug(f"🗑️ Trash content from {url[:40]}...")
                    return None
                
                logger.debug(f"✅ Fetched {len(clean_content)} chars from {url[:40]}...")
                
                return {
                    "doc_id": url,
                    "url": article["url"],
                    "host": article["host"],
                    "title": url_info.get("title", ""),
                    "text": clean_content,
                    "published_at": None,  # Could extract from page if needed
                    "source": f"discovery_{url_info.get('source', 'unknown')}"
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout fetching {url_info.get('url', 'unknown')[:40]}...")
                return None
            except Exception as e:
                logger.warning(f"❌ Failed to fetch {url_info.get('url', 'unknown')[:40]}...: {str(e)[:50]}")
                return None
    
    async def _ingest_document(self, doc: Dict[str, Any]) -> int:
        """Ingest a single document into vector store and graph"""
        
        # Chunk the document
        chunks = chunk_with_meta(doc["doc_id"], doc["text"])
        if not chunks:
            return 0
        
        # Prepare for vector store
        ids = []
        texts = []
        metas = []
        
        for cid, ch, idx in chunks:
            ids.append(cid)
            texts.append(ch)
            # Clean metadata - ChromaDB doesn't accept None values
            meta = {
                "url": doc["url"],
                "host": doc["host"],
                "doc_id": doc["doc_id"],
                "title": doc.get("title", ""),
                "chunk_index": idx,
                "source": doc.get("source", "discovery")
            }
            
            # Only add published_at if it's not None
            if doc.get("published_at"):
                meta["published_at"] = doc["published_at"]
            
            metas.append(meta)
        
        # Embed and upsert
        embeddings = embed_texts(texts)
        store.upsert(ids=ids, texts=texts, embeddings=embeddings, metadatas=metas)
        
        # Update graph with entities
        for cid, ch, idx in chunks:
            entities = extract_entities(ch)
            if entities:
                graph_store.add_chunk(
                    chunk_id=cid,
                    entities=entities,
                    meta={
                        "url": doc["url"],
                        "host": doc["host"],
                        "doc_id": doc["doc_id"]
                    }
                )
        
        return len(chunks)
    
    async def _trigger_incremental_raptor_update(self):
        """Trigger incremental RAPTOR node building for new content"""
        try:
            from index.raptor.builder import RaptorBuilder
            
            logger.info("Triggering incremental RAPTOR update...")
            builder = RaptorBuilder()
            
            # Run RAPTOR building in executor to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: builder.build_nodes(topic_hint="osint_discovery", incremental=True)
            )
            
            logger.info("Incremental RAPTOR update completed")
            
        except Exception as e:
            logger.error(f"Incremental RAPTOR update failed: {e}")
            raise

# Singleton
discovery_orchestrator = DiscoveryOrchestrator()