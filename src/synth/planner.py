"""
Tiny planner for agent-on-query: derives seeds, ingests fresh content, triggers bounded raptor rebuild
"""

from typing import List, Dict, Any, Set
from datetime import datetime, timedelta
import logging
from preprocess.ner import extract_entities
from discover.websearch import web_searcher
from ingest.rss import pull_rss
from ingest.html_fetch import fetch_article
from preprocess.clean import clean_text, is_trash
from preprocess.chunk import chunk_with_meta
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store
from index.raptor.builder import RaptorBuilder
from index.graph.graph_store import graph_store
import tldextract

logger = logging.getLogger(__name__)

def derive_seeds_from_query(query: str) -> Dict[str, List[str]]:
    """
    Extract entities and known feed patterns from query to create search seeds
    Returns: {"entities": [...], "feeds": [...]}
    """
    # Extract entities from the query
    entities = extract_entities(query)
    
    # Filter out generic terms
    generic_terms = {"today", "yesterday", "last week", "last month", "security", "attack", "breach", "news", "latest", "recent"}
    entities = [e for e in entities if e.lower() not in generic_terms and len(e) > 2]
    
    # Comprehensive RSS feed selection based on query content
    feeds = []
    query_lower = query.lower()
    
    # Always include core news and current events (primary sources)
    feeds.extend([
        # News and Current Events - Comprehensive global coverage
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.reuters.com/reuters/topNews", 
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.ap.org/rss/apf-usnews.xml",
        "https://rss.ap.org/rss/apf-worldnews.xml",
        f"https://news.google.com/rss/search?q={'+'.join(query.split())}&hl=en-US&gl=US&ceid=US:en"
    ])
    
    # Security and Cyber Intelligence (always include for OSINT)
    feeds.extend([
        "https://krebsonsecurity.com/feed/",
        "https://threatpost.com/feed/",
        "https://www.darkreading.com/rss.xml",
        "https://therecord.media/feed/",
        "https://www.bleepingcomputer.com/feed/",
        "https://feeds.feedburner.com/eset/blog",
        "https://www.databreaches.net/feed/",
        "https://isc.sans.edu/rssfeed.xml",
        "https://www.schneier.com/feed/",
        "https://arstechnica.com/security/feed/"
    ])
    
    # Technology and Digital Forensics
    feeds.extend([
        "https://www.bellingcat.com/feed/",
        "https://arstechnica.com/feed/"
    ])
    
    # Security/breach focused feeds (additional if query matches)
    if any(term in query_lower for term in ["breach", "hack", "cyber", "security", "attack", "vulnerability", "ransomware", "malware"]):
        feeds.extend([
            "https://www.securityweek.com/feed",
            "https://cyberscoop.com/feed/",
            "https://www.scmagazine.com/feed",
            "https://www.csoonline.com/feed"
        ])
    
    # University/education focused
    if any(term in query_lower for term in ["university", "college", "school", "student", "education", "campus"]):
        feeds.extend([
            "https://www.insidehighered.com/rss.xml",
            "https://www.chronicle.com/section/news/rss",
            "https://www.educationdive.com/feeds/news/",
            "https://campustechnology.com/rss-feeds/all.aspx"
        ])
    
    # Healthcare focused
    if any(term in query_lower for term in ["hospital", "health", "medical", "patient", "healthcare"]):
        feeds.extend([
            "https://www.healthcareinfosecurity.com/rss-feeds",
            "https://www.modernhealthcare.com/rss"
        ])
    
    # Financial focused
    if any(term in query_lower for term in ["bank", "financial", "credit", "payment", "finance"]):
        feeds.extend([
            "https://www.bankinfosecurity.com/rss-feeds",
            "https://www.americanbanker.com/feed"
        ])
    
    # Geopolitical Analysis (for international/conflict queries)
    if any(term in query_lower for term in ["war", "conflict", "geopolitical", "military", "defense", "international"]):
        feeds.extend([
            "https://www.foreignaffairs.com/rss.xml",
            "https://www.understandingwar.org/rss.xml"
        ])
    
    # Regional Specialists
    if any(term in query_lower for term in ["russia", "ukraine", "eastern europe", "central asia"]):
        feeds.extend([
            "https://www.rferl.org/api/epiqq"
        ])
    
    if any(term in query_lower for term in ["middle east", "arab", "israel", "palestine"]):
        feeds.extend([
            "https://www.aljazeera.com/xml/rss/all.xml"
        ])
    
    if any(term in query_lower for term in ["china", "asia", "pacific"]):
        feeds.extend([
            "https://www.scmp.com/rss/91/feed"
        ])
    
    if any(term in query_lower for term in ["defense", "military", "pentagon"]):
        feeds.extend([
            "https://www.defenseone.com/rss/all/"
        ])
    
    # Data and Leaked Information
    if any(term in query_lower for term in ["leak", "document", "investigation", "transparency"]):
        feeds.extend([
            "https://www.propublica.org/feeds/propublica/main",
            "https://www.icij.org/feed/"
        ])
    
    return {
        "entities": entities[:5],  # Limit to top 5 entities
        "feeds": list(set(feeds))  # Remove duplicates
    }

