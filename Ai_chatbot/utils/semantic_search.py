from sentence_transformers import SentenceTransformer
import faiss
import numpy as np


# Cache
cached_index = None
cached_chunks = None
cached_pdf_hash = None

# Load embedding model once
model = SentenceTransformer("all-MiniLM-L6-v2")


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

        start += chunk_size - overlap

    return chunks


def build_index(text):

    global cached_index
    global cached_chunks
    global cached_pdf_hash

    pdf_hash = hash(text)

    # Return cached index if PDF is unchanged
    if cached_pdf_hash == pdf_hash:

        return cached_index, cached_chunks

    chunks = create_chunks(text)

    embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        show_progress_bar=False
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(np.array(embeddings).astype("float32"))

    cached_index = index
    cached_chunks = chunks
    cached_pdf_hash = pdf_hash

    return index, chunks