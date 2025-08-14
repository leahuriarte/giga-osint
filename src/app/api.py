from fastapi import APIRouter
from typing import List, Dict, Any
import logging
from app.schemas import IngestRequest, IngestResult, QueryRequest, QueryResult, Hit

logger = logging.getLogger(__name__)
from ingest.rss import pull_rss
from ingest.html_fetch import fetch_article
from preprocess.clean import clean_text, is_trash
from preprocess.chunk import chunk_with_meta
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store
import tldextract
from preprocess.ner import extract_entities
from index.graph.graph_store import graph_store
from synth.verify import verify_brief



router = APIRouter()

def _ingest_urls(urls: List[str]) -> List[Dict[str, Any]]:
    out = []
    for u in urls:
        art = fetch_article(u)
        if not art:
            continue
        out.append({
            "doc_id": u,  # naive id; ok for demo
            "url": art["url"],
            "host": art["host"],
            "title": "",
            "published_at": None,
            "text": art["text"]
        })
    return out

@router.post("/ingest", response_model=IngestResult)
def ingest(req: IngestRequest):
    errors = 0
    docs: List[Dict[str, Any]] = []

    if req.rss_feeds:
        rss_items = pull_rss([str(x) for x in req.rss_feeds])
        for it in rss_items:
            url = it.get("url")
            if not url:
                continue
            art = fetch_article(url)
            if art and not is_trash(art["text"]):
                docs.append({
                    "doc_id": url,
                    "url": art["url"],
                    "host": art["host"],
                    "title": it.get("title",""),
                    "published_at": it.get("published_at"),
                    "source": it.get("source"),
                    "text": art["text"],
                })
            else:
                # fallback: use rss title+summary if page extraction failed
                fallback_text = clean_text(f"{it.get('title','')} — {it.get('summary','')}")
                if is_trash(fallback_text):
                    continue
                host = tldextract.extract(url).registered_domain
                docs.append({
                    "doc_id": url,
                    "url": url,
                    "host": host or "",
                    "title": it.get("title",""),
                    "published_at": it.get("published_at"),
                    "source": it.get("source"),
                    "text": fallback_text,
                })

    if req.urls:
        docs.extend(_ingest_urls([str(x) for x in req.urls]))

    # clean + chunk + upsert
    total_chunks = 0
    for d in docs:
        txt = clean_text(d["text"])
        if is_trash(txt):
            continue
        chunks = chunk_with_meta(d["doc_id"], txt)
        ids = []
        texts = []
        metas = []
        for cid, ch, idx in chunks:
            ids.append(cid)
            texts.append(ch)
            metas.append({
                "url": d["url"],
                "host": d["host"],
                "doc_id": d["doc_id"],
                "title": d.get("title",""),
                "published_at": (d.get("published_at").isoformat() if hasattr(d.get("published_at"), "isoformat") and d.get("published_at") else d.get("published_at")),
                "chunk_index": idx
            })
        embs = embed_texts(texts)
        store.upsert(ids=ids, texts=texts, embeddings=embs, metadatas=metas)
        total_chunks += len(ids)
        # graph updates (entities per chunk)
        for (cid, ch, idx) in chunks:
            ents = extract_entities(ch)
            if ents:
                graph_store.add_chunk(
                    chunk_id=cid,
                    entities=ents,
                    meta={
                        "url": d["url"],
                        "host": d["host"],
                        "doc_id": d["doc_id"]
                    }
                )
        graph_store.save()


    return IngestResult(docs=len(docs), chunks=total_chunks, errors=errors)

# query
from retrieve.hybrid import hybrid_search

@router.post("/query", response_model=QueryResult)
def query(req: QueryRequest):
    hits = hybrid_search(req.q, k=req.k)
    return QueryResult(hits=[Hit(**h) for h in hits])

from fastapi import Query
from index.graph.graph_store import graph_store

@router.get("/entities")
def entities(top: int = Query(20, ge=1, le=100)):
    top_ents = graph_store.top_entities(n=top)
    return {"entities":[{"name":n, **meta} for n,meta in top_ents]}

from synth.brief import make_brief
from app.schemas import QueryRequest

