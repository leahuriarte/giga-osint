#!/usr/bin/env python3
"""
Demo script showing the new agent-on-query functionality
"""

import requests
import json

def test_brief_with_auto_ingest():
    """Test the /api/brief endpoint with auto_ingest enabled"""
    
    # Test query
    query = "What's up with university data breaches?"
    
    # New request with auto_ingest parameters
    payload = {
        "q": query,
        "k": 8,
        "expand": True,
        "auto_ingest": True,  # Enable auto-ingest
        "recent_days": 14,    # Look back 14 days
        "max_urls": 50        # Limit to 50 URLs for demo
    }
    
    print(f"🤖 Testing agent-on-query for: '{query}'")
    print(f"📋 Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Make request to local server (assuming it's running on port 8000)
        response = requests.post("http://localhost:8000/api/brief", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Success! Response structure:")
            
            # Show corpus update info if available
            if "corpus_update" in result:
                corpus = result["corpus_update"]
                print(f"📊 Corpus Update:")
                print(f"  - Fresh items found: {corpus['fresh_items_found']}")
                print(f"  - Docs ingested: {corpus['ingested']['docs']}")
                print(f"  - Chunks created: {corpus['ingested']['chunks']}")
                print(f"  - RAPTOR rebuilt: {corpus['raptor_rebuilt']}")
                print(f"  - Entities derived: {len(corpus['seeds']['entities'])}")
                print(f"  - RSS feeds used: {len(corpus['seeds']['feeds'])}")
            
            # Show brief summary
            print(f"\n📝 Brief Summary:")
            summary = result.get("summary", "No summary available")
            print(summary[:300] + "..." if len(summary) > 300 else summary)
            
            # Show source count
            sources = result.get("sources", [])
            print(f"\n📚 Sources: {len(sources)} found")
            
            # Show verification
            verification = result.get("verification", {})
            if verification:
                print(f"🔍 Verification: {verification.get('confidence', 'unknown')} confidence")
        
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - make sure the server is running on localhost:8000")
        print("   Run: python -m uvicorn app.main:app --reload --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_legacy_vs_new():
    """Compare legacy discovery vs new auto-ingest"""
    
    query = "recent ransomware attacks"
    
    # Legacy request
    legacy_payload = {
        "q": query,
        "k": 8,
        "discover": True,
        "auto_ingest": False
    }
    
    # New auto-ingest request
    new_payload = {
        "q": query,
        "k": 8,
        "auto_ingest": True,
        "recent_days": 7,
        "max_urls": 30
    }
    
    print(f"\n🔄 Comparing legacy vs new approach for: '{query}'")
    
    for name, payload in [("Legacy", legacy_payload), ("Auto-ingest", new_payload)]:
        print(f"\n{name} approach:")
        try:
            response = requests.post("http://localhost:8000/api/brief", json=payload)
            if response.status_code == 200:
                result = response.json()
                sources = len(result.get("sources", []))
                print(f"  ✅ {sources} sources found")
                
                if "corpus_update" in result:
                    corpus = result["corpus_update"]
                    print(f"  📊 {corpus['ingested']['docs']} new docs ingested")
                elif "discovery" in result:
                    print(f"  🔍 Legacy discovery used")
            else:
                print(f"  ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Agent-on-Query Demo")
    print("=" * 50)
    
    test_brief_with_auto_ingest()
    test_legacy_vs_new()
    
    print("\n✅ Demo complete!")
    print("\nTo run the server:")
    print("  python -m uvicorn app.main:app --reload --port 8000")