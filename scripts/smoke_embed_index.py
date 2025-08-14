import uuid
from models.embeddings import embed_texts
from index.vectorstore.chroma_store import store_singleton as store

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
docs = [
    ("doc1", "acme corp was breached last friday by a ransomware group called foobar."),
    ("doc2", "the foobar collective posted stolen acme data on their leaks site."),
    ("doc3", "meanwhile, contoso released a new security patch for their vpn appliance.")
]

ids = [d[0] for d in docs]
texts = [d[1] for d in docs]
embs = embed_texts(texts)
store.upsert(ids=ids, texts=texts, embeddings=embs, metadatas=[{"source":"smoke"}]*len(ids))

q = "which group attacked acme?"
q_emb = embed_texts([q])
res = store.query(query_embeddings=q_emb, k=2)

print("query:", q)
for i,(doc,meta) in enumerate(zip(res["documents"][0], res["metadatas"][0])):
    print(f"hit {i+1}:", doc, "|", meta)
