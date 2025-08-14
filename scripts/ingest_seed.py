import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from app.api import _ingest_urls
from preprocess.clean import clean_text, is_trash
from preprocess.chunk import chunk_with_meta
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store

urls = [
    "https://krebsonsecurity.com/",
    "https://blog.google/threat-analysis-group/",
]

docs = _ingest_urls(urls)
n_chunks = 0
for d in docs:
    txt = clean_text(d["text"])
    if is_trash(txt): 
        continue
    chunks = chunk_with_meta(d["doc_id"], txt)
    ids, texts, metas = [], [], []
    for cid, ch, idx in chunks:
        ids.append(cid); texts.append(ch)
        metas.append({"url": d["url"], "host": d["host"], "doc_id": d["doc_id"], "chunk_index": idx})
    embs = embed_texts(texts)
    store.upsert(ids=ids, texts=texts, embeddings=embs, metadatas=metas)
    n_chunks += len(ids)

print("ingested docs:", len(docs), "chunks:", n_chunks)
