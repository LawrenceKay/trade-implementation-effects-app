"""
Retrieval helper for the trade knowledge base.

Usage (from app code):
    from knowledge_base.retrieve import retrieve
    context = retrieve("How does FTA network centrality affect economic complexity?", k=5)
"""

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

KB_DIR    = Path(__file__).parent
VECTORDB  = KB_DIR / "vectordb"
MODEL_NAME = "all-MiniLM-L6-v2"

_client     = None
_collection = None
_embedder   = None


def _init():
    global _client, _collection, _embedder
    if _collection is None:
        _client     = chromadb.PersistentClient(path=str(VECTORDB))
        _collection = _client.get_or_create_collection("trade_knowledge")
        _embedder   = SentenceTransformer(MODEL_NAME)


def retrieve(query: str, k: int = 5, theme: str | None = None) -> str:
    """
    Return the top-k chunks matching the query as a single formatted string,
    with inline source labels ready to paste into a prompt.

    Args:
        query: Natural-language question or topic.
        k:     Number of chunks to return.
        theme: Optional filter — one of 'fta_networks', 'economic_complexity',
               'agreement_depth'. If None, searches across all themes.
    """
    _init()

    if _collection.count() == 0:
        return "[Knowledge base is empty — run knowledge_base/ingest.py first]"

    query_embedding = _embedder.encode([query]).tolist()
    where = {"theme": theme} if theme else None

    results = _collection.query(
        query_embeddings=query_embedding,
        n_results=min(k, _collection.count()),
        where=where,
        include=["documents", "metadatas"],
    )

    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]

    parts = []
    for chunk, meta in zip(chunks, metadatas):
        label = f"[{meta['authors']}, {meta['year']} — {meta['title']}]"
        parts.append(f"{label}\n{chunk}")

    return "\n\n---\n\n".join(parts)
