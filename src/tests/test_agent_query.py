"""
Integration tests for agent-on-query functionality
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from synth.planner import derive_seeds_from_query, ensure_corpus, pull_fresh_items
from app.schemas import QueryRequest

class TestSeedDerivation:
    """Test seed derivation from queries"""
    
    def test_security_query_seeds(self):
        """Test seed derivation for security-related queries"""
        query = "university data breach recent attacks"
        seeds = derive_seeds_from_query(query)
        
        assert "entities" in seeds
        assert "feeds" in seeds
        assert len(seeds["feeds"]) > 0
        
        # Should include education and security feeds
        feed_urls = " ".join(seeds["feeds"])
        assert "insidehighered" in feed_urls or "chronicle" in feed_urls  # Education
        assert "bleepingcomputer" in feed_urls or "krebsonsecurity" in feed_urls  # Security
    
    def test_healthcare_query_seeds(self):
        """Test seed derivation for healthcare queries"""
        query = "hospital ransomware attack patient data"
        seeds = derive_seeds_from_query(query)
        
        feed_urls = " ".join(seeds["feeds"])
        assert "healthcareinfosecurity" in feed_urls or "modernhealthcare" in feed_urls
    
    def test_financial_query_seeds(self):
        """Test seed derivation for financial queries"""
        query = "bank security breach credit card data"
        seeds = derive_seeds_from_query(query)
        
        feed_urls = " ".join(seeds["feeds"])
        assert "bankinfosecurity" in feed_urls or "americanbanker" in feed_urls

class TestFreshContentPulling:
    """Test fresh content discovery and pulling"""
    
    @pytest.mark.asyncio
    async def test_pull_fresh_items_rss_only(self):
        """Test pulling fresh items from RSS feeds only"""
        seeds = {
            "entities": [],
            "feeds": ["https://feeds.reuters.com/reuters/topNews"]
        }
        
        with patch('synth.planner.pull_rss') as mock_rss:
            # Mock RSS response
            mock_rss.return_value = [
                {
                    "url": "https://example.com/news1",
                    "title": "Test News 1",
                    "summary": "Test summary 1",
                    "published_at": "2024-01-15T10:00:00",
                    "source": "Reuters"
                }
            ]
            
            # Mock datetime to ensure recency filter works
            from datetime import datetime, timedelta
            recent_date = datetime.now() - timedelta(days=1)
            
            with patch('synth.planner.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime.now()
                mock_rss.return_value[0]["published_at"] = recent_date
                
                items = await pull_fresh_items(seeds, recent_days=7, max_urls=10)
                
                assert len(items) > 0
                assert items[0]["discovery_method"] == "rss"
    
    @pytest.mark.asyncio
    async def test_pull_fresh_items_with_web_search(self):
        """Test pulling fresh items with web search"""
        seeds = {
            "entities": ["TestEntity"],
            "feeds": []
        }
        
        with patch('synth.planner.web_searcher') as mock_searcher:
            # Mock web search response
            mock_searcher.discover.return_value = [
                {
                    "url": "https://example.com/search1",
                    "title": "Search Result 1",
                    "snippet": "Search snippet 1",
                    "source": "web_search"
                }
            ]
            
            items = await pull_fresh_items(seeds, recent_days=7, max_urls=10)
            
            assert len(items) > 0
            assert items[0]["discovery_method"] == "web_search"
            assert items[0]["entity"] == "TestEntity"

class TestEnsureCorpus:
    """Test the main ensure_corpus function"""
    
    @pytest.mark.asyncio
    async def test_ensure_corpus_basic_flow(self):
        """Test the basic ensure_corpus flow"""
        query = "test security breach"
        
        # Mock all the dependencies
        with patch('synth.planner.pull_fresh_items') as mock_pull, \
             patch('synth.planner.ingest_fresh_content') as mock_ingest, \
             patch('synth.planner.should_rebuild_raptor') as mock_should_rebuild, \
             patch('synth.planner.RaptorBuilder') as mock_builder:
            
            # Setup mocks
            mock_pull.return_value = [{"url": "test.com", "title": "Test"}]
            mock_ingest.return_value = {"docs": 5, "chunks": 20}
            mock_should_rebuild.return_value = False
            
            result = await ensure_corpus(query, recent_days=7, max_urls=50)
            
            # Verify result structure
            assert "seeds" in result
            assert "fresh_items_found" in result
            assert "ingested" in result
            assert "raptor_rebuilt" in result
            assert result["query"] == query
            
            # Verify function calls
            mock_pull.assert_called_once()
            mock_ingest.assert_called_once()
            mock_should_rebuild.assert_called_once_with(5)

class TestQueryRequestSchema:
    """Test the extended QueryRequest schema"""
    
    def test_query_request_defaults(self):
        """Test QueryRequest with default values"""
        req = QueryRequest(q="test query")
        
        assert req.q == "test query"
        assert req.k == 8
        assert req.expand == False
        assert req.discover == False
        assert req.fast_mode == True
        assert req.auto_ingest == True  # New default
        assert req.recent_days == 14   # New default
        assert req.max_urls == 200     # New default
    
    def test_query_request_custom_values(self):
        """Test QueryRequest with custom values"""
        req = QueryRequest(
            q="custom query",
            k=12,
            auto_ingest=False,
            recent_days=7,
            max_urls=100
        )
        
        assert req.q == "custom query"
        assert req.k == 12
        assert req.auto_ingest == False
        assert req.recent_days == 7
        assert req.max_urls == 100

# Integration test that can be run manually
async def manual_integration_test():
    """Manual integration test - requires actual services"""
    print("🧪 Running manual integration test...")
    
    try:
        # Test seed derivation
        query = "university data breach"
        seeds = derive_seeds_from_query(query)
        print(f"✅ Seeds derived: {len(seeds['entities'])} entities, {len(seeds['feeds'])} feeds")
        
        # Test ensure_corpus (with small limits for testing)
        result = await ensure_corpus(query, recent_days=1, max_urls=5)
        print(f"✅ Corpus ensured: {result['fresh_items_found']} items found")
        
        print("🎉 Manual integration test passed!")
        
    except Exception as e:
        print(f"❌ Manual integration test failed: {e}")
        raise

if __name__ == "__main__":
    # Run manual test
    asyncio.run(manual_integration_test())