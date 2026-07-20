import re
from collections import Counter

from pdf.pdf_utils import extract_pdf_text


def extract_topics(pdf_text, top_n=12):
    """
    Extract important topics dynamically from PDF.
    """

    text = pdf_text.lower()

    stop_words = {
        "the", "and", "for", "that", "this", "with",
        "from", "into", "about", "have", "will",
        "their", "there", "your", "what", "when",
        "where", "which", "whose", "while", "been",
        "being", "are", "was", "were", "can", "could",
        "would", "should", "shall", "may", "might",
        "also", "than", "then", "them", "they",
        "you", "our", "his", "her", "its", "not",
        "all", "any", "each", "other", "some",
        "using", "used", "use", "into", "over",
        "more", "most", "very", "much",
        "pdf", "page", "chapter", "section",
        "answer", "question"
    }

    words = re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}", text)

    words = [
        word for word in words
        if word not in stop_words
    ]

    counts = Counter(words)

    topics = []

    for word, freq in counts.most_common():

        if freq >= 2:
            topics.append(word.title())

        if len(topics) >= top_n:
            break

    return topics


def generate_suggestions(pdf_text):

    suggestions = [
        "📋 Summarize this PDF",
        "📖 What is the main topic?",
        "⭐ List important points"
    ]

    text = pdf_text.lower()

    # Resume Suggestions
    if "resume" in text or "experience" in text:

        suggestions.extend([
            "👨‍💼 What internships are mentioned?",
            "📂 What projects are included?",
            "🛠 What technical skills are listed?",
            "🎓 What is the education background?",
            "🏆 What certifications are mentioned?",
            "📊 What tools does the candidate know?"
        ])

    # Technical / Study Material Suggestions
    elif (
        "python" in text
        or "sql" in text
        or "machine learning" in text
        or "power bi" in text
        or "excel" in text
    ):

        suggestions.extend([
            "💡 Explain the important concepts",
            "📚 What are the important definitions?",
            "📝 List interview questions",
            "⭐ List key topics"
        ])

    topics = extract_topics(pdf_text)

    for topic in topics:

        suggestions.extend([
            f"💬 Explain {topic}",
            f"💬 Tell me about {topic}",
            f"💬 What skills are related to {topic}?"
        ])

    # Remove duplicates while preserving order
    unique = []

    for suggestion in suggestions:

        if suggestion not in unique:
            unique.append(suggestion)

    # Maximum 20 suggestions
    return "\n".join(unique[:20])


def load_suggestions(pdf_files):

    if not pdf_files:
        return ""

    pdf_text = ""

    for pdf in pdf_files:

        try:

            text = extract_pdf_text(pdf)

            if text:
                pdf_text += "\n\n" + text

        except Exception as e:

            print(f"Suggestion Error ({pdf}):", e)

    if not pdf_text.strip():
        return ""

    # Limit text size for faster processing
    pdf_text = pdf_text[:50000]

    return generate_suggestions(pdf_text)