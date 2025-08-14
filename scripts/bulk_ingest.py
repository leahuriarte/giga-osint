#!/usr/bin/env python3
"""Bulk ingest high-quality sources for knowledge base"""

import sys
import os
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set required env vars
if not os.getenv('GEMINI_API_KEY'):
    os.environ['GEMINI_API_KEY'] = 'your_key_here'

from ingest.html_fetch import fetch_article
from preprocess.clean import clean_text, is_trash
from preprocess.chunk import chunk_with_meta
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store
from preprocess.ner import extract_entities
from index.graph.graph_store import graph_store
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Comprehensive OSINT knowledge base sources
QUALITY_SOURCES = [
    # === CYBERSECURITY & INFORMATION SECURITY ===
    "https://en.wikipedia.org/wiki/Computer_security",
    "https://en.wikipedia.org/wiki/Cybersecurity",
    "https://en.wikipedia.org/wiki/Information_security",
    "https://en.wikipedia.org/wiki/Data_breach",
    "https://en.wikipedia.org/wiki/Cyberattack",
    "https://en.wikipedia.org/wiki/Malware",
    "https://en.wikipedia.org/wiki/Ransomware",
    "https://en.wikipedia.org/wiki/Phishing",
    "https://en.wikipedia.org/wiki/Social_engineering_(security)",
    "https://en.wikipedia.org/wiki/Zero-day_(computing)",
    "https://en.wikipedia.org/wiki/Botnet",
    "https://en.wikipedia.org/wiki/Denial-of-service_attack",
    "https://en.wikipedia.org/wiki/Man-in-the-middle_attack",
    "https://en.wikipedia.org/wiki/SQL_injection",
    "https://en.wikipedia.org/wiki/Cross-site_scripting",
    
    # === APT GROUPS & THREAT ACTORS ===
    "https://en.wikipedia.org/wiki/Advanced_persistent_threat",
    "https://en.wikipedia.org/wiki/Lazarus_Group",
    "https://en.wikipedia.org/wiki/Fancy_Bear",
    "https://en.wikipedia.org/wiki/Cozy_Bear",
    "https://en.wikipedia.org/wiki/Equation_Group",
    "https://en.wikipedia.org/wiki/Comment_Crew",
    "https://en.wikipedia.org/wiki/Carbanak",
    "https://en.wikipedia.org/wiki/Sandworm_(hacker_group)",
    
    # === MAJOR CYBER INCIDENTS ===
    "https://en.wikipedia.org/wiki/Equifax_data_breach",
    "https://en.wikipedia.org/wiki/Yahoo!_data_breaches",
    "https://en.wikipedia.org/wiki/WannaCry_ransomware_attack",
    "https://en.wikipedia.org/wiki/NotPetya_cyberattack",
    "https://en.wikipedia.org/wiki/SolarWinds_hack",
    "https://en.wikipedia.org/wiki/Colonial_Pipeline_cyberattack",
    "https://en.wikipedia.org/wiki/2014_Sony_Pictures_hack",
    "https://en.wikipedia.org/wiki/2016_Democratic_National_Committee_email_leak",
    "https://en.wikipedia.org/wiki/Stuxnet",
    "https://en.wikipedia.org/wiki/Operation_Aurora",
    "https://en.wikipedia.org/wiki/2017_Equifax_data_breach",
    "https://en.wikipedia.org/wiki/Capital_One_data_breach",
    "https://en.wikipedia.org/wiki/Marriott_International_data_breaches",
    
    # === GEOPOLITICS & INTERNATIONAL RELATIONS ===
    "https://en.wikipedia.org/wiki/Geopolitics",
    "https://en.wikipedia.org/wiki/International_relations",
    "https://en.wikipedia.org/wiki/Diplomacy",
    "https://en.wikipedia.org/wiki/Foreign_policy",
    "https://en.wikipedia.org/wiki/National_security",
    "https://en.wikipedia.org/wiki/Intelligence_agency",
    "https://en.wikipedia.org/wiki/Economic_sanctions",
    "https://en.wikipedia.org/wiki/Trade_war",
    "https://en.wikipedia.org/wiki/Cyber_warfare",
    "https://en.wikipedia.org/wiki/Information_warfare",
    "https://en.wikipedia.org/wiki/Hybrid_warfare",
    "https://en.wikipedia.org/wiki/Proxy_war",
    
    # === SUPPLY CHAIN & LOGISTICS ===
    "https://en.wikipedia.org/wiki/Supply_chain",
    "https://en.wikipedia.org/wiki/Supply_chain_management",
    "https://en.wikipedia.org/wiki/Supply_chain_attack",
    "https://en.wikipedia.org/wiki/Supply_chain_security",
    "https://en.wikipedia.org/wiki/Logistics",
    "https://en.wikipedia.org/wiki/Global_supply_chain",
    "https://en.wikipedia.org/wiki/Supply_chain_disruption",
    "https://en.wikipedia.org/wiki/Just-in-time_manufacturing",
    "https://en.wikipedia.org/wiki/Vendor_management",
    "https://en.wikipedia.org/wiki/Third-party_risk_management",
    
    # === ECONOMIC INTELLIGENCE ===
    "https://en.wikipedia.org/wiki/Economic_intelligence",
    "https://en.wikipedia.org/wiki/Economic_espionage",
    "https://en.wikipedia.org/wiki/Industrial_espionage",
    "https://en.wikipedia.org/wiki/Trade_secret",
    "https://en.wikipedia.org/wiki/Intellectual_property_theft",
    "https://en.wikipedia.org/wiki/Corporate_espionage",
    "https://en.wikipedia.org/wiki/Business_intelligence",
    "https://en.wikipedia.org/wiki/Competitive_intelligence",
    "https://en.wikipedia.org/wiki/Market_manipulation",
    "https://en.wikipedia.org/wiki/Insider_trading",
    
    # === CRITICAL INFRASTRUCTURE ===
    "https://en.wikipedia.org/wiki/Critical_infrastructure",
    "https://en.wikipedia.org/wiki/Critical_infrastructure_protection",
    "https://en.wikipedia.org/wiki/Industrial_control_system",
    "https://en.wikipedia.org/wiki/SCADA",
    "https://en.wikipedia.org/wiki/Smart_grid",
    "https://en.wikipedia.org/wiki/Power_grid",
    "https://en.wikipedia.org/wiki/Transportation_security",
    "https://en.wikipedia.org/wiki/Port_security",
    "https://en.wikipedia.org/wiki/Aviation_security",
    "https://en.wikipedia.org/wiki/Maritime_security",
    
    # === TERRORISM & EXTREMISM ===
    "https://en.wikipedia.org/wiki/Terrorism",
    "https://en.wikipedia.org/wiki/Counterterrorism",
    "https://en.wikipedia.org/wiki/Domestic_terrorism",
    "https://en.wikipedia.org/wiki/Cyberterrorism",
    "https://en.wikipedia.org/wiki/Extremism",
    "https://en.wikipedia.org/wiki/Radicalization",
    "https://en.wikipedia.org/wiki/Lone_wolf_attack",
    "https://en.wikipedia.org/wiki/Terrorist_financing",
    
    # === ORGANIZED CRIME ===
    "https://en.wikipedia.org/wiki/Organized_crime",
    "https://en.wikipedia.org/wiki/Transnational_organized_crime",
    "https://en.wikipedia.org/wiki/Cybercrime",
    "https://en.wikipedia.org/wiki/Money_laundering",
    "https://en.wikipedia.org/wiki/Human_trafficking",
    "https://en.wikipedia.org/wiki/Drug_trafficking",
    "https://en.wikipedia.org/wiki/Arms_trafficking",
    "https://en.wikipedia.org/wiki/Financial_crime",
    "https://en.wikipedia.org/wiki/Fraud",
    "https://en.wikipedia.org/wiki/Identity_theft",
    
    # === INTELLIGENCE AGENCIES & METHODS ===
    "https://en.wikipedia.org/wiki/Central_Intelligence_Agency",
    "https://en.wikipedia.org/wiki/National_Security_Agency",
    "https://en.wikipedia.org/wiki/Federal_Bureau_of_Investigation",
    "https://en.wikipedia.org/wiki/MI6",
    "https://en.wikipedia.org/wiki/Mossad",
    "https://en.wikipedia.org/wiki/FSB_(Russia)",
    "https://en.wikipedia.org/wiki/Ministry_of_State_Security_(China)",
    "https://en.wikipedia.org/wiki/HUMINT",
    "https://en.wikipedia.org/wiki/SIGINT",
    "https://en.wikipedia.org/wiki/OSINT",
    "https://en.wikipedia.org/wiki/GEOINT",
    "https://en.wikipedia.org/wiki/MASINT",
    
    # === MAJOR COUNTRIES & REGIONS ===
    "https://en.wikipedia.org/wiki/United_States",
    "https://en.wikipedia.org/wiki/China",
    "https://en.wikipedia.org/wiki/Russia",
    "https://en.wikipedia.org/wiki/European_Union",
    "https://en.wikipedia.org/wiki/NATO",
    "https://en.wikipedia.org/wiki/Middle_East",
    "https://en.wikipedia.org/wiki/Asia-Pacific",
    "https://en.wikipedia.org/wiki/Africa",
    "https://en.wikipedia.org/wiki/Latin_America",
    
    # === CURRENT CONFLICTS & TENSIONS ===
    "https://en.wikipedia.org/wiki/Russo-Ukrainian_War",
    "https://en.wikipedia.org/wiki/China%E2%80%93United_States_trade_war",
    "https://en.wikipedia.org/wiki/Israeli%E2%80%93Palestinian_conflict",
    "https://en.wikipedia.org/wiki/Taiwan_Strait_crisis",
    "https://en.wikipedia.org/wiki/South_China_Sea_disputes",
    "https://en.wikipedia.org/wiki/Iran%E2%80%93United_States_relations",
    "https://en.wikipedia.org/wiki/North_Korea%E2%80%93United_States_relations",
    
    # === TECHNOLOGY & EMERGING THREATS ===
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Quantum_computing",
    "https://en.wikipedia.org/wiki/5G",
    "https://en.wikipedia.org/wiki/Internet_of_things",
    "https://en.wikipedia.org/wiki/Blockchain",
    "https://en.wikipedia.org/wiki/Cryptocurrency",
    "https://en.wikipedia.org/wiki/Deepfake",
    "https://en.wikipedia.org/wiki/Disinformation",
    "https://en.wikipedia.org/wiki/Misinformation",
    
    # === REGULATORY & COMPLIANCE ===
    "https://en.wikipedia.org/wiki/General_Data_Protection_Regulation",
    "https://en.wikipedia.org/wiki/NIST_Cybersecurity_Framework",
    "https://en.wikipedia.org/wiki/ISO_27001",
    "https://en.wikipedia.org/wiki/SOX_compliance",
    "https://en.wikipedia.org/wiki/HIPAA",
    "https://en.wikipedia.org/wiki/PCI_DSS",
    "https://en.wikipedia.org/wiki/FISMA",
    
    # === MAJOR CORPORATIONS & SECTORS ===
    "https://en.wikipedia.org/wiki/Fortune_500",
    "https://en.wikipedia.org/wiki/Big_Tech",
    "https://en.wikipedia.org/wiki/Defense_contractor",
    "https://en.wikipedia.org/wiki/Financial_services",
    "https://en.wikipedia.org/wiki/Healthcare_industry",
    "https://en.wikipedia.org/wiki/Energy_industry",
    "https://en.wikipedia.org/wiki/Telecommunications_industry",
    "https://en.wikipedia.org/wiki/Aerospace_industry",
    "https://en.wikipedia.org/wiki/Pharmaceutical_industry",
    
    # === FRAMEWORKS & METHODOLOGIES ===
    "https://en.wikipedia.org/wiki/MITRE_ATT%26CK",
    "https://en.wikipedia.org/wiki/Common_Vulnerabilities_and_Exposures",
    "https://en.wikipedia.org/wiki/CERT_Coordination_Center",
    "https://en.wikipedia.org/wiki/Threat_intelligence",
    "https://en.wikipedia.org/wiki/Risk_assessment",
    "https://en.wikipedia.org/wiki/Vulnerability_assessment",
    "https://en.wikipedia.org/wiki/Penetration_test",
    "https://en.wikipedia.org/wiki/Red_team",
    "https://en.wikipedia.org/wiki/Blue_team",
    
    # === RECENT HIGH-PROFILE CASES ===
    "https://en.wikipedia.org/wiki/Cambridge_Analytica",
    "https://en.wikipedia.org/wiki/Edward_Snowden",
    "https://en.wikipedia.org/wiki/WikiLeaks",
    "https://en.wikipedia.org/wiki/Panama_Papers",
    "https://en.wikipedia.org/wiki/Paradise_Papers",
    "https://en.wikipedia.org/wiki/Pandora_Papers",
]

