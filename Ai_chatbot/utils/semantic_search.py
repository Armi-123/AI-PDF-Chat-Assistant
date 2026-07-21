from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


# =====================================================
# CACHE
# =====================================================

cached_index = None
cached_chunks = None
cached_embeddings = None
cached_pdf_hash = None


# =====================================================
# LOAD EMBEDDING MODEL ONCE
# =====================================================

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# =====================================================
# CREATE CHUNKS
# =====================================================

def create_chunks(
    text,
    chunk_size=700,
    overlap=150
):
    """
    Split PDF text into overlapping chunks.

    Larger chunks give the model more context,
    while overlap prevents important information
    from being cut between chunks.
    """

    if not text:
        return []

    text = text.replace("\r", "")
    text = text.replace("\t", " ")

    # Clean excessive spaces
    text = " ".join(
        text.split()
    )

    chunks = []

    start = 0

    step = chunk_size - overlap

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += step

    return chunks


# =====================================================
# BUILD FAISS INDEX
# =====================================================

def build_index(text):

    global cached_index
    global cached_chunks
    global cached_embeddings
    global cached_pdf_hash

    # ---------------------------------------------
    # Empty PDF
    # ---------------------------------------------

    if not text or not text.strip():

        return None, []


    # ---------------------------------------------
    # Create hash for caching
    # ---------------------------------------------

    pdf_hash = hash(text)


    # ---------------------------------------------
    # Return cached index
    # ---------------------------------------------

    if (
        cached_pdf_hash == pdf_hash
        and cached_index is not None
        and cached_chunks is not None
    ):

        return (
            cached_index,
            cached_chunks
        )


    # ---------------------------------------------
    # Create chunks
    # ---------------------------------------------

    chunks = create_chunks(text)


    if not chunks:

        return None, []


    # ---------------------------------------------
    # Generate embeddings
    # ---------------------------------------------

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        show_progress_bar=False
    )


    # ---------------------------------------------
    # Convert to float32
    # ---------------------------------------------

    embeddings = np.asarray(
        embeddings,
        dtype="float32"
    )


    # ---------------------------------------------
    # Normalize embeddings
    #
    # This allows FAISS Inner Product
    # to behave like cosine similarity.
    # ---------------------------------------------

    faiss.normalize_L2(
        embeddings
    )


    # ---------------------------------------------
    # Create FAISS index
    # ---------------------------------------------

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dimension
    )


    # ---------------------------------------------
    # Add embeddings
    # ---------------------------------------------

    index.add(
        embeddings
    )


    # ---------------------------------------------
    # Save cache
    # ---------------------------------------------

    cached_index = index

    cached_chunks = chunks

    cached_embeddings = embeddings

    cached_pdf_hash = pdf_hash


    return (
        index,
        chunks
    )


# =====================================================
# SEMANTIC SEARCH
# =====================================================

def semantic_search(
    query,
    index,
    chunks,
    top_k=5,
    min_score=0.30
):
    """
    Search PDF chunks using semantic similarity.

    Returns only relevant chunks.

    This prevents unrelated chunks from being
    passed to Gemini as PDF context.
    """

    # ---------------------------------------------
    # Validate input
    # ---------------------------------------------

    if not query:
        return ""


    if index is None:
        return ""


    if not chunks:
        return ""


    # ---------------------------------------------
    # Encode user question
    # ---------------------------------------------

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False
    )


    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )


    # ---------------------------------------------
    # Normalize query
    # ---------------------------------------------

    faiss.normalize_L2(
        query_embedding
    )


    # ---------------------------------------------
    # Search FAISS
    # ---------------------------------------------

    search_k = min(
        top_k,
        len(chunks)
    )


    scores, indices = index.search(
        query_embedding,
        search_k
    )


    # ---------------------------------------------
    # Collect relevant chunks
    # ---------------------------------------------

    results = []

    seen = set()


    for score, idx in zip(
        scores[0],
        indices[0]
    ):

        # Invalid index
        if idx == -1:
            continue


        # Ignore low similarity
        if float(score) < min_score:
            continue


        chunk = chunks[idx].strip()


        if not chunk:
            continue


        # Remove duplicate chunks
        if chunk in seen:
            continue


        seen.add(
            chunk
        )


        results.append(
            chunk
        )


    # ---------------------------------------------
    # Return empty if nothing is relevant
    # ---------------------------------------------

    if not results:

        return ""


    return "\n\n".join(
        results
    )