async def pull_fresh_items(seeds: Dict[str, List[str]], recent_days: int = 14, max_urls: int = 200) -> List[Dict[str, Any]]:
    """
    Pull fresh items from RSS feeds first, then web search if needed
    RSS is prioritized as it's faster and more reliable
    """
    cutoff_date = datetime.now() - timedelta(days=recent_days)
    fresh_items = []
    
    # Step 1: Pull from RSS feeds (primary method)
    logger.info(f"🔍 RSS Discovery: Pulling from {len(seeds['feeds'])} RSS feeds...")
    try:
        rss_items = pull_rss(seeds["feeds"])
        for item in rss_items:
            if not item.get("url"):
                continue
                
            # Apply recency filter if we have a published date
            pub_date = item.get("published_at")
            if pub_date and pub_date < cutoff_date:
                continue
                
            fresh_items.append({
                "url": item["url"],
                "title": item["title"] or "",
                "summary": item["summary"] or "",
                "published_at": pub_date,
                "source": item["source"] or "RSS",
                "discovery_method": "rss"
            })
            
            # Stop if we have enough from RSS
            if len(fresh_items) >= max_urls:
                break
                
        rss_count = len(fresh_items)
        logger.info(f"✅ RSS Discovery: Found {rss_count} fresh items")
        
    except Exception as e:
        logger.error(f"❌ RSS Discovery failed: {e}")
        rss_count = 0
    
    # Step 2: Web search only if we need more content
    remaining_slots = max_urls - len(fresh_items)
    if seeds["entities"] and remaining_slots > 0:
        logger.info(f"🌐 Web Search: Need {remaining_slots} more items, searching for entities: {seeds['entities'][:3]}")
        try:
            for entity in seeds["entities"][:3]:  # Limit to top 3 entities
                if len(fresh_items) >= max_urls:
                    break
                    
                search_query = f"{entity} recent news"
                search_results = await web_searcher.discover(search_query, max_results=min(20, remaining_slots))
                
                for result in search_results:
                    if len(fresh_items) >= max_urls:
                        break
                    fresh_items.append({
                        "url": result["url"],
                        "title": result["title"],
                        "summary": result["snippet"],
                        "published_at": None,  # Web search doesn't always have dates
                        "source": result["source"],
                        "discovery_method": "web_search",
                        "entity": entity
                    })
                
            web_count = len([i for i in fresh_items if i['discovery_method'] == 'web_search'])
            logger.info(f"✅ Web Search: Added {web_count} additional items")
            
        except Exception as e:
            logger.error(f"❌ Web Search failed: {e}")
    else:
        logger.info(f"⏭️  Web Search: Skipped (RSS provided {len(fresh_items)} items, entities: {len(seeds['entities'])})")
    
    # Step 3: Deduplicate by URL
    seen_urls = set()
    deduped_items = []
    for item in fresh_items:
        url = item["url"]
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped_items.append(item)
    
    logger.info(f"📊 Discovery Summary: {len(deduped_items)} unique items (RSS: {rss_count}, Web: {len(deduped_items) - rss_count})")
    return deduped_items[:max_urls]

