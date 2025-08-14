#!/usr/bin/env python3
"""
Test the fixed agent-on-query functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from synth.planner import derive_seeds_from_query

def test_comprehensive_feeds():
    """Test the new comprehensive RSS feed selection"""
    
    test_queries = [
        "university data breach",
        "hospital ransomware attack", 
        "bank security incident",
        "russia ukraine conflict",
        "china cyber attack",
        "leaked documents investigation"
    ]
    
    print("🧪 Testing Comprehensive RSS Feed Selection")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        seeds = derive_seeds_from_query(query)
        
        print(f"   🌱 Entities: {seeds['entities']}")
        print(f"   📡 RSS Feeds: {len(seeds['feeds'])} selected")
        
        # Show sample feeds
        for i, feed in enumerate(seeds['feeds'][:5]):
            print(f"      {i+1}. {feed}")
        
        if len(seeds['feeds']) > 5:
            print(f"      ... and {len(seeds['feeds']) - 5} more")

def test_api_schema():
    """Test the API schema defaults"""
    from app.schemas import QueryRequest
    
    print(f"\n🔧 Testing API Schema Defaults")
    print("=" * 30)
    
    req = QueryRequest(q="test query")
    print(f"   auto_ingest: {req.auto_ingest}")
    print(f"   recent_days: {req.recent_days}")
    print(f"   max_urls: {req.max_urls}")
    print(f"   discover: {req.discover}")

if __name__ == "__main__":
    test_comprehensive_feeds()
    test_api_schema()
    print(f"\n✅ All tests completed!")
    print(f"\nThe fix should resolve:")
    print(f"  1. ❌ UnboundLocalError: 'result' variable scoping issue")
    print(f"  2. ✅ Comprehensive RSS feeds (40+ sources)")
    print(f"  3. ✅ RSS-first discovery strategy")
    print(f"  4. ✅ Auto-ingest enabled by default")