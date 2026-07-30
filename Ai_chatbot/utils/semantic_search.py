from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# ==========================================================
# LOAD MODEL (ONLY ONCE)
# ==========================================================

model = SentenceTransformer("all-MiniLM-L6-v2")

# ==========================================================
# CACHE
# ==========================================================

_cached_hash = None
_cached_index = None
_cached_chunks = None

# ==========================================================
# CREATE TEXT CHUNKS
# ==========================================================

def create_chunks(
    text,
    chunk_size=700,
    overlap=150
):

    if not text:
        return []

    text = " ".join(
        text.replace("\r", "")
            .replace("\t", " ")
            .split()
    )

    chunks = []

    step = chunk_size - overlap

    for start in range(
        0,
        len(text),
        step
    ):

        chunk = text[
            start:start + chunk_size
        ].strip()

        if chunk:

            chunks.append(chunk)

    return chunks


# ==========================================================
# BUILD INDEX
# ==========================================================

def build_index(pdf_text):

    global _cached_hash
    global _cached_index
    global _cached_chunks

    if not pdf_text:

        return None, []

    pdf_hash = hash(pdf_text)

    if (
        pdf_hash == _cached_hash
        and _cached_index is not None
    ):

        return (
            _cached_index,
            _cached_chunks
        )

    chunks = create_chunks(pdf_text)

    if not chunks:

        return None, []

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        show_progress_bar=False
    )

    embeddings = embeddings.astype("float32")

    faiss.normalize_L2(
        embeddings
    )

    index = faiss.IndexFlatIP(
        embeddings.shape[1]
    )

    index.add(
        embeddings
    )

    _cached_hash = pdf_hash
    _cached_index = index
    _cached_chunks = chunks

    return (
        index,
        chunks
    )


# ==========================================================
# SEMANTIC SEARCH
# ==========================================================

def semantic_search(
    index,
    chunks,
    query,
    top_k=5,
    min_score=0.30
):

    if (
        not query
        or index is None
        or not chunks
    ):
        return ""

    query_vector = model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False
    ).astype("float32")

    faiss.normalize_L2(
        query_vector
    )

    scores, ids = index.search(
        query_vector,
        min(
            top_k,
            len(chunks)
        )
    )

    results = []

    for score, idx in zip(
        scores[0],
        ids[0]
    ):

        if idx == -1:
            continue

        if score < min_score:
            continue

        results.append(
            chunks[idx]
        )

    return "\n\n".join(results)