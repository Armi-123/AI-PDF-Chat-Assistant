import re
from difflib import SequenceMatcher

from pdf.pdf_utils import (
    extract_pdf_links
)

# =====================================================
# SIMILARITY
# =====================================================

def similarity(a, b):
    """
    Calculate similarity between two strings.
    """

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a.lower(),
        b.lower()
    ).ratio()


# =====================================================
# NORMALIZE TEXT
# =====================================================

def normalize_pdf_text(text):
    """
    Normalize PDF text for searching.
    """

    if not text:
        return ""

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# =====================================================
# NORMALIZE QUESTION
# =====================================================

def normalize_question(question):
    """
    Normalize user question.
    """

    if not question:
        return ""

    question = question.lower().strip()

    replacements = {
        "powerbi": "power bi",
        "power-bi": "power bi",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "db": "database",
    }

    for old, new in replacements.items():

        question = re.sub(
            rf"\b{re.escape(old)}\b",
            new,
            question
        )

    return question


# =====================================================
# STOP WORDS
# =====================================================

STOP_WORDS = {
    "what",
    "is",
    "the",
    "a",
    "an",
    "of",
    "how",
    "many",
    "who",
    "where",
    "when",
    "does",
    "do",
    "are",
    "in",
    "on",
    "for",
    "tell",
    "me",
    "pdf",
    "uploaded",
    "please",
    "can",
    "could",
    "would",
    "give",
    "define",
    "describe",
    "about",
    "from",
    "their",
    "there",
    "this",
    "that",
    "show",
    "list",
    "explain",
    "candidate",
    "candidates",
    "person",
    "profile",
    "mentioned",
    "included",
    "listed",
}


# =====================================================
# DIRECT QUESTION TYPE
# =====================================================

def detect_direct_query(question):
    """
    Detect important direct PDF questions.

    Returns:
    - email
    - phone
    - linkedin
    - github
    - certifications
    - name
    - None
    """

    q = normalize_question(
        question
    )

    # Email
    if any(
        phrase in q
        for phrase in [
            "email",
            "email address",
            "email id",
            "mail id",
            "mail address",
        ]
    ):
        return "email"

    # Phone
    if any(
        phrase in q
        for phrase in [
            "phone",
            "phone number",
            "mobile",
            "mobile number",
            "contact number",
            "contact no",
            "telephone",
        ]
    ):
        return "phone"

    # LinkedIn
    if "linkedin" in q:
        return "linkedin"

    # GitHub
    if (
        "github" in q
        or "git hub" in q
    ):
        return "github"

    # Certifications
    if any(
        phrase in q
        for phrase in [
            "certification",
            "certifications",
            "certificate",
            "certificates",
        ]
    ):
        return "certifications"

    # Name
    if (
        "candidate name" in q
        or "candidate's name" in q
        or "person name" in q
        or "person's name" in q
        or "what is the name" in q
        or "who is the candidate" in q
        or "who is the person" in q
    ):
        return "name"

    return None


# =====================================================
# EMAIL SEARCH
# =====================================================

def find_email(pdf_text):
    """
    Find email addresses in PDF text.
    """

    if not pdf_text:
        return ""

    emails = re.findall(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        pdf_text
    )

    unique = []

    seen = set()

    for email in emails:

        email = email.strip()

        if email.lower() not in seen:

            seen.add(
                email.lower()
            )

            unique.append(
                email
            )

    return "\n".join(
        unique
    )


# =====================================================
# PHONE SEARCH
# =====================================================

def find_phone(pdf_text):
    """
    Find Indian and international phone numbers.

    Supports formats such as:

    (+91) 70968 70759
    +91 70968 70759
    +91-7096870759
    70968 70759
    7096870759
    """

    if not pdf_text:
        return ""

    patterns = [

        # (+91) 70968 70759
        r"\(\s*\+91\s*\)\s*\d{5}\s*\d{5}",

        # +91 70968 70759
        r"\+91[\s-]*\d{5}[\s-]*\d{5}",

        # +91-7096870759
        r"\+91[\s-]*[6-9]\d{9}",

        # 70968 70759
        r"\b[6-9]\d{4}[\s-]\d{5}\b",

        # 7096870759
        r"\b[6-9]\d{9}\b",
    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            pdf_text
        )

        for phone in matches:

            phone = phone.strip()

            # Normalize spaces
            phone = re.sub(
                r"\s+",
                " ",
                phone
            )

            if phone not in found:

                found.append(
                    phone
                )

    return "\n".join(
        found
    )


