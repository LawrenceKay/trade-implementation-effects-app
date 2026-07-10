"""
Ingest documents from knowledge_base/raw/ into ChromaDB.

Usage:
    conda activate trade-app && python knowledge_base/ingest.py
    conda activate trade-app && python knowledge_base/ingest.py --reset   # wipe and re-ingest
"""

import argparse
import csv
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

KB_DIR    = Path(__file__).parent
VECTORDB  = KB_DIR / "vectordb"
SOURCES   = KB_DIR / "sources.csv"

CHUNK_TOKENS   = 500   # approximate — we split on words
OVERLAP_TOKENS = 50
MODEL_NAME     = "all-MiniLM-L6-v2"


def load_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str, chunk_size: int = CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[str]:
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def main(reset: bool = False) -> None:
    client     = chromadb.PersistentClient(path=str(VECTORDB))
    embedder   = SentenceTransformer(MODEL_NAME)

    if reset:
        try:
            client.delete_collection("trade_knowledge")
            print("Existing collection deleted.")
        except Exception:
            pass

    collection = client.get_or_create_collection("trade_knowledge")

    with open(SOURCES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        doc_id   = row["id"]
        doc_path = KB_DIR / row["file"]

        if not doc_path.exists():
            print(f"  SKIP {doc_id} — file not found: {doc_path}")
            continue

        # Check if already ingested (any chunk with this doc_id prefix)
        existing = collection.get(where={"doc_id": doc_id}, limit=1)
        if existing["ids"] and not reset:
            print(f"  SKIP {doc_id} — already in collection")
            continue

        print(f"  Ingesting {doc_id} …", end=" ", flush=True)
        text   = load_pdf_text(doc_path)
        chunks = chunk_text(text)

        ids        = [f"{doc_id}__{i}" for i in range(len(chunks))]
        embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()
        metadatas  = [
            {
                "doc_id":  doc_id,
                "authors": row["authors"],
                "year":    row["year"],
                "title":   row["title"],
                "theme":   row["theme"],
            }
            for _ in chunks
        ]

        collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        print(f"{len(chunks)} chunks.")

    print(f"\nDone. Collection size: {collection.count()} chunks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe and re-ingest all documents")
    args = parser.parse_args()
    main(reset=args.reset)