def ingest_fresh_content(fresh_items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Ingest fresh content items into the vector store and graph
    Returns: {"docs": int, "chunks": int}
    """
    docs_ingested = 0
    total_chunks = 0
    
    for item in fresh_items:
        try:
            url = item["url"]
            
            # Try to fetch full article content
            article = fetch_article(url)
            if article and not is_trash(article["text"]):
                text = article["text"]
                host = article["host"]
            else:
                # Fallback to RSS summary
                text = clean_text(f"{item.get('title', '')} — {item.get('summary', '')}")
                if is_trash(text):
                    continue
                host = tldextract.extract(url).registered_domain or ""
            
            # Create document
            doc = {
                "doc_id": url,
                "url": url,
                "host": host,
                "title": item.get("title", ""),
                "published_at": item.get("published_at"),
                "source": item.get("source", ""),
                "text": text,
                "discovery_method": item.get("discovery_method", "unknown")
            }
            
            # Clean and chunk
            clean_text_content = clean_text(doc["text"])
            if is_trash(clean_text_content):
                continue
                
            chunks = chunk_with_meta(doc["doc_id"], clean_text_content)
            if not chunks:
                continue
            
            # Prepare for vector store
            ids = []
            texts = []
            metas = []
            
            for cid, chunk_text, idx in chunks:
                ids.append(cid)
                texts.append(chunk_text)
                metas.append({
                    "url": doc["url"],
                    "host": doc["host"],
                    "doc_id": doc["doc_id"],
                    "title": doc.get("title", ""),
                    "published_at": (doc.get("published_at").isoformat() if hasattr(doc.get("published_at"), "isoformat") and doc.get("published_at") else doc.get("published_at")),
                    "chunk_index": idx,
                    "discovery_method": doc.get("discovery_method", "unknown"),
                    "auto_ingested": True
                })
            
            # Embed and store
            embeddings = embed_texts(texts)
            store.upsert(ids=ids, texts=texts, embeddings=embeddings, metadatas=metas)
            
            # Update graph with entities
            for cid, chunk_text, idx in chunks:
                entities = extract_entities(chunk_text)
                if entities:
                    graph_store.add_chunk(
                        chunk_id=cid,
                        entities=entities,
                        meta={
                            "url": doc["url"],
                            "host": doc["host"],
                            "doc_id": doc["doc_id"],
                            "auto_ingested": True
                        }
                    )
            
            docs_ingested += 1
            total_chunks += len(chunks)
            
        except Exception as e:
            logger.error(f"Failed to ingest {item.get('url', 'unknown')}: {e}")
            continue
    
    # Save graph updates
    if docs_ingested > 0:
        graph_store.save()
    
    logger.info(f"Ingested {docs_ingested} docs, {total_chunks} chunks")
    return {"docs": docs_ingested, "chunks": total_chunks}

def should_rebuild_raptor(fresh_docs: int, last_build_hours: int = None) -> bool:
    """
    Determine if RAPTOR should be rebuilt based on fresh content and time since last build
    """
    # Rebuild if we have significant new content (>10 docs) or it's been >6 hours
    if fresh_docs >= 10:
        return True
    
    if last_build_hours and last_build_hours >= 6:
        return True
    
    return False

async def ensure_corpus(query: str, recent_days: int = 14, max_urls: int = 200) -> Dict[str, Any]:
    """
    Main planner function: ensures corpus is fresh for the query
    (i) expands seeds, (ii) ingests, (iii) (re)builds summaries if needed
    """
    logger.info(f"🤖 Agent-on-query: ensuring corpus for '{query}'")
    
    # Step 1: Derive seeds from query
    seeds = derive_seeds_from_query(query)
    logger.info(f"📍 Derived seeds: {len(seeds['entities'])} entities, {len(seeds['feeds'])} feeds")
    
    # Step 2: Pull fresh items
    fresh_items = await pull_fresh_items(seeds, recent_days, max_urls)
    logger.info(f"🔍 Found {len(fresh_items)} fresh items")
    
    # Step 3: Ingest fresh content
    ingest_result = {"docs": 0, "chunks": 0}
    if fresh_items:
        ingest_result = ingest_fresh_content(fresh_items)
    
    # Step 4: Trigger bounded RAPTOR rebuild if needed
    raptor_rebuilt = False
    if should_rebuild_raptor(ingest_result["docs"]):
        logger.info("🌳 Triggering RAPTOR rebuild...")
        try:
            builder = RaptorBuilder()
            builder.build_nodes(topic_hint=query, incremental=True)
            raptor_rebuilt = True
            logger.info("✅ RAPTOR rebuild complete")
        except Exception as e:
            logger.error(f"❌ RAPTOR rebuild failed: {e}")
    
    return {
        "seeds": seeds,
        "fresh_items_found": len(fresh_items),
        "ingested": ingest_result,
        "raptor_rebuilt": raptor_rebuilt,
        "query": query
    }