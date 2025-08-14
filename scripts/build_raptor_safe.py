#!/usr/bin/env python3
"""Safe RAPTOR node building without LLM calls"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set required env vars
if not os.getenv('GEMINI_API_KEY'):
    os.environ['GEMINI_API_KEY'] = 'dummy_key_for_raptor'  # Not used for extractive summaries

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_raptor_nodes():
    """Build RAPTOR nodes with extractive summaries (no LLM calls)"""
    
    logger.info("🌳 Starting safe RAPTOR build (no LLM calls)...")
    
    try:
        from index.raptor.builder import RaptorBuilder
        from discover.knowledge_tracker import knowledge_tracker
        
        # Get current knowledge base stats
        stats = knowledge_tracker.get_current_stats()
        logger.info(f"📊 Current knowledge base: {stats['total_chunks']} chunks")
        
        if stats['total_chunks'] < 50:
            logger.warning("⚠️ Very few chunks available. Consider running bulk ingestion first.")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                return False
        
        # Build with conservative limits
        builder = RaptorBuilder()
        
        # Use smaller limits to prevent hanging
        max_docs = min(1000, stats['total_chunks'])
        logger.info(f"🔢 Processing up to {max_docs} chunks")
        
        builder.build_nodes(
            topic_hint="osint_intelligence",
            min_docs=20,  # Lower minimum
            max_docs=max_docs,
            incremental=False
        )
        
        logger.info("✅ RAPTOR build complete!")
        
        # Test the nodes
        from index.raptor.builder import query_nodes
        test_results = query_nodes("cybersecurity", k=3)
        logger.info(f"🧪 Test query returned {len(test_results)} nodes")
        
        if test_results:
            logger.info("📄 Sample node preview:")
            sample = test_results[0]['text'][:200]
            logger.info(f"   {sample}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ RAPTOR build failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_raptor_status():
    """Check current RAPTOR node status"""
    try:
        from index.raptor.builder import query_nodes
        
        # Try to query existing nodes
        test_results = query_nodes("test", k=1)
        
        if test_results:
            logger.info(f"✅ RAPTOR nodes exist: {len(test_results)} found")
            return True
        else:
            logger.info("📭 No RAPTOR nodes found")
            return False
            
    except Exception as e:
        logger.info(f"📭 No RAPTOR nodes available: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build RAPTOR nodes safely")
    parser.add_argument("--check", action="store_true", help="Check RAPTOR status only")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    if args.check:
        check_raptor_status()
        sys.exit(0)
    
    if not args.force:
        print("🌳 RAPTOR Node Builder (Safe Mode)")
        print("=" * 40)
        print("This will build hierarchical summary nodes using:")
        print("- Extractive summarization (no LLM calls)")
        print("- Conservative memory usage")
        print("- Progress tracking")
        print()
        
        if not check_raptor_status():
            response = input("Build RAPTOR nodes? (y/N): ")
            if response.lower() != 'y':
                print("Cancelled.")
                sys.exit(0)
        else:
            response = input("RAPTOR nodes exist. Rebuild? (y/N): ")
            if response.lower() != 'y':
                print("Cancelled.")
                sys.exit(0)
    
    success = build_raptor_nodes()
    sys.exit(0 if success else 1)