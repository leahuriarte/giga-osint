"""Simple RSS-based discovery for fresh content"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Curated RSS feeds for breaking security news
BREAKING_NEWS_FEEDS = [
    # Google News for breaking stories
    "https://news.google.com/rss/search?q=data+breach&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=cyber+attack&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=ransomware&hl=en-US&gl=US&ceid=US:en",
    
    # Primary security sources
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
    "https://threatpost.com/feed/",
    "https://www.securityweek.com/feed",
    
    # Tech news with security coverage
    "https://arstechnica.com/security/feed/",
    "https://techcrunch.com/category/security/feed/",
    
    # Government/official sources
    "https://www.cisa.gov/news.xml",
]

async def discover_breaking_news(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Discover breaking news via RSS feeds
    Much faster and more reliable than web search APIs
    """
    try:
        from ingest.rss import pull_rss
        
        logger.info(f"📡 Searching RSS feeds for: {query}")
        
        # Pull recent RSS items
        items = pull_rss(BREAKING_NEWS_FEEDS)
        logger.info(f"Found {len(items)} total RSS items")
        
        if not items:
            return []
        
        # Simple keyword matching for relevance
        query_words = set(query.lower().split())
        relevant_items = []
        
        for item in items:
            title = item.get("title", "").lower()
            summary = item.get("summary", "").lower()
            text = f"{title} {summary}"
            
            # Score by keyword overlap
            text_words = set(text.split())
            overlap = len(query_words.intersection(text_words))
            
            if overlap > 0:  # At least one keyword match
                relevant_items.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("summary", "")[:200],
                    "source": "rss_breaking",
                    "relevance_score": overlap,
                    "published_at": item.get("published_at")
                })
        
        # Sort by relevance and recency
        relevant_items.sort(key=lambda x: (x["relevance_score"], x.get("published_at") or ""), reverse=True)
        
        result = relevant_items[:max_results]
        logger.info(f"📰 Found {len(result)} relevant breaking news items")
        
        return result
        
    except Exception as e:
        logger.error(f"RSS discovery failed: {e}")
        return []

async def quick_ingest_breaking_news(query: str, max_items: int = 5) -> Dict[str, Any]:
    """
    Quick ingestion of breaking news items
    Lightweight alternative to full discovery
    """
    start_time = datetime.now()
    
    try:
        # Discover relevant items
        items = await discover_breaking_news(query, max_items * 2)  # Get extra for filtering
        
        if not items:
            return {
                "discovered_items": 0,
                "ingested_docs": 0,
                "ingested_chunks": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "source": "rss_breaking"
            }
        
        # Quick ingest top items
        from ingest.html_fetch import fetch_article
        from preprocess.clean import clean_text, is_trash
        from preprocess.chunk import chunk_with_meta
        from models.embeddings import embed_texts
        from index.vectorstore.chroma_store import store_singleton as store
        from preprocess.ner import extract_entities
        from index.graph.graph_store import graph_store
        
        ingested_docs = 0
        ingested_chunks = 0
        
        for item in items[:max_items]:
            try:
                url = item["url"]
                logger.info(f"📄 Quick ingesting {url[:50]}...")
                
                # Fetch with timeout
                article = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, fetch_article, url),
                    timeout=8.0  # Quick timeout
                )
                
                if not article:
                    continue
                
                # Quick clean and chunk
                clean_content = clean_text(article["text"])
                if is_trash(clean_content):
                    continue
                
                chunks = chunk_with_meta(url, clean_content)
                if not chunks:
                    continue
                
                # Quick embed and store
                ids, texts, metas = [], [], []
                for cid, ch, idx in chunks:
                    ids.append(cid)
                    texts.append(ch)
                    metas.append({
                        "url": article["url"],
                        "host": article["host"],
                        "doc_id": url,
                        "title": item.get("title", ""),
                        "chunk_index": idx,
                        "source": "rss_breaking"
                    })
                
                embeddings = embed_texts(texts)
                store.upsert(ids=ids, texts=texts, embeddings=embeddings, metadatas=metas)
                
                # Quick entity extraction
                for cid, ch, idx in chunks:
                    entities = extract_entities(ch)
                    if entities:
                        graph_store.add_chunk(
                            chunk_id=cid,
                            entities=entities,
                            meta={
                                "url": article["url"],
                                "host": article["host"],
                                "doc_id": url
                            }
                        )
                
                ingested_docs += 1
                ingested_chunks += len(chunks)
                logger.info(f"✅ Quick ingested {len(chunks)} chunks")
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout on {item['url'][:40]}...")
                continue
            except Exception as e:
                logger.warning(f"❌ Failed to ingest {item['url'][:40]}...: {e}")
                continue
        
        # Save graph if we ingested anything
        if ingested_chunks > 0:
            try:
                graph_store.save()
            except Exception as e:
                logger.warning(f"Failed to save graph: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "discovered_items": len(items),
            "ingested_docs": ingested_docs,
            "ingested_chunks": ingested_chunks,
            "duration_seconds": duration,
            "source": "rss_breaking"
        }
        
        logger.info(f"📰 Breaking news ingestion complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Breaking news ingestion failed: {e}")
        return {
            "discovered_items": 0,
            "ingested_docs": 0,
            "ingested_chunks": 0,
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "source": "rss_breaking",
            "error": str(e)
        }