@router.post("/brief")
async def brief(req: QueryRequest):
    # Agent-on-query: ensure corpus is fresh if auto_ingest is enabled
    corpus_result = None
    if req.auto_ingest:
        try:
            from synth.planner import ensure_corpus
            corpus_result = await ensure_corpus(req.q, req.recent_days, req.max_urls)
            logger.info(f"Auto-ingest complete: {corpus_result['ingested']['docs']} docs, {corpus_result['ingested']['chunks']} chunks")
        except Exception as e:
            logger.error(f"Auto-ingest failed: {e}")
            # Continue with existing corpus if auto-ingest fails
    
    # Legacy discovery fallback (if auto_ingest is disabled but discover is enabled)
    discovery_result = None
    if not req.auto_ingest and req.discover:
        try:
            # Use simple RSS discovery instead of complex web discovery
            from discover.rss_discovery import quick_ingest_breaking_news
            discovery_result = await quick_ingest_breaking_news(req.q, max_items=5)
        except Exception as e:
            logger.error(f"RSS discovery failed: {e}")
            # Continue with existing corpus if discovery fails
    
    # Generate brief (with potentially new content from auto-ingest)
    result = make_brief(req.q, k=req.k, expand=req.expand)
    ver = verify_brief(result.get("summary",""), result.get("sources",[]))
    result["verification"] = ver
    
    # Add corpus metadata
    if corpus_result:
        result["corpus_update"] = corpus_result
    
    # Add legacy discovery metadata if used
    if discovery_result:
        result["discovery"] = discovery_result
    
    return result
from index.raptor.builder import RaptorBuilder

@router.post("/raptor/build")
def raptor_build():
    RaptorBuilder().build_nodes(topic_hint="security/osint")
    return {"status":"ok"}

from synth.timeline import make_timeline

@router.post("/timeline")
def timeline(req: QueryRequest):
    return make_timeline(req.q, k=max(20, req.k))

@router.post("/discover")
async def discover_only(req: QueryRequest):
    """Standalone discovery endpoint for testing"""
    try:
        from discover.orchestrator import discovery_orchestrator
        result = await discovery_orchestrator.discover_and_ingest(
            req.q, expand_queries=req.expand, fast_mode=req.fast_mode
        )
        return result
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return {"error": str(e), "discovered_urls": 0, "ingested_docs": 0}

@router.get("/knowledge/status")
def knowledge_status():
    """Get knowledge base growth statistics"""
    try:
        from discover.knowledge_tracker import knowledge_tracker
        return knowledge_tracker.get_growth_summary()
    except Exception as e:
        logger.error(f"Failed to get knowledge status: {e}")
        return {"error": str(e)}

@router.get("/knowledge/stats")
def knowledge_detailed_stats():
    """Get detailed knowledge base statistics"""
    try:
        from discover.knowledge_tracker import knowledge_tracker
        current = knowledge_tracker.get_current_stats()
        recent_history = knowledge_tracker.stats.get("ingestion_history", [])[-20:]  # Last 20 ingestions
        
        return {
            "current_state": current,
            "total_ingestions": knowledge_tracker.stats.get("total_ingestions", 0),
            "recent_ingestions": recent_history,
            "entity_growth": knowledge_tracker.stats.get("entity_growth", [])[-10:],  # Last 10 snapshots
            "knowledge_base_age": knowledge_tracker._get_age_days(),
            "growth_velocity": knowledge_tracker._calculate_growth_velocity()
        }
    except Exception as e:
        logger.error(f"Failed to get detailed knowledge stats: {e}")
        return {"error": str(e)}

from fastapi.responses import PlainTextResponse
from synth.export import brief_to_markdown

@router.post("/export/brief.md")
async def export_brief_md(req: QueryRequest):
    # Run discovery if requested
    if getattr(req, 'discover', True):
        try:
            from discover.orchestrator import discovery_orchestrator
            await discovery_orchestrator.discover_and_ingest(req.q, expand_queries=req.expand, fast_mode=getattr(req, 'fast_mode', True))
        except Exception as e:
            logger.error(f"Discovery failed during export: {e}")
    
    result = make_brief(req.q, k=req.k, expand=req.expand)
    ver = verify_brief(result.get("summary",""), result.get("sources",[]))
    result["verification"] = ver
    md = brief_to_markdown(result)
    # return as downloadable
    headers = {"Content-Disposition": 'attachment; filename="brief.md"'}
    return PlainTextResponse(content=md, headers=headers, media_type="text/markdown")
