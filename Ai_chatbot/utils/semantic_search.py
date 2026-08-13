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
    chunk_size=450,
    overlap=80
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
    min_score=0.25
):

    if not query or index is None or not chunks:
        print("SEMANTIC SEARCH: Invalid input")
        return ""

    # --------------------------------------------------
    # CREATE QUERY EMBEDDING
    # --------------------------------------------------

    query_vector = model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False
    ).astype("float32")

    faiss.normalize_L2(query_vector)

    # --------------------------------------------------
    # SEARCH
    # --------------------------------------------------

    search_k = min(top_k, len(chunks))

    scores, ids = index.search(
        query_vector,
        search_k
    )

    # --------------------------------------------------
    # DEBUG
    # --------------------------------------------------

    print("=" * 60)
    print("SEMANTIC SEARCH DEBUG")
    print(f"Question: {query}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Top K: {search_k}")
    print(f"Minimum score: {min_score}")
    print("-" * 60)

    results = []
    seen = set()

    best_score = 0.0

    for rank, (score, idx) in enumerate(
        zip(scores[0], ids[0]),
        start=1
    ):

        if idx == -1:
            continue

        chunk = chunks[idx].strip()

        print(f"\nResult #{rank}")
        print(f"Score: {score:.4f}")
        print(f"Chunk ID: {idx}")
        print(f"Accepted: {score >= min_score}")
        print(f"Preview: {chunk[:250]}")

        # Track best score
        best_score = max(
            best_score,
            float(score)
        )

        # --------------------------------------------------
        # FILTER
        # --------------------------------------------------

        if score < min_score:
            continue

        if chunk in seen:
            continue

        seen.add(chunk)

        results.append(chunk)

    print("=" * 60)

    # --------------------------------------------------
    # NO RESULT
    # --------------------------------------------------

    if not results:

        print("SEMANTIC SEARCH RESULT: NO MATCH")
        print(f"Best similarity score: {best_score:.4f}")

        return ""

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    final_context = "\n\n".join(
        results
    ).strip()

    print(
        f"SEMANTIC SEARCH RESULT: "
        f"{len(results)} chunks returned"
    )

    print(
        f"Best similarity score: "
        f"{best_score:.4f}"
    )

    print(
        f"Context length: "
        f"{len(final_context)} characters"
    )

    print("=" * 60)

    return final_context