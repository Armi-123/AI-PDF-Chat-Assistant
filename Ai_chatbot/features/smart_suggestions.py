import re
from collections import Counter

from pdf.pdf_utils import extract_pdf_text


# =====================================================
# STOP WORDS
# =====================================================

STOP_WORDS = {
    "the", "and", "for", "that", "this", "with",
    "from", "into", "about", "have", "will",
    "their", "there", "your", "what", "when",
    "where", "which", "whose", "while", "been",
    "being", "are", "was", "were", "can", "could",
    "would", "should", "shall", "may", "might",
    "also", "than", "then", "them", "they",
    "you", "our", "his", "her", "its", "not",
    "all", "any", "each", "other", "some",
    "using", "used", "use", "over",
    "more", "most", "very", "much",
    "pdf", "page", "chapter", "section",
    "answer", "question"
}


# =====================================================
# EXTRACT IMPORTANT TOPICS
# =====================================================

def extract_topics(
    pdf_text,
    top_n=8
):
    """
    Extract meaningful topics from PDF text.

    Uses frequently occurring words while
    ignoring common stop words.
    """

    if not pdf_text:
        return []

    text = pdf_text.lower()

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9+#.\-]{2,}",
        text
    )

    filtered_words = [
        word
        for word in words
        if word not in STOP_WORDS
    ]

    counts = Counter(
        filtered_words
    )

    topics = []

    for word, frequency in counts.most_common():

        if frequency >= 2:

            topic = word.title()

            if topic not in topics:

                topics.append(
                    topic
                )

        if len(topics) >= top_n:
            break

    return topics


# =====================================================
# GENERATE DYNAMIC SUGGESTIONS
# =====================================================

def generate_suggestions(
    pdf_text,
    max_suggestions=5
):
    """
    Generate dynamic questions based on
    the actual uploaded PDF content.

    Returns only 3-5 useful suggestions.
    """

    if not pdf_text:
        return ""

    text = pdf_text.lower()

    suggestions = []

    # -------------------------------------------------
    # ALWAYS INCLUDE SUMMARY
    # -------------------------------------------------

    suggestions.append(
        "📋 Summarize this PDF"
    )

    # -------------------------------------------------
    # DETECT DOCUMENT TYPE
    # -------------------------------------------------

    is_resume = any(
        keyword in text
        for keyword in [
            "resume",
            "curriculum vitae",
            "experience",
            "education",
            "skills",
            "internship",
            "projects"
        ]
    )

    has_projects = (
        "project" in text
        or "projects" in text
    )

    has_experience = (
        "experience" in text
        or "internship" in text
        or "intern" in text
    )

    has_skills = (
        "skills" in text
        or "technologies" in text
        or "technical skills" in text
    )

    has_education = (
        "education" in text
        or "university" in text
        or "college" in text
        or "degree" in text
    )

    # -------------------------------------------------
    # RESUME-BASED DYNAMIC QUESTIONS
    # -------------------------------------------------

    if is_resume:

        if has_experience:

            suggestions.append(
                "👨‍💼 What experience or internships are mentioned?"
            )

        if has_projects:

            suggestions.append(
                "📂 What projects are included?"
            )

        if has_skills:

            suggestions.append(
                "🛠 What technical skills are listed?"
            )

        if has_education:

            suggestions.append(
                "🎓 What is the education background?"
            )

    # -------------------------------------------------
    # GENERAL DOCUMENT QUESTIONS
    # -------------------------------------------------

    else:

        suggestions.extend([
            "📖 What is the main topic?",
            "⭐ What are the most important points?",
            "📝 What are the key concepts?",
            "💡 Explain the important topics"
        ])

    # -------------------------------------------------
    # TOPIC-BASED QUESTIONS
    # -------------------------------------------------

    topics = extract_topics(
        pdf_text,
        top_n=8
    )

    # Add only useful topic questions
    for topic in topics:

        # Avoid very short or generic topics
        if len(topic) < 4:
            continue

        suggestion = (
            f"💬 Explain {topic}"
        )

        if suggestion not in suggestions:

            suggestions.append(
                suggestion
            )

        if len(suggestions) >= max_suggestions:

            break

    # -------------------------------------------------
    # REMOVE DUPLICATES
    # -------------------------------------------------

    unique_suggestions = []

    for suggestion in suggestions:

        if suggestion not in unique_suggestions:

            unique_suggestions.append(
                suggestion
            )

    # -------------------------------------------------
    # RETURN ONLY 3-5 SUGGESTIONS
    # -------------------------------------------------

    return "\n".join(
        unique_suggestions[
            :max_suggestions
        ]
    )


# =====================================================
# LOAD SUGGESTIONS FROM PDF
# =====================================================

def load_suggestions(
    pdf_files
):
    """
    Extract text from uploaded PDFs
    and generate dynamic suggestions.
    """

    if not pdf_files:

        return ""

    pdf_text = ""

    # -------------------------------------------------
    # EXTRACT PDF TEXT
    # -------------------------------------------------

    for pdf in pdf_files:

        try:

            text = extract_pdf_text(
                pdf
            )

            if text:

                pdf_text += (
                    "\n\n"
                    + text
                )

        except Exception as e:

            print(
                f"Suggestion extraction failed: "
                f"{e}"
            )

    # -------------------------------------------------
    # VALIDATE PDF TEXT
    # -------------------------------------------------

    pdf_text = pdf_text.strip()

    if not pdf_text:

        return ""

    # -------------------------------------------------
    # LIMIT TEXT SIZE
    # -------------------------------------------------

    pdf_text = pdf_text[
        :50000
    ]

    # -------------------------------------------------
    # GENERATE SUGGESTIONS
    # -------------------------------------------------

    return generate_suggestions(
        pdf_text,
        max_suggestions=5
    )
