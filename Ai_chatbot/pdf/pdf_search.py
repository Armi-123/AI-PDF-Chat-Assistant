import re

def find_relevant_text(pdf_text, question):

    # -----------------------------
    # Clean PDF
    # -----------------------------
    pdf_text = re.sub(r"\r", "", pdf_text)
    pdf_text = re.sub(r"[ \t]+", " ", pdf_text)
    pdf_text = re.sub(r"\n{2,}", "\n\n", pdf_text)
    pdf_text = pdf_text.strip()

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
        "powerbi": "power bi",
        "power-bi": "power bi",
        "excel sheet": "excel",
        "sql join": "join",
        "joins": "join",
        "analyst": "data analyst"
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
        "this","that","explain","show","list"
    }

    question_words = {
        word
        for word in re.findall(r"\w+", question)
        if word not in stop_words
    }
    
    question_phrase = " ".join(question_words)

    # -----------------------------
    # Score Chunks
    # -----------------------------
    scored = []

    for chunk in chunks:

        text = chunk.lower()

        score = 0

        # Exact question match
        if question in text:
            score += 25

        # Important keyword phrase match
        if question_phrase and question_phrase in text:
            score += 20

        # Individual keywords
        for word in question_words:

            if word in text:
                score += 5

        # Heading bonus
        first_line = chunk.split("\n")[0].lower()

        if question in first_line:
            score += 50

        for word in question_words:

            if word in first_line:
                score += 10
                
        # Short definition bonus
        if "answer" in text:
            score += 2

        if score >= 8:
            scored.append((score, chunk))

    # -----------------------------
    # No Match
    # -----------------------------
    if not scored:
        return ""

    scored = sorted(
        scored,
        key=lambda x: (x[0], len(x[1])),
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

        if len(result) == 2:
            break

    return "\n\n".join(result)[:6000]