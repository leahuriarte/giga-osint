#!/usr/bin/env python3
"""Continuous RSS monitoring for breaking news and updates"""

import sys
import os
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set required env vars
if not os.getenv('GEMINI_API_KEY'):
    os.environ['GEMINI_API_KEY'] = 'your_key_here'

import logging
from discover.rss_discovery import quick_ingest_breaking_news

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# High-priority RSS feeds for continuous monitoring
PRIORITY_FEEDS = [
    # Breaking news
    "https://news.google.com/rss/search?q=data+breach&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=cyber+attack&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=ransomware&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=supply+chain+attack&hl=en-US&gl=US&ceid=US:en",
    
    # Security alerts
    "https://www.cisa.gov/news.xml",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
    
    # Global news
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

# Keywords that trigger immediate ingestion
PRIORITY_KEYWORDS = [
    "data breach", "cyber attack", "ransomware", "supply chain attack",
    "zero day", "vulnerability", "malware", "phishing", "apt",
    "critical infrastructure", "national security", "espionage",
    "sanctions", "trade war", "geopolitical", "conflict",
    "supply chain", "logistics", "shipping", "port", "pipeline",
    "financial crime", "money laundering", "terrorist financing"
]

async def monitor_rss_feeds(check_interval_minutes: int = 30):
    """Continuously monitor RSS feeds for breaking news"""
    logger.info(f"🔄 Starting RSS monitoring (checking every {check_interval_minutes} minutes)")
    logger.info(f"📡 Monitoring {len(PRIORITY_FEEDS)} priority feeds")
    logger.info(f"🎯 Priority keywords: {len(PRIORITY_KEYWORDS)} terms")
    
    last_check = datetime.now() - timedelta(hours=1)  # Start with 1 hour lookback
    
    while True:
        try:
            logger.info(f"🔍 Checking for updates since {last_check.strftime('%H:%M:%S')}")
            
            # Check each priority keyword
            total_ingested = 0
            for keyword in PRIORITY_KEYWORDS[:10]:  # Limit to top 10 to avoid overload
                try:
                    result = await quick_ingest_breaking_news(keyword, max_items=3)
                    ingested = result.get('ingested_chunks', 0)
                    if ingested > 0:
                        logger.info(f"📰 '{keyword}': ingested {ingested} chunks")
                        total_ingested += ingested
                    
                    # Brief pause between keywords
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.warning(f"❌ Failed to check '{keyword}': {e}")
            
            if total_ingested > 0:
                logger.info(f"✅ Monitoring cycle complete: {total_ingested} total chunks ingested")
                
                # Save progress
                try:
                    from index.graph.graph_store import graph_store
                    graph_store.save()
                    logger.info("💾 Progress saved")
                except Exception as e:
                    logger.warning(f"Failed to save: {e}")
            else:
                logger.info("📊 No new content found this cycle")
            
            last_check = datetime.now()
            
            # Wait for next check
            logger.info(f"⏰ Next check in {check_interval_minutes} minutes...")
            await asyncio.sleep(check_interval_minutes * 60)
            
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
            logger.info("🔄 Continuing monitoring in 5 minutes...")
            await asyncio.sleep(300)  # 5 minute error recovery

async def one_time_priority_scan():
    """One-time scan of all priority keywords"""
    logger.info("🚀 Starting one-time priority scan...")
    
    total_ingested = 0
    for i, keyword in enumerate(PRIORITY_KEYWORDS):
        logger.info(f"🔍 [{i+1}/{len(PRIORITY_KEYWORDS)}] Scanning: '{keyword}'")
        
        try:
            result = await quick_ingest_breaking_news(keyword, max_items=5)
            ingested = result.get('ingested_chunks', 0)
            if ingested > 0:
                logger.info(f"✅ '{keyword}': {ingested} chunks")
                total_ingested += ingested
            
            # Brief pause
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.warning(f"❌ Failed '{keyword}': {e}")
    
    logger.info(f"🎯 Priority scan complete: {total_ingested} total chunks ingested")
    
    # Save results
    try:
        from index.graph.graph_store import graph_store
        graph_store.save()
        logger.info("💾 Results saved")
    except Exception as e:
        logger.warning(f"Failed to save: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RSS monitoring for OSINT")
    parser.add_argument("--mode", choices=["monitor", "scan"], default="scan",
                       help="monitor: continuous monitoring, scan: one-time scan")
    parser.add_argument("--interval", type=int, default=30,
                       help="Check interval in minutes (for monitor mode)")
    
    args = parser.parse_args()
    
    if args.mode == "monitor":
        asyncio.run(monitor_rss_feeds(args.interval))
    else:
        asyncio.run(one_time_priority_scan())