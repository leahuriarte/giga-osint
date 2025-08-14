"""Web search discovery via SerpAPI/Bing API or fallback to RSS feeds"""

import httpx
import asyncio
from typing import List, Dict, Any, Optional
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class WebSearcher:
    def __init__(self):
        self.serpapi_key = getattr(settings, 'serpapi_api_key', None)
        self.exa_key = getattr(settings, 'exa_api_key', None)
        
    async def discover(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Discover URLs for a query using available search APIs
        Returns: [{"url": str, "title": str, "snippet": str, "source": str}, ...]
        """
        # Try search APIs in order of preference: Exa -> SerpAPI -> RSS fallback
        if self.exa_key:
            logger.info("Trying Exa search...")
            exa_results = await self._exa_search(query, max_results)
            if exa_results:
                logger.info(f"Exa returned {len(exa_results)} results")
                return exa_results
            else:
                logger.warning("Exa search failed, trying other options")
        
        if self.serpapi_key:
            logger.info("Trying SerpAPI search...")
            serpapi_results = await self._serpapi_search(query, max_results)
            if serpapi_results:
                logger.info(f"SerpAPI returned {len(serpapi_results)} results")
                return serpapi_results
            else:
                logger.warning("SerpAPI failed, falling back to RSS discovery")
        
        # Final fallback to RSS
        logger.info("Using RSS discovery (no search APIs available or all failed)")
        return await self._rss_fallback(query, max_results)
    
    async def _serpapi_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using SerpAPI"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "q": query,
                    "api_key": self.serpapi_key,
                    "engine": "google",
                    "num": min(max_results, 100),
                    "gl": "us",
                    "hl": "en"
                }
                response = await client.get("https://serpapi.com/search", params=params)
                
                if response.status_code == 401:
                    logger.error("SerpAPI: Invalid API key - check your SERPAPI_API_KEY")
                    return []
                elif response.status_code == 429:
                    logger.error("SerpAPI: Rate limit exceeded")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                results = []
                organic_results = data.get("organic_results", [])
                logger.info(f"SerpAPI returned {len(organic_results)} organic results")
                
                for item in organic_results[:max_results]:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    
                    if link and title:  # Basic validation
                        results.append({
                            "url": link,
                            "title": title,
                            "snippet": snippet,
                            "source": "serpapi"
                        })
                
                logger.info(f"SerpAPI: Processed {len(results)} valid results")
                return results
                
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []
    
    async def _exa_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using Exa API (high-quality content discovery)"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "x-api-key": self.exa_key,
                    "Content-Type": "application/json"
                }
                
                # Strategy: Try recent-first search, then broader coverage
                from datetime import datetime, timedelta
                
                # Get dates for very recent content
                today = datetime.now()
                week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                month_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")
                
                payloads = [
                    # 1. Very recent content (last 7 days) - no date restriction for freshest results
                    {
                        "query": query,
                        "num_results": min(max_results, 10),
                        "use_autoprompt": True,
                        "type": "neural"
                        # No start_crawl_date to get the absolute freshest content
                    },
                    # 2. Recent content with broader domains (last 30 days)
                    {
                        "query": query,
                        "num_results": min(max_results, 15),
                        "start_crawl_date": month_ago,
                        "include_domains": [
                            # Major news sources that break stories first
                            "reuters.com", "apnews.com", "bloomberg.com", "wsj.com", "nytimes.com",
                            "cnn.com", "bbc.com", "techcrunch.com", "theverge.com", "wired.com",
                            # Security/tech sources
                            "krebsonsecurity.com", "bleepingcomputer.com", "arstechnica.com",
                            "threatpost.com", "darkreading.com", "securityweek.com", "cyberscoop.com",
                            # Tech industry publications
                            "techradar.com", "zdnet.com", "computerworld.com", "infoworld.com",
                            "scmagazine.com", "securitymagazine.com", "csoonline.com",
                            # Government/public sector tech
                            "govtech.com", "federalnewsnetwork.com", "fedscoop.com", "nextgov.com",
                            # Industry-specific sources
                            "insurancejournal.com", "healthcareinfosecurity.com", "bankinfosecurity.com",
                            # Legal/class action sources
                            "classaction.org", "law360.com", "legalnewsline.com", "jdsupra.com",
                            # University/education sources
                            "insidehighered.com", "chronicle.com", "educationdive.com", "campustechnology.com",
                            # Data breach specialists
                            "databreaches.net", "privacyrights.org", "identitytheft.gov"
                        ],
                        "use_autoprompt": True,
                        "type": "neural"
                    },
                    # 3. Fallback with enhanced query for older but relevant content
                    {
                        "query": f"{query} latest news recent incident",
                        "num_results": min(max_results, 10),
                        "start_crawl_date": "2024-01-01",
                        "use_autoprompt": True,
                        "type": "neural"
                    }
                ]
                
                for i, payload in enumerate(payloads):
                    try:
                        response = await client.post(
                            "https://api.exa.ai/search",
                            headers=headers,
                            json=payload
                        )
                        
                        if response.status_code == 401:
                            logger.error("Exa API: Invalid API key")
                            return []
                        elif response.status_code == 429:
                            logger.error("Exa API: Rate limit exceeded")
                            return []
                        
                        response.raise_for_status()
                        data = response.json()
                        
                        search_results = data.get("results", [])
                        logger.info(f"Exa search {i+1}: returned {len(search_results)} results")
                        
                        if search_results:  # If we got results, process and return
                            results = []
                            for item in search_results[:max_results]:
                                url = item.get("url", "")
                                title = item.get("title", "")
                                snippet = item.get("text", "")
                                
                                if url and title:
                                    results.append({
                                        "url": url,
                                        "title": title,
                                        "snippet": snippet[:300] if snippet else "",
                                        "source": f"exa"
                                    })
                            
                            logger.info(f"Exa: Processed {len(results)} valid results from search {i+1}")
                            return results
                            
                    except Exception as search_error:
                        logger.warning(f"Exa search {i+1} failed: {search_error}")
                        continue  # Try next search strategy
                
                # If all searches failed
                logger.error("All Exa search strategies failed")
                return []
                
        except Exception as e:
            logger.error(f"Exa search failed: {e}")
            return []
    

    
    async def _rss_fallback(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback to topic-relevant RSS feeds when no search API available"""
        # Comprehensive RSS feeds for breaking news and security
        security_feeds = [
            # Google News RSS (fastest breaking news)
            "https://news.google.com/rss/search?q=data+breach&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=cyber+attack&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=university+hack&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=cybersecurity&hl=en-US&gl=US&ceid=US:en",
            
            # Primary security sources
            "https://feeds.feedburner.com/eset/blog",
            "https://www.bleepingcomputer.com/feed/",
            "https://krebsonsecurity.com/feed/",
            "https://www.darkreading.com/rss.xml",
            "https://threatpost.com/feed/",
            "https://www.securityweek.com/feed",
            "https://cyberscoop.com/feed/",
            "https://www.scmagazine.com/feed",
            
            # Major news outlets (breaking news)
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/technologyNews",
            "https://feeds.reuters.com/Reuters/domesticNews",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            
            # Tech news that covers breaches quickly
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://arstechnica.com/feed/",
            "https://www.wired.com/feed/rss",
            "https://www.zdnet.com/news/rss.xml",
            "https://www.computerworld.com/index.rss",
            
            # Government/public sector (often first to report breaches)
            "https://www.govtech.com/rss/all.aspx",
            "https://www.fedscoop.com/feed/",
            "https://www.nextgov.com/rss/all/",
            
            # Education/university news (faster than general news for edu breaches)
            "https://www.insidehighered.com/rss.xml",
            "https://www.chronicle.com/section/news/rss",
            "https://www.educationdive.com/feeds/news/",
            "https://campustechnology.com/rss-feeds/all.aspx",
            
            # Legal/class action (often break breach news)
            "https://www.law360.com/articles/search?q=data+breach&rss=1",
            "https://www.classaction.org/news/feed",
            
            # Industry-specific (insurance, healthcare, finance report breaches fast)
            "https://www.insurancejournal.com/news/rss.xml",
            "https://www.healthcareinfosecurity.com/rss-feeds",
            "https://www.bankinfosecurity.com/rss-feeds",
            
            # Data breach specialists (very fast on breach news)
            "https://www.databreaches.net/feed/",
            "https://www.privacyrights.org/rss.xml",
            
            # Reddit security communities (often break news first)
            "https://www.reddit.com/r/cybersecurity/.rss",
            "https://www.reddit.com/r/netsec/.rss",
            "https://www.reddit.com/r/privacy/.rss"
        ]
        
        try:
            from ingest.rss import pull_rss
            # Pull recent items from security feeds
            items = pull_rss(security_feeds)
            
            # Simple keyword matching for relevance
            query_words = set(query.lower().split())
            relevant_items = []
            
            for item in items[:max_results * 2]:  # Get more to filter
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
                        "source": "rss_fallback",
                        "relevance_score": overlap
                    })
            
            # Sort by relevance and return top results
            relevant_items.sort(key=lambda x: x["relevance_score"], reverse=True)
            return relevant_items[:max_results]
            
        except Exception as e:
            logger.error(f"RSS fallback failed: {e}")
            return []

# Singleton
web_searcher = WebSearcher()