# Comprehensive RSS feeds for OSINT
RSS_FEEDS = [
    # === CYBERSECURITY & TECH SECURITY ===
    "https://feeds.feedburner.com/eset/blog",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
    "https://threatpost.com/feed/",
    "https://www.securityweek.com/feed",
    "https://cyberscoop.com/feed/",
    "https://www.scmagazine.com/feed",
    "https://techcrunch.com/category/security/feed/",
    "https://arstechnica.com/security/feed/",
    "https://www.csoonline.com/feed",
    "https://www.infosecurity-magazine.com/rss/news/",
    "https://www.helpnetsecurity.com/feed/",
    "https://www.securitymagazine.com/rss/topic/2236-cyber-security",
    
    # === GLOBAL NEWS & GEOPOLITICS ===
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.washingtonpost.com/arcio/rss/category/world/",
    "https://www.theguardian.com/world/rss",
    "https://feeds.ap.org/ap/worldnews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.ft.com/world?format=rss",
    
    # === BUSINESS & ECONOMICS ===
    "https://feeds.reuters.com/reuters/businessNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.wsj.com/xml/rss/3_7085.xml",
    "https://www.ft.com/companies?format=rss",
    "https://fortune.com/feed/",
    "https://www.forbes.com/real-time/feed2/",
    "https://www.economist.com/rss",
    
    # === SUPPLY CHAIN & LOGISTICS ===
    "https://www.supplychainbrain.com/rss",
    "https://www.logisticsmgmt.com/rss",
    "https://www.inboundlogistics.com/cms/rss/",
    "https://www.supplychaindive.com/feeds/news/",
    "https://www.freightwaves.com/feed",
    "https://www.joc.com/rss.xml",
    "https://www.supplychainquarterly.com/rss",
    
    # === GOVERNMENT & POLICY ===
    "https://www.cisa.gov/news.xml",
    "https://www.fbi.gov/feeds/fbi-news/@@RSS",
    "https://www.dhs.gov/news-releases/rss.xml",
    "https://www.whitehouse.gov/feed/",
    "https://www.state.gov/rss-feeds/",
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945&max=10",
    
    # === INTELLIGENCE & DEFENSE ===
    "https://www.defensenews.com/arc/outboundfeeds/rss/category/cyber/?outputType=xml",
    "https://www.janes.com/feeds/news",
    "https://www.c4isrnet.com/arc/outboundfeeds/rss/",
    "https://breakingdefense.com/feed/",
    "https://www.militarytimes.com/arc/outboundfeeds/rss/",
    
    # === REGIONAL NEWS (MAJOR REGIONS) ===
    # Europe
    "https://www.euronews.com/rss?format=mrss",
    "https://www.politico.eu/feed/",
    "https://www.dw.com/en/rss",
    # Asia-Pacific
    "https://www.scmp.com/rss/91/feed",
    "https://www.straitstimes.com/news/world/rss.xml",
    "https://www.japantimes.co.jp/feed/topstories/",
    # Middle East
    "https://www.haaretz.com/cmlink/1.628752",
    "https://www.timesofisrael.com/feed/",
    "https://english.alarabiya.net/rss.xml",
    
    # === TECHNOLOGY & EMERGING THREATS ===
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.zdnet.com/news/rss.xml",
    "https://www.computerworld.com/index.rss",
    "https://www.infoworld.com/index.rss",
    
    # === FINANCIAL CRIME & COMPLIANCE ===
    "https://www.acfcs.org/feed/",
    "https://www.fincen.gov/rss.xml",
    "https://www.fatf-gafi.org/en/news.rss",
    
    # === ENERGY & CRITICAL INFRASTRUCTURE ===
    "https://www.energy.gov/rss-feeds",
    "https://www.utilitydive.com/feeds/news/",
    "https://www.powermag.com/feed/",
    "https://www.oilandgasjournal.com/rss",
    
    # === HEALTHCARE & PHARMA ===
    "https://www.healthcareinfosecurity.com/rss-feeds",
    "https://www.fiercehealthcare.com/rss/xml",
    "https://www.modernhealthcare.com/rss",
    
    # === TRANSPORTATION & MARITIME ===
    "https://www.maritime-executive.com/rss",
    "https://www.tradewindsnews.com/rss",
    "https://www.flightglobal.com/rss/articles",
    "https://www.railwaygazette.com/rss/news",
    
    # === ACADEMIC & RESEARCH ===
    "https://www.brookings.edu/feed/",
    "https://www.cfr.org/rss-feeds",
    "https://www.csis.org/rss/analysis-and-commentary",
    "https://www.rand.org/content/rand/pubs.rss",
    
    # === LEGAL & REGULATORY ===
    "https://www.law360.com/rss/articles",
    "https://www.jdsupra.com/rss/legalnews/",
    "https://www.lexology.com/rss",
]