# =====================================================
# LINK SEARCH
# =====================================================

def find_social_links(
    pdf_file,
    pdf_text=""
):
    """
    Find LinkedIn and GitHub URLs.

    Priority:
    1. Hidden PDF hyperlink annotations
    2. Visible URLs inside extracted text
    """

    result = {
        "linkedin": [],
        "github": [],
    }

    # =================================================
    # HIDDEN PDF LINKS
    # =================================================

    try:

        pdf_links = extract_pdf_links(
            pdf_file
        )

        result["linkedin"].extend(
            pdf_links.get(
                "linkedin",
                []
            )
        )

        result["github"].extend(
            pdf_links.get(
                "github",
                []
            )
        )

    except Exception as e:

        print(
            "Social Link Extraction Error:",
            e
        )

    # =================================================
    # VISIBLE URL SEARCH
    # =================================================

    urls = re.findall(
        r"https?://[^\s<>\"]+",
        pdf_text or "",
        re.IGNORECASE
    )

    for url in urls:

        url = url.rstrip(
            ".,;:!?)]}>"
        )

        lower_url = url.lower()

        if "linkedin.com" in lower_url:

            if url not in result[
                "linkedin"
            ]:

                result[
                    "linkedin"
                ].append(
                    url
                )

        elif "github.com" in lower_url:

            if url not in result[
                "github"
            ]:

                result[
                    "github"
                ].append(
                    url
                )

    return result


# =====================================================
# NAME SEARCH
# =====================================================

def find_candidate_name(pdf_text):
    """
    Extract candidate name from the beginning
    of resume text.
    """

    if not pdf_text:
        return ""

    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    ignored = {
        "resume",
        "cv",
        "curriculum vitae",
        "summary",
        "profile",
        "contact",
        "education",
        "skills",
        "experience",
        "projects",
        "certifications",
    }

    # Check first 15 lines
    for line in lines[:15]:

        lower = line.lower()

        if lower in ignored:
            continue

        if "@" in line:
            continue

        if "linkedin" in lower:
            continue

        if "github" in lower:
            continue

        if "http://" in lower:
            continue

        if "https://" in lower:
            continue

        # Skip phone/contact line
        if re.search(
            r"\d{5}\s*\d{5}",
            line
        ):
            continue

        # Name-like pattern
        if re.fullmatch(
            r"[A-Za-z]+(?:\s+[A-Za-z]+){1,4}",
            line
        ):

            words = line.split()

            if 2 <= len(words) <= 5:

                return line

    return ""


# =====================================================
# CERTIFICATION SEARCH
# =====================================================

def find_certifications(pdf_text):
    """
    Find certification section.

    If the PDF does not contain a certification
    section or certification content, return an
    explicit message.
    """

    if not pdf_text:

        return (
            "No certifications are mentioned "
            "in the uploaded PDF."
        )

    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    certification_heading_patterns = [

        r"^certifications?$",

        r"^certificates?$",

        r"^professional certifications?$",

        r"^certification[s]?\s*&\s*licenses?$",

    ]

    start_index = None

    for i, line in enumerate(lines):

        lower_line = line.lower()

        for pattern in certification_heading_patterns:

            if re.fullmatch(
                pattern,
                lower_line,
                re.IGNORECASE
            ):

                start_index = i

                break

        if start_index is not None:
            break

    # No certification section
    if start_index is None:

        return (
            "No certifications are mentioned "
            "in the uploaded PDF."
        )

    # =================================================
    # EXTRACT SECTION
    # =================================================

    next_sections = {
        "summary",
        "education",
        "skills",
        "experience",
        "projects",
        "achievements",
        "contact",
    }

    result = []

    for i in range(
        start_index + 1,
        len(lines)
    ):

        line = lines[i].strip()

        if not line:
            continue

        if line.lower() in next_sections:

            break

        result.append(
            line
        )

    if not result:

        return (
            "No certifications are mentioned "
            "in the uploaded PDF."
        )

    return "\n".join(
        result
    )


# =====================================================
# DIRECT PDF SEARCH
# =====================================================

