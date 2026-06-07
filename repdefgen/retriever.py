"""Query the ChromaDB Codebase Index for relevant code chunks."""

from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from repdefgen.indexer import COLLECTION_NAME, EMBED_MODEL


def query(
    field_names: list[str],
    description: str,
    index_dir: Path,
    n: int = 8,
) -> list[dict]:
    """
    Embed a combined query of field names + description and return top-n chunks.
    Each result is a dict with keys: text, file_path, file_type, chunk_type, object_name.
    """
    client = chromadb.PersistentClient(
        path=str(index_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(COLLECTION_NAME)

    query_text = description + " " + " ".join(field_names)
    model = SentenceTransformer(EMBED_MODEL)
    embedding = model.encode([query_text])[0].tolist()

    actual_n = min(n, collection.count())
    if actual_n < 1:
        return []

    results = collection.query(
        query_embeddings=[embedding],
        n_results=actual_n,
        include=["documents", "metadatas"],
    )

    chunks = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        chunks.append({
            "text": doc,
            "file_path": meta.get("file_path", ""),
            "file_type": meta.get("file_type", ""),
            "chunk_type": meta.get("chunk_type", ""),
            "object_name": meta.get("object_name", ""),
        })
    return chunks
