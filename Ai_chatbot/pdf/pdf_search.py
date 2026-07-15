import re

def find_relevant_text(pdf_text, question):

    # -----------------------------
    # Clean PDF
    # -----------------------------
    pdf_text = re.sub(r"\n{2,}", "\n", pdf_text)

    # -----------------------------
    # Split into paragraphs
    # -----------------------------
    chunks = []

    paragraphs = pdf_text.split("\n\n")

    for para in paragraphs:

        para = para.strip()

        if len(para) > 40:
            chunks.append(para)

    # Fallback
    if len(chunks) < 5:

        lines = [
            x.strip()
            for x in pdf_text.splitlines()
            if x.strip()
        ]

        chunk_size = 15

        chunks = []

        for i in range(0, len(lines), chunk_size):

            chunks.append(
                "\n".join(lines[i:i+chunk_size])
            )

    # -----------------------------
    # Normalize Question
    # -----------------------------
    question = question.lower()

    replacements = {
        "ai": "artificial intelligence",
        "ml": "machine learning",
        "db": "database",
        "powerbi": "power bi"
    }

    for old, new in replacements.items():
        question = question.replace(old, new)

    # -----------------------------
    # Stop Words
    # -----------------------------
    stop_words = {
        "what","is","the","a","an","of",
        "how","many","who","where","when",
        "does","do","are","in","on","for",
        "tell","me","pdf","uploaded",
        "please","can","could","would",
        "give","define","describe",
        "about","from","their","there",
        "this","that"
    }

    question_words = {
        word
        for word in re.findall(r"\w+", question)
        if word not in stop_words
    }

    # -----------------------------
    # Score Chunks
    # -----------------------------
    scored = []

    for chunk in chunks:

        text = chunk.lower()

        score = 0

        # Exact phrase
        if question in text:
            score += 25

        # Individual keywords
        for word in question_words:

            if word in text:
                score += 5

        # Heading bonus
        first_line = chunk.split("\n")[0].lower()

        for word in question_words:

            if word in first_line:
                score += 10

        # Short definition bonus
        if "answer" in text:
            score += 2

        if score > 0:
            scored.append((score, chunk))

    # -----------------------------
    # No Match
    # -----------------------------
    if not scored:
        return ""

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # -----------------------------
    # Take Best Chunks
    # -----------------------------
    result = []

    seen = set()

    for score, chunk in scored:

        if chunk not in seen:

            seen.add(chunk)

            result.append(chunk)

        if len(result) == 3:
            break

    return "\n\n".join(result)[:6000]