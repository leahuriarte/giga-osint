"""Filtering and deduplication for discovered URLs"""

import re
from typing import List, Dict, Any, Set
from urllib.parse import urlparse
import tldextract
import logging

logger = logging.getLogger(__name__)

# Blocklisted domains/patterns
DOMAIN_BLOCKLIST = {
    # Social media (often low-quality for OSINT)
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com", "tiktok.com",
    # Generic content farms
    "pinterest.com", "reddit.com", "quora.com", "yahoo.com",
    # Paywalled/subscription sites that often fail extraction
    "wsj.com", "ft.com", "economist.com",
    # Low-quality aggregators
    "buzzfeed.com", "clickhole.com", "upworthy.com"
}

# Allowed file extensions for content
ALLOWED_EXTENSIONS = {
    "", "html", "htm", "php", "asp", "aspx", "jsp", "cfm", "shtml"
}

# Blocked file extensions
BLOCKED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", 
    "zip", "rar", "tar", "gz", "exe", "dmg", "pkg",
    "jpg", "jpeg", "png", "gif", "svg", "webp",
    "mp3", "mp4", "avi", "mov", "wmv", "flv",
    "css", "js", "json", "xml", "rss"
}

def filter_discovered_urls(discovered_results: List[Dict[str, Any]], 
                          existing_urls: Set[str] = None,
                          max_per_domain: int = 3) -> List[Dict[str, Any]]:
    """
    Filter and deduplicate discovered URLs
    
    Args:
        discovered_results: List of discovery results with url, title, snippet, source
        existing_urls: Set of URLs already in the system
        max_per_domain: Maximum URLs to keep per domain
    
    Returns:
        Filtered list of discovery results
    """
    if existing_urls is None:
        existing_urls = set()
    
    filtered = []
    seen_urls = set()
    domain_counts = {}
    
    for result in discovered_results:
        url = result.get("url", "").strip()
        if not url:
            continue
            
        # Skip if already processed
        if url in existing_urls or url in seen_urls:
            continue
            
        # Parse URL
        try:
            parsed = urlparse(url)
            domain_info = tldextract.extract(url)
            domain = domain_info.registered_domain.lower()
        except Exception:
            logger.warning(f"Failed to parse URL: {url}")
            continue
        
        # Apply filters
        if not _passes_filters(url, parsed, domain):
            continue
            
        # Domain diversity - limit per domain
        domain_count = domain_counts.get(domain, 0)
        if domain_count >= max_per_domain:
            continue
            
        # Passed all filters
        filtered.append(result)
        seen_urls.add(url)
        domain_counts[domain] = domain_count + 1
    
    logger.info(f"Filtered {len(discovered_results)} URLs down to {len(filtered)}")
    return filtered

def _passes_filters(url: str, parsed, domain: str) -> bool:
    """Check if URL passes all filters"""
    
    # Domain blocklist
    if domain in DOMAIN_BLOCKLIST:
        return False
    
    # Check for suspicious patterns in URL
    suspicious_patterns = [
        r'/login', r'/register', r'/signup', r'/auth',
        r'/admin', r'/wp-admin', r'/dashboard',
        r'/search\?', r'/tag/', r'/category/',
        r'\.pdf$', r'\.doc$', r'\.zip$'
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    
    # Check file extension
    path = parsed.path.lower()
    if '.' in path:
        ext = path.split('.')[-1]
        if ext in BLOCKED_EXTENSIONS:
            return False
        if ext not in ALLOWED_EXTENSIONS and len(ext) <= 4:
            return False  # Unknown short extension, likely a file
    
    # URL length check (very long URLs often problematic)
    if len(url) > 500:
        return False
    
    # Must be HTTP/HTTPS
    if parsed.scheme not in ('http', 'https'):
        return False
    
    return True

def dedupe_by_content_similarity(results: List[Dict[str, Any]], 
                                similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Remove results with very similar titles/snippets
    Simple implementation using string similarity
    """
    if len(results) <= 1:
        return results
    
    filtered = []
    
    for i, result in enumerate(results):
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        content = f"{title} {snippet}"
        
        # Check against already filtered results
        is_duplicate = False
        for existing in filtered:
            existing_title = existing.get("title", "").lower()
            existing_snippet = existing.get("snippet", "").lower()
            existing_content = f"{existing_title} {existing_snippet}"
            
            # Simple similarity check
            if _text_similarity(content, existing_content) > similarity_threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered.append(result)
    
    if len(filtered) < len(results):
        logger.info(f"Removed {len(results) - len(filtered)} similar results")
    
    return filtered

def _text_similarity(text1: str, text2: str) -> float:
    """Simple text similarity using word overlap"""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def get_existing_urls_from_store() -> Set[str]:
    """Get URLs already in the vector store to avoid duplicates"""
    try:
        from index.vectorstore.chroma_store import store_singleton as store
        
        # Fetch all documents with metadata
        all_docs = store.fetch_all(limit=10000)
        
        urls = set()
        for meta in all_docs.get("metadatas", []):
            if meta and "url" in meta:
                urls.add(meta["url"])
        
        logger.info(f"Found {len(urls)} existing URLs in store")
        return urls
        
    except Exception as e:
        logger.error(f"Failed to get existing URLs: {e}")
        return set()