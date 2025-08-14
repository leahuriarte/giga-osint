#!/usr/bin/env python3
"""Complete setup for massive OSINT knowledge base"""

import sys
import os
import asyncio
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def setup_massive_osint():
    """Complete setup process for massive OSINT system"""
    
    logger.info("🚀 MASSIVE OSINT SETUP STARTING")
    logger.info("=" * 60)
    
    # Check environment
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("❌ GEMINI_API_KEY not set!")
        logger.info("Please set your API key in .env file")
        return False
    
    # Phase 1: Clean slate
    logger.info("🧹 Phase 1: Preparing clean environment...")
    try:
        from index.vectorstore.chroma_store import store_singleton as store
        from index.graph.graph_store import graph_store
        
        # Reset vector store
        store.reset()
        logger.info("✅ Vector store reset")
        
        # Reset graph
        if hasattr(graph_store, 'G'):
            graph_store.G.clear()
            graph_store.save()
        logger.info("✅ Graph reset")
        
    except Exception as e:
        logger.warning(f"⚠️ Reset warning: {e}")
    
    # Phase 2: Massive bulk ingestion
    logger.info("📚 Phase 2: MASSIVE bulk ingestion...")
    logger.info("This will ingest 150+ Wikipedia articles + 80+ RSS feeds")
    logger.info("Estimated time: 30-60 minutes")
    
    try:
        # Import and run bulk ingestion
        bulk_script = Path(__file__).parent / "bulk_ingest.py"
        result = subprocess.run([sys.executable, str(bulk_script)], 
                              capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode == 0:
            logger.info("✅ Bulk ingestion completed successfully")
            logger.info(result.stdout.split('\n')[-10:])  # Show last 10 lines
        else:
            logger.error(f"❌ Bulk ingestion failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Bulk ingestion timed out (>1 hour)")
        return False
    except Exception as e:
        logger.error(f"❌ Bulk ingestion error: {e}")
        return False
    
    # Phase 3: Priority RSS scan
    logger.info("📡 Phase 3: Priority RSS scan...")
    try:
        rss_script = Path(__file__).parent / "rss_monitor.py"
        result = subprocess.run([sys.executable, str(rss_script), "--mode", "scan"], 
                              capture_output=True, text=True, timeout=600)  # 10 min timeout
        
        if result.returncode == 0:
            logger.info("✅ Priority RSS scan completed")
        else:
            logger.warning(f"⚠️ RSS scan issues: {result.stderr}")
            
    except Exception as e:
        logger.warning(f"⚠️ RSS scan error: {e}")
    
    # Phase 4: Final optimization
    logger.info("🔧 Phase 4: Final optimization...")
    try:
        # Build RAPTOR nodes
        from index.raptor.builder import RaptorBuilder
        builder = RaptorBuilder()
        builder.build_nodes(topic_hint="comprehensive_global_osint")
        logger.info("✅ RAPTOR hierarchical summaries built")
        
        # Get final stats
        from discover.knowledge_tracker import knowledge_tracker
        stats = knowledge_tracker.get_current_stats()
        
        logger.info("🎯 MASSIVE OSINT SETUP COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"📊 FINAL KNOWLEDGE BASE STATISTICS:")
        logger.info(f"   📄 Documents: {stats['total_documents']:,}")
        logger.info(f"   📝 Chunks: {stats['total_chunks']:,}")
        logger.info(f"   🏷️  Entities: {stats['total_entities']:,}")
        
        # Estimate coverage
        if stats['total_chunks'] > 10000:
            logger.info("🌍 COVERAGE: Comprehensive global intelligence")
        elif stats['total_chunks'] > 5000:
            logger.info("🌎 COVERAGE: Extensive regional intelligence")
        elif stats['total_chunks'] > 1000:
            logger.info("🏢 COVERAGE: Solid organizational intelligence")
        else:
            logger.info("🔍 COVERAGE: Basic intelligence foundation")
        
        logger.info("🚀 READY TO USE:")
        logger.info("   1. Start server: PYTHONPATH=./src uvicorn app.main:app --reload --port 8000")
        logger.info("   2. Open browser: http://localhost:8000")
        logger.info("   3. Query anything: geopolitics, supply chains, cyber threats, etc.")
        logger.info("   4. Optional: Run RSS monitoring: python scripts/rss_monitor.py --mode monitor")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Final optimization failed: {e}")
        return False

def estimate_requirements():
    """Estimate system requirements for massive ingestion"""
    logger.info("📊 SYSTEM REQUIREMENTS ESTIMATE:")
    logger.info("   💾 Disk space: ~2-5 GB (vector embeddings + graph)")
    logger.info("   🧠 RAM: ~4-8 GB (embedding models + processing)")
    logger.info("   ⏱️  Time: 30-60 minutes (depends on network speed)")
    logger.info("   🌐 Network: Stable internet (150+ sources to fetch)")
    logger.info("   🔑 API: Valid Gemini API key required")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup massive OSINT knowledge base")
    parser.add_argument("--estimate", action="store_true", 
                       help="Show system requirements estimate")
    parser.add_argument("--confirm", action="store_true",
                       help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if args.estimate:
        estimate_requirements()
        sys.exit(0)
    
    if not args.confirm:
        estimate_requirements()
        print("\n" + "="*60)
        response = input("🤔 Proceed with massive OSINT setup? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            sys.exit(0)
    
    success = asyncio.run(setup_massive_osint())
    sys.exit(0 if success else 1)