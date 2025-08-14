"""Query expansion for discovery using entities and semantic expansion"""

from typing import List, Set
from preprocess.ner import extract_entities
from retrieve.hybrid import hybrid_search
import logging

logger = logging.getLogger(__name__)

def generate_subqueries(query: str, max_subqueries: int = 5) -> List[str]:
    """
    Generate subqueries for discovery by:
    1. Extracting entities from the original query
    2. Finding related entities from existing corpus
    3. Creating focused subqueries
    """
    subqueries = []
    
    # Extract entities from the original query
    query_entities = extract_entities(query)
    logger.info(f"Query entities: {query_entities}")
    
    if not query_entities:
        # If no entities, create some basic variations
        return _create_basic_variations(query, max_subqueries)
    
    # Get related entities from existing corpus
    try:
        # Search existing corpus to find related entities
        existing_hits = hybrid_search(query, k=10)
        related_entities = set()
        
        for hit in existing_hits:
            hit_text = hit.get("text", "")
            hit_entities = extract_entities(hit_text)
            related_entities.update(hit_entities[:3])  # Top 3 entities per hit
        
        # Remove query entities to avoid duplication
        related_entities = related_entities - set(query_entities)
        related_entities = list(related_entities)[:8]  # Limit to prevent explosion
        
        logger.info(f"Related entities from corpus: {related_entities}")
        
    except Exception as e:
        logger.warning(f"Failed to get related entities: {e}")
        related_entities = []
    
    # Create subqueries by combining original query with entities
    for entity in query_entities[:3]:  # Top 3 query entities
        subqueries.append(f"{query} {entity}")
    
    for entity in related_entities[:3]:  # Top 3 related entities
        subqueries.append(f"{query} {entity}")
    
    # Create entity-focused queries
    for entity in (query_entities + related_entities)[:4]:
        subqueries.append(f"{entity} security breach attack")
        subqueries.append(f"{entity} vulnerability threat")
    
    # Deduplicate and limit
    seen = set()
    unique_subqueries = []
    for sq in subqueries:
        if sq.lower() not in seen and sq.lower() != query.lower():
            seen.add(sq.lower())
            unique_subqueries.append(sq)
            if len(unique_subqueries) >= max_subqueries:
                break
    
    logger.info(f"Generated {len(unique_subqueries)} subqueries: {unique_subqueries}")
    return unique_subqueries

def _create_basic_variations(query: str, max_variations: int) -> List[str]:
    """Create basic query variations when no entities are found"""
    variations = []
    
    # Add security-focused variations
    security_terms = ["security", "breach", "attack", "vulnerability", "threat", "malware"]
    for term in security_terms[:max_variations]:
        variations.append(f"{query} {term}")
    
    # Add temporal variations
    temporal_terms = ["recent", "latest", "2024", "new"]
    for term in temporal_terms:
        if len(variations) < max_variations:
            variations.append(f"{term} {query}")
    
    return variations[:max_variations]

def expand_discovery_queries(original_query: str, max_total_queries: int = 8) -> List[str]:
    """
    Main function to expand a query into multiple discovery queries
    Returns the original query plus subqueries
    """
    queries = [original_query]  # Always include original
    
    subqueries = generate_subqueries(original_query, max_total_queries - 1)
    queries.extend(subqueries)
    
    return queries[:max_total_queries]