#!/usr/bin/env python3
"""
Test script for the new agent-on-query functionality
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from synth.planner import derive_seeds_from_query, ensure_corpus

async def test_seed_derivation():
    """Test seed derivation from various queries"""
    test_queries = [
        "What's up with university data breaches?",
        "Recent cyber attacks on hospitals",
        "Bank security incidents this month",
        "Latest ransomware attacks"
    ]
    
    print("🧪 Testing seed derivation...")
    for query in test_queries:
        seeds = derive_seeds_from_query(query)
        print(f"\nQuery: {query}")
        print(f"  Entities: {seeds['entities']}")
        print(f"  Feeds: {len(seeds['feeds'])} feeds")

async def test_ensure_corpus():
    """Test the full ensure_corpus pipeline"""
    query = "university data breach"
    print(f"\n🤖 Testing ensure_corpus for: '{query}'")
    
    try:
        result = await ensure_corpus(query, recent_days=7, max_urls=10)
        print(f"✅ Success!")
        print(f"  Seeds: {len(result['seeds']['entities'])} entities, {len(result['seeds']['feeds'])} feeds")
        print(f"  Fresh items: {result['fresh_items_found']}")
        print(f"  Ingested: {result['ingested']['docs']} docs, {result['ingested']['chunks']} chunks")
        print(f"  RAPTOR rebuilt: {result['raptor_rebuilt']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🚀 Testing Agent-on-Query Implementation")
    
    await test_seed_derivation()
    await test_ensure_corpus()
    
    print("\n✅ Tests complete!")

if __name__ == "__main__":
    asyncio.run(main())