"""Index an IFS Build Home into a local ChromaDB vector store."""

import re
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "repdefgen_index"
EMBED_MODEL = "all-MiniLM-L6-v2"
# all-MiniLM-L6-v2 max input tokens is 256; chunks are kept under that.
MAX_CHUNK_CHARS = 900  # ~200 tokens at avg 4.5 chars/token — safe margin


def _get_client(index_dir: Path) -> chromadb.Client:
    index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(index_dir),
        settings=Settings(anonymized_telemetry=False),
    )


def _chunk_view_file(content: str, file_path: Path) -> list[dict]:
    """One chunk per COMMENT ON COLUMN statement, with the preceding column alias line for context."""
    chunks = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not re.match(r"COMMENT\s+ON\s+COLUMN\s+", stripped, re.IGNORECASE):
            continue
        # Include the line immediately before (often the column alias in the SELECT)
        context_line = lines[i - 1].strip() if i > 0 else ""
        chunk_text = f"{context_line}\n{stripped}" if context_line else stripped

        # Extract view.column from COMMENT ON COLUMN view_name.col_name IS ...
        m = re.match(
            r"COMMENT\s+ON\s+COLUMN\s+(\w+)\.(\w+)\s+IS\s+",
            stripped,
            re.IGNORECASE,
        )
        view_name = m.group(1) if m else file_path.stem
        col_name = m.group(2) if m else f"col_{i}"

        chunks.append({
            "text": chunk_text[:MAX_CHUNK_CHARS],
            "file_path": str(file_path),
            "file_type": "view",
            "chunk_type": "column",
            "object_name": f"{view_name}.{col_name}",
        })
    return chunks


def _chunk_api_file(content: str, file_path: Path, file_type: str) -> list[dict]:
    """One chunk per PROCEDURE or FUNCTION definition."""
    chunks = []
    # Split at PROCEDURE/FUNCTION keyword at start of line (after optional whitespace)
    pattern = re.compile(
        r"^(?:PROCEDURE|FUNCTION)\s+(\w+)",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(pattern.finditer(content))
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        chunk_text = content[start:end].strip()
        obj_name = match.group(1)
        chunks.append({
            "text": chunk_text[:MAX_CHUNK_CHARS],
            "file_path": str(file_path),
            "file_type": file_type,
            "chunk_type": "function",
            "object_name": obj_name,
        })
    return chunks


def build_index(build_home: Path, index_dir: Path) -> tuple[int, int]:
    """
    Scan build_home for .api/.apy/.view files, chunk them, embed and store in ChromaDB.
    Returns (file_count, chunk_count).
    """
    model = SentenceTransformer(EMBED_MODEL)
    client = _get_client(index_dir)

    # Drop and recreate collection for a clean rebuild
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    extensions = {".api", ".apy", ".view"}
    files = [p for p in build_home.rglob("*") if p.suffix.lower() in extensions]

    all_chunks: list[dict] = []
    file_count = 0

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  [warn] skipping {file_path}: {e}")
            continue

        ext = file_path.suffix.lower()
        if ext == ".view":
            chunks = _chunk_view_file(content, file_path)
        else:
            file_type = "api" if ext == ".api" else "apy"
            chunks = _chunk_api_file(content, file_path, file_type)

        if chunks:
            all_chunks.extend(chunks)
            file_count += 1

    if not all_chunks:
        return 0, 0

    # Batch upsert
    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        collection.upsert(
            ids=[f"chunk_{i + j}" for j in range(len(batch))],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "file_path": c["file_path"],
                    "file_type": c["file_type"],
                    "chunk_type": c["chunk_type"],
                    "object_name": c["object_name"],
                }
                for c in batch
            ],
        )

    return file_count, len(all_chunks)