async def ingest_url(url: str, source_type: str = "bulk") -> bool:
    """Ingest a single URL"""
    try:
        logger.info(f"📄 Fetching {url[:60]}...")
        
        # Fetch article
        article = fetch_article(url)
        if not article:
            logger.warning(f"❌ Failed to fetch {url}")
            return False
        
        # Clean content
        clean_content = clean_text(article["text"])
        if is_trash(clean_content):
            logger.warning(f"🗑️ Trash content from {url}")
            return False
        
        # Chunk content
        chunks = chunk_with_meta(url, clean_content)
        if not chunks:
            logger.warning(f"📝 No chunks from {url}")
            return False
        
        # Prepare for vector store
        ids, texts, metas = [], [], []
        for cid, ch, idx in chunks:
            ids.append(cid)
            texts.append(ch)
            metas.append({
                "url": article["url"],
                "host": article["host"],
                "doc_id": url,
                "title": url.split('/')[-1].replace('_', ' ').replace('-', ' '),
                "chunk_index": idx,
                "source": source_type
            })
        
        # Embed and store
        embeddings = embed_texts(texts)
        store.upsert(ids=ids, texts=texts, embeddings=embeddings, metadatas=metas)
        
        # Update graph
        for cid, ch, idx in chunks:
            entities = extract_entities(ch)
            if entities:
                graph_store.add_chunk(
                    chunk_id=cid,
                    entities=entities,
                    meta={
                        "url": article["url"],
                        "host": article["host"],
                        "doc_id": url
                    }
                )
        
        logger.info(f"✅ Ingested {len(chunks)} chunks from {url[:40]}...")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error ingesting {url}: {e}")
        return False

