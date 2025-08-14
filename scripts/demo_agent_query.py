#!/usr/bin/env python3
"""
Demo script for agent-on-query functionality
Shows the complete workflow from query to fresh brief
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from synth.planner import derive_seeds_from_query, ensure_corpus
from synth.brief import make_brief
from app.schemas import QueryRequest

async def demo_workflow():
    """Demonstrate the complete agent-on-query workflow"""
    
    print("🤖 Agent-on-Query Demo Workflow")
    print("=" * 50)
    
    # Example query
    query = "What's up with university data breaches?"
    print(f"📝 Query: {query}")
    
    # Step 1: Show seed derivation
    print(f"\n🌱 Step 1: Deriving seeds from query...")
    seeds = derive_seeds_from_query(query)
    print(f"   Entities found: {seeds['entities']}")
    print(f"   RSS feeds selected: {len(seeds['feeds'])}")
    print(f"   Sample feeds:")
    for feed in seeds['feeds'][:3]:
        print(f"     - {feed}")
    
    # Step 2: Show what ensure_corpus would do (with small limits for demo)
    print(f"\n🔍 Step 2: Ensuring corpus is fresh...")
    print(f"   Parameters: recent_days=7, max_urls=20 (demo limits)")
    
    try:
        corpus_result = await ensure_corpus(query, recent_days=7, max_urls=20)
        
        print(f"   ✅ Fresh items discovered: {corpus_result['fresh_items_found']}")
        print(f"   📚 Documents ingested: {corpus_result['ingested']['docs']}")
        print(f"   📄 Chunks created: {corpus_result['ingested']['chunks']}")
        print(f"   🌳 RAPTOR rebuilt: {corpus_result['raptor_rebuilt']}")
        
    except Exception as e:
        print(f"   ⚠️  Demo corpus update failed: {e}")
        print(f"   (This is normal in demo mode - would use existing corpus)")
    
    # Step 3: Show brief generation
    print(f"\n📋 Step 3: Generating brief with updated corpus...")
    try:
        brief_result = make_brief(query, k=8, expand=True)
        
        print(f"   ✅ Brief generated successfully")
        print(f"   📚 Sources used: {len(brief_result.get('sources', []))}")
        
        # Show brief summary (truncated)
        summary = brief_result.get('summary', 'No summary available')
        if len(summary) > 200:
            summary = summary[:200] + "..."
        print(f"   📝 Summary preview: {summary}")
        
    except Exception as e:
        print(f"   ⚠️  Brief generation failed: {e}")
    
    # Step 4: Show the complete API request that would achieve this
    print(f"\n🔌 Step 4: Equivalent API request")
    api_request = {
        "q": query,
        "k": 8,
        "expand": True,
        "auto_ingest": True,
        "recent_days": 14,
        "max_urls": 100
    }
    
    print(f"   POST /api/brief")
    print(f"   Content-Type: application/json")
    print(f"   Body: {json.dumps(api_request, indent=6)}")
    
    print(f"\n✅ Demo workflow complete!")
    print(f"\nTo run the actual API:")
    print(f"  1. Start server: python -m uvicorn app.main:app --reload --port 8000")
    print(f"  2. Test request: python demo_agent_query.py")

def show_comparison():
    """Show before/after comparison"""
    
    print(f"\n📊 Before vs After Comparison")
    print("=" * 50)
    
    query = "recent hospital ransomware attacks"
    
    print(f"Query: {query}")
    print(f"\n🔴 BEFORE (Static corpus):")
    print(f"   - Searches only existing knowledge base")
    print(f"   - May miss recent incidents (hours/days old)")
    print(f"   - Limited to previously ingested sources")
    print(f"   - Response time: ~1-2 seconds")
    
    print(f"\n🟢 AFTER (Agent-on-query):")
    print(f"   - Automatically discovers fresh content")
    print(f"   - Includes breaking news and recent incidents")
    print(f"   - Expands to relevant sources dynamically")
    print(f"   - Response time: ~10-30 seconds (includes discovery)")
    
    # Show the request difference
    print(f"\n📝 Request Changes:")
    
    old_request = {"q": query, "k": 8}
    new_request = {
        "q": query, 
        "k": 8,
        "auto_ingest": True,
        "recent_days": 14,
        "max_urls": 100
    }
    
    print(f"   Old: {json.dumps(old_request)}")
    print(f"   New: {json.dumps(new_request)}")

async def main():
    """Main demo function"""
    await demo_workflow()
    show_comparison()

if __name__ == "__main__":
    asyncio.run(main())