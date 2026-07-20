from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


# =====================================================
# CACHE
# =====================================================

cached_index = None
cached_chunks = None
cached_pdf_hash = None


# =====================================================
# LOAD MODEL (Only once)
# =====================================================

model = SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# CREATE CHUNKS
# =====================================================

def create_chunks(text, chunk_size=500, overlap=100):
    """
    Split PDF text into overlapping chunks.
    """

    text = text.replace("\r", "")
    text = text.replace("\t", " ")

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk)

        start += (chunk_size - overlap)

    return chunks


# =====================================================
# BUILD FAISS INDEX
# =====================================================

def build_index(text):

    global cached_index
    global cached_chunks
    global cached_pdf_hash

    pdf_hash = hash(text)

    # Return cached index if PDF hasn't changed
    if cached_pdf_hash == pdf_hash:

        return cached_index, cached_chunks

    chunks = create_chunks(text)

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        show_progress_bar=False
    )

    embeddings = np.array(
        embeddings,
        dtype="float32"
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)

    cached_index = index
    cached_chunks = chunks
    cached_pdf_hash = pdf_hash

    return index, chunks


# =====================================================
# SEMANTIC SEARCH
# =====================================================

def semantic_search(query, index, chunks, top_k=3):
    """
    Search the most relevant chunks using FAISS.
    """

    if index is None:
        return ""

    if not chunks:
        return ""

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True
    )

    query_embedding = np.array(
        query_embedding,
        dtype="float32"
    )

    distances, indices = index.search(
        query_embedding,
        top_k
    )

    results = []

    for idx in indices[0]:

        if idx != -1:

            results.append(chunks[idx])

    return "\n\n".join(results)