async def ingest_rss_feeds():
    """Ingest recent content from RSS feeds"""
    try:
        from ingest.rss import pull_rss
        
        logger.info("📡 Pulling RSS feeds...")
        items = pull_rss(RSS_FEEDS)
        logger.info(f"Found {len(items)} RSS items")
        
        # Ingest recent items (limit to prevent overload)
        success_count = 0
        for item in items[:50]:  # Limit to 50 most recent
            url = item.get("url")
            if url:
                success = await ingest_url(url, "rss")
                if success:
                    success_count += 1
        
        logger.info(f"✅ Successfully ingested {success_count} RSS articles")
        return success_count
        
    except Exception as e:
        logger.error(f"❌ RSS ingestion failed: {e}")
        return 0

async def ingest_batch(urls: list, source_type: str, batch_size: int = 10) -> tuple:
    """Ingest URLs in batches with progress tracking"""
    total_success = 0
    total_attempted = 0
    
    logger.info(f"📦 Processing {len(urls)} {source_type} sources in batches of {batch_size}")
    
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(urls) + batch_size - 1) // batch_size
        
        logger.info(f"🔄 Batch {batch_num}/{total_batches}: Processing {len(batch)} URLs...")
        
        # Process batch concurrently
        tasks = []
        for url in batch:
            task = ingest_url(url, source_type)
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_success = 0
            for result in results:
                total_attempted += 1
                if isinstance(result, Exception):
                    logger.warning(f"❌ Batch error: {result}")
                elif result:
                    total_success += 1
                    batch_success += 1
            
            logger.info(f"✅ Batch {batch_num} complete: {batch_success}/{len(batch)} successful")
            
            # Save progress periodically
            if batch_num % 5 == 0:
                try:
                    graph_store.save()
                    logger.info(f"💾 Progress saved (batch {batch_num})")
                except Exception as e:
                    logger.warning(f"Failed to save progress: {e}")
            
            # Brief pause between batches
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Batch {batch_num} failed: {e}")
            total_attempted += len(batch)
    
    return total_success, total_attempted

