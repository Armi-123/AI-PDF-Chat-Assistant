import re
from difflib import SequenceMatcher


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def find_relevant_text(pdf_text, question):

    # -----------------------------
    # Clean PDF
    # -----------------------------
    pdf_text = re.sub(r"\r", "", pdf_text)
    pdf_text = re.sub(r"[ \t]+", " ", pdf_text)
    pdf_text = re.sub(r"\n{2,}", "\n\n", pdf_text)
    pdf_text = pdf_text.strip()

    # -----------------------------
    # Split PDF into chunks
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
            line.strip()
            for line in pdf_text.splitlines()
            if line.strip()
        ]

        chunk_size = 15

        chunks = []

        for i in range(0, len(lines), chunk_size):

            chunks.append(
                "\n".join(lines[i:i + chunk_size])
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
        "joins": "join"
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
        "this","that","show","list",
        "explain"
    }

    question_words = [
        word
        for word in re.findall(r"\w+", question)
        if word not in stop_words
    ]

    question_phrase = " ".join(question_words)

    # -----------------------------
    # Score chunks
    # -----------------------------
    scored = []

    for chunk in chunks:

        text = chunk.lower()

        score = 0

        # Exact question
        if question in text:
            score += 35

        # Phrase
        if question_phrase and question_phrase in text:
            score += 25

        # Heading
        first_line = chunk.split("\n")[0].lower()

        if question_phrase in first_line:
            score += 30

        # Keywords
        for word in question_words:

            if word in text:
                score += 8

            # Fuzzy word match
            else:

                for token in re.findall(r"\w+", text):

                    if similarity(word, token) > 0.90:

                        score += 4
                        break

        # Definition bonus
        if "answer" in text:
            score += 3

        if "definition" in text:
            score += 3

        if score >= 10:
            scored.append((score, chunk))

    # -----------------------------
    # Nothing found
    # -----------------------------
    if not scored:
        return ""

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # -----------------------------
    # Best chunks
    # -----------------------------
    result = []

    used = set()

    for score, chunk in scored:

        if chunk not in used:

            used.add(chunk)

            result.append(chunk)

        if len(result) == 3:
            break

    return "\n\n".join(result)[:6000]