def find_direct_pdf_answer(
    pdf_text,
    question,
    pdf_files=None
):
    

    """
    Search direct factual questions from PDF.

    Returns:
    - Exact direct answer when found
    - Explicit certification message
    - Empty string when not found
    """

    if not question:
        return ""

    pdf_text = normalize_pdf_text(
        pdf_text
    )

    query_type = detect_direct_query(
        question
    )

    # =================================================
    # EMAIL
    # =================================================

    if query_type == "email":

        return find_email(
            pdf_text
        )

    # =================================================
    # PHONE
    # =================================================

    if query_type == "phone":

        return find_phone(
            pdf_text
        )

    # =================================================
    # LINKEDIN
    # =================================================

    if query_type == "linkedin":

        links = find_social_links(
            pdf_files,
            pdf_text
        )

        if links["linkedin"]:

            return "\n".join(
                links["linkedin"]
            )

        return ""

    # =================================================
    # GITHUB
    # =================================================

    if query_type == "github":

        links = find_social_links(
            pdf_files,
            pdf_text
        )

        if links["github"]:

            return "\n".join(
                links["github"]
            )

        return ""

    # =================================================
    # CERTIFICATIONS
    # =================================================

    if query_type == "certifications":

        return find_certifications(
            pdf_text
        )

    # =================================================
    # NAME
    # =================================================

    if query_type == "name":

        return find_candidate_name(
            pdf_text
        )

    return ""


# =====================================================
# GENERIC KEYWORD SEARCH
# =====================================================

def find_relevant_text(
    pdf_text,
    question
):
    """
    Find relevant PDF chunks for general questions.

    Used after direct factual searches.
    """

    pdf_text = normalize_pdf_text(
        pdf_text
    )

    question = normalize_question(
        question
    )

    if not pdf_text or not question:
        return ""

    # -------------------------------------------------
    # Split PDF into chunks
    # -------------------------------------------------

    chunks = []

    paragraphs = pdf_text.split(
        "\n\n"
    )

    for para in paragraphs:

        para = para.strip()

        if len(para) > 40:

            chunks.append(
                para
            )

    # -------------------------------------------------
    # Fallback chunks
    # -------------------------------------------------

    if len(chunks) < 5:

        lines = [
            line.strip()
            for line in pdf_text.splitlines()
            if line.strip()
        ]

        chunk_size = 15

        chunks = []

        for i in range(
            0,
            len(lines),
            chunk_size
        ):

            chunk = "\n".join(
                lines[
                    i:i + chunk_size
                ]
            )

            if chunk:

                chunks.append(
                    chunk
                )

    if not chunks:
        return ""

    # -------------------------------------------------
    # Question words
    # -------------------------------------------------

    question_words = [
        word
        for word in re.findall(
            r"\w+",
            question
        )
        if (
            word not in STOP_WORDS
            and len(word) > 1
        )
    ]

    if not question_words:
        return ""

    question_phrase = " ".join(
        question_words
    )

    # -------------------------------------------------
    # Score chunks
    # -------------------------------------------------

    scored = []

    for chunk in chunks:

        text = chunk.lower()

        score = 0

        # Exact question
        if question in text:

            score += 40

        # Exact phrase
        if (
            question_phrase
            and question_phrase in text
        ):

            score += 25

        # Heading
        first_line = (
            chunk
            .split("\n")[0]
            .lower()
        )

        if (
            question_phrase
            and question_phrase in first_line
        ):

            score += 30

        # Keyword scoring
        for word in question_words:

            if word in text:

                score += 8

            else:

                # Only compare against unique
                # tokens to reduce unnecessary work

                tokens = set(
                    re.findall(
                        r"\w+",
                        text
                    )
                )

                for token in tokens:

                    if (
                        similarity(
                            word,
                            token
                        ) >= 0.90
                    ):

                        score += 3

                        break

        # Definition bonus
        if "definition" in text:

            score += 3

        if "defined as" in text:

            score += 3

        if score >= 10:

            scored.append(
                (
                    score,
                    chunk
                )
            )

    # -------------------------------------------------
    # Nothing found
    # -------------------------------------------------

    if not scored:

        return ""

    # -------------------------------------------------
    # Sort
    # -------------------------------------------------

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # -------------------------------------------------
    # Return best chunks
    # -------------------------------------------------

    result = []

    used = set()

    for score, chunk in scored:

        if chunk in used:
            continue

        used.add(
            chunk
        )

        result.append(
            chunk
        )

        if len(result) >= 3:

            break

    return "\n\n".join(
        result
    )[:6000]