async def main():
    """Main bulk ingestion process with massive scale"""
    logger.info("🚀 Starting MASSIVE bulk ingestion...")
    logger.info(f"📊 Scope: {len(QUALITY_SOURCES)} quality sources + {len(RSS_FEEDS)} RSS feeds")
    
    start_time = asyncio.get_event_loop().time()
    
    # Phase 1: Quality sources (Wikipedia, major references)
    logger.info("📚 Phase 1: Ingesting quality sources...")
    quality_success, quality_attempted = await ingest_batch(QUALITY_SOURCES, "quality", batch_size=8)
    
    # Phase 2: RSS feeds (current news and analysis)
    logger.info("📡 Phase 2: Ingesting RSS feeds...")
    rss_success = await ingest_rss_feeds()
    
    # Phase 3: Save and optimize
    logger.info("💾 Phase 3: Saving and optimizing...")
    try:
        graph_store.save()
        logger.info("✅ Graph saved")
    except Exception as e:
        logger.error(f"❌ Failed to save graph: {e}")
    
    # Phase 4: Build RAPTOR hierarchical summaries (optional)
    build_raptor = os.getenv('BUILD_RAPTOR', 'false').lower() == 'true'
    if build_raptor:
        try:
            logger.info("🌳 Phase 4: Building RAPTOR nodes...")
            from index.raptor.builder import RaptorBuilder
            builder = RaptorBuilder()
            builder.build_nodes(topic_hint="osint")
            logger.info("✅ RAPTOR nodes built")
        except Exception as e:
            logger.error(f"❌ RAPTOR build failed: {e}")
    else:
        logger.info("⏭️ Phase 4: Skipping RAPTOR build (set BUILD_RAPTOR=true to enable)")
    
    # Final statistics
    total_time = asyncio.get_event_loop().time() - start_time
    total_success = quality_success + rss_success
    total_attempted = quality_attempted + len(RSS_FEEDS)
    
    logger.info(f"🎯 MASSIVE BULK INGESTION COMPLETE!")
    logger.info(f"   ⏱️  Total time: {total_time / 60:.1f} minutes")
    logger.info(f"   📊 Attempted: {total_attempted} sources")
    logger.info(f"   ✅ Successful: {total_success}")
    logger.info(f"   📈 Success rate: {total_success / max(1, total_attempted) * 100:.1f}%")
    logger.info(f"   🚀 Throughput: {total_success / max(1, total_time / 60):.1f} sources/minute")
    
    # Get final knowledge base stats
    try:
        from discover.knowledge_tracker import knowledge_tracker
        stats = knowledge_tracker.get_current_stats()
        logger.info(f"📊 FINAL KNOWLEDGE BASE:")
        logger.info(f"   📄 Documents: {stats['total_documents']:,}")
        logger.info(f"   📝 Chunks: {stats['total_chunks']:,}")
        logger.info(f"   🏷️  Entities: {stats['total_entities']:,}")
        
        # Estimate knowledge base size
        avg_chunk_size = 800  # rough estimate
        total_chars = stats['total_chunks'] * avg_chunk_size
        total_mb = total_chars / (1024 * 1024)
        logger.info(f"   💾 Estimated size: {total_mb:.1f} MB of text")
        
    except Exception as e:
        logger.warning(f"Failed to get final stats: {e}")
    
    logger.info("🎉 Your OSINT system now has comprehensive global intelligence coverage!")

if __name__ == "__main__":
    asyncio.run(main())