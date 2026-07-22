import re
from difflib import SequenceMatcher


# =====================================================
# CONFIGURATION
# =====================================================

MAX_RESULTS = 3
MAX_RESULT_LENGTH = 8000


# =====================================================
# TEXT SIMILARITY
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
# CLEAN TEXT
# =====================================================

def clean_search_text(text):
    """
    Clean PDF text while preserving useful
    line and paragraph structure.
    """

    if not text:
        return ""

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = text.replace(
        "\t",
        " "
    )

    # Remove excessive spaces
    text = re.sub(
        r"[ ]{2,}",
        " ",
        text
    )

    # Remove excessive blank lines
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
    Normalize user question for better matching.
    """

    if not question:
        return ""

    question = question.lower().strip()

    replacements = {

        "powerbi": "power bi",

        "power-bi": "power bi",

        "power bi": "power bi",

        "machine learning":
            "machine learning",

        "ml":
            "machine learning",

        "artificial intelligence":
            "artificial intelligence",

        "ai":
            "artificial intelligence",

        "database":
            "database",

        "db":
            "database",

        "technologies":
            "technology",

        "tools":
            "tool",

        "skills":
            "skill",

        "internships":
            "internship",

        "projects":
            "project",

        "certifications":
            "certification",

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
    "to",
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
    "person",
    "mentioned",
    "included",
    "listed",
    "know",
}


# =====================================================
# QUESTION KEYWORDS
# =====================================================

def extract_question_keywords(question):
    """
    Extract meaningful keywords from the question.
    """

    words = re.findall(
        r"[a-zA-Z0-9]+",
        question.lower()
    )

    keywords = []

    for word in words:

        if word in STOP_WORDS:
            continue

        if len(word) <= 2:
            continue

        if word not in keywords:

            keywords.append(
                word
            )

    return keywords


# =====================================================
# SECTION DETECTION
# =====================================================

SECTION_ALIASES = {

    "skills": [

        "skills",
        "technical skills",
        "skill",
        "technologies",
        "programming skills",
        "technical skill",
    ],

    "tools": [

        "tools",
        "tools platforms",
        "tools & platforms",
        "tools and platforms",
        "software tools",
        "platforms",
    ],

    "education": [

        "education",
        "educational background",
        "academic background",
        "degree",
        "qualification",
    ],

    "experience": [

        "experience",
        "work experience",
        "professional experience",
        "internship",
        "internships",
    ],

    "projects": [

        "projects",
        "project",
        "project experience",
        "projects included",
        "projects listed",
    ],

    "certifications": [

        "certifications",
        "certification",
        "certificates",
        "certificate",
    ],

    "summary": [

        "summary",
        "profile",
        "professional summary",
        "objective",
    ],
}


# =====================================================
# DETECT TARGET SECTION
# =====================================================

def detect_target_section(question):
    """
    Detect whether the question is asking about
    a specific PDF section.
    """

    question = question.lower()

    # Tools should be checked before skills
    # because tools questions may also contain
    # words such as "skills".

    for section in [
        "tools",
        "education",
        "projects",
        "experience",
        "certifications",
        "skills",
        "summary",
    ]:

        for keyword in SECTION_ALIASES[section]:

            if keyword in question:

                return section

    return None


# =====================================================
# FIND SECTION BOUNDARIES
# =====================================================

def find_section_content(
    pdf_text,
    target_section
):
    """
    Extract content belonging to a specific
    PDF section.
    """

    if not pdf_text:
        return ""

    if not target_section:
        return ""

    lines = pdf_text.splitlines()

    start_index = None

    # -------------------------------------------------
    # Find section start
    # -------------------------------------------------

    for index, line in enumerate(lines):

        clean_line = line.strip().lower()

        if not clean_line:
            continue

        for alias in SECTION_ALIASES[
            target_section
        ]:

            alias = alias.lower()

            # Exact heading
            if clean_line == alias:

                start_index = index

                break

            # Heading with colon
            if clean_line.startswith(
                alias + ":"
            ):

                start_index = index

                break

        if start_index is not None:

            break

    if start_index is None:

        return ""

    # -------------------------------------------------
    # Major section headings
    # -------------------------------------------------

    all_sections = []

    for aliases in SECTION_ALIASES.values():

        all_sections.extend(
            aliases
        )

    # -------------------------------------------------
    # Collect section content
    # -------------------------------------------------

    result = []

    for index in range(
        start_index,
        len(lines)
    ):

        line = lines[index].strip()

        if not line:
            continue

        # Skip original heading?
        # Keep it because Gemini understands
        # the context better.

        if index > start_index:

            lower_line = line.lower()

            is_next_section = False

            for section_name in all_sections:

                section_name = section_name.lower()

                if (
                    lower_line == section_name
                    or lower_line.startswith(
                        section_name + ":"
                    )
                ):

                    is_next_section = True

                    break

            if is_next_section:

                break

        result.append(
            line
        )

    return "\n".join(
        result
    ).strip()


# =====================================================
# BUILD SEARCH CHUNKS
# =====================================================

def build_chunks(pdf_text):
    """
    Split PDF text into searchable chunks.
    """

    if not pdf_text:
        return []

    paragraphs = pdf_text.split(
        "\n\n"
    )

    chunks = []

    # -------------------------------------------------
    # Paragraph chunks
    # -------------------------------------------------

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if len(paragraph) >= 40:

            chunks.append(
                paragraph
            )

    # -------------------------------------------------
    # Fallback line chunks
    # -------------------------------------------------

    if len(chunks) < 5:

        lines = [

            line.strip()

            for line in pdf_text.splitlines()

            if line.strip()

        ]

        chunk_size = 12

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

    return chunks


# =====================================================
# SCORE CHUNK
# =====================================================

def score_chunk(
    chunk,
    question,
    keywords,
    target_section=None
):
    """
    Calculate relevance score for a PDF chunk.
    """

    if not chunk:
        return 0

    text = chunk.lower()

    score = 0

    # =================================================
    # EXACT QUESTION
    # =================================================

    if question and question in text:

        score += 40

    # =================================================
    # KEYWORDS
    # =================================================

    matched_keywords = 0

    for keyword in keywords:

        if keyword in text:

            score += 10

            matched_keywords += 1

        else:

            # Fuzzy matching
            tokens = re.findall(
                r"\w+",
                text
            )

            for token in tokens:

                if similarity(
                    keyword,
                    token
                ) >= 0.90:

                    score += 3

                    break

    # =================================================
    # MULTIPLE KEYWORD MATCH
    # =================================================

    if (
        len(keywords) > 0
        and matched_keywords == len(keywords)
    ):

        score += 25

    # =================================================
    # FIRST LINE / HEADING
    # =================================================

    first_line = (
        chunk
        .split("\n")[0]
        .lower()
    )

    for keyword in keywords:

        if keyword in first_line:

            score += 15

    # =================================================
    # TARGET SECTION BONUS
    # =================================================

    if target_section:

        section_keywords = (
            SECTION_ALIASES[
                target_section
            ]
        )

        for section_keyword in section_keywords:

            if section_keyword in text:

                score += 20

                break

    # =================================================
    # CONTENT BONUS
    # =================================================

    if any(
        word in text
        for word in [
            "python",
            "sql",
            "machine learning",
            "education",
            "experience",
            "project",
            "skills",
            "tools",
        ]
    ):

        score += 2

    return score


# =====================================================
# MAIN PDF SEARCH
# =====================================================

def find_relevant_text(
    pdf_text,
    question
):
    """
    Find the most relevant text from PDF.

    IMPORTANT:
    Correct argument order is:

        find_relevant_text(
            pdf_text,
            question
        )

    Returns:
        Relevant PDF text
        or empty string if nothing relevant found.
    """

    if not pdf_text:

        return ""

    if not question:

        return ""

    # =================================================
    # CLEAN PDF
    # =================================================

    pdf_text = clean_search_text(
        pdf_text
    )

    # =================================================
    # NORMALIZE QUESTION
    # =================================================

    question = normalize_question(
        question
    )

    # =================================================
    # EXTRACT KEYWORDS
    # =================================================

    keywords = extract_question_keywords(
        question
    )

    if not keywords:

        return ""

    # =================================================
    # TARGET SECTION
    # =================================================

    target_section = detect_target_section(
        question
    )

    # =================================================
    # SECTION-AWARE SEARCH
    # =================================================

    if target_section:

        section_text = find_section_content(
            pdf_text,
            target_section
        )

        if section_text:

            return section_text[
                :MAX_RESULT_LENGTH
            ]

    # =================================================
    # BUILD CHUNKS
    # =================================================

    chunks = build_chunks(
        pdf_text
    )

    if not chunks:

        return ""

    # =================================================
    # SCORE CHUNKS
    # =================================================

    scored = []

    for chunk in chunks:

        score = score_chunk(

            chunk,

            question,

            keywords,

            target_section

        )

        if score >= 10:

            scored.append(
                (
                    score,
                    chunk
                )
            )

    # =================================================
    # NOTHING FOUND
    # =================================================

    if not scored:

        return ""

    # =================================================
    # SORT
    # =================================================

    scored.sort(

        key=lambda item:
        item[0],

        reverse=True

    )

    # =================================================
    # RETURN BEST RESULTS
    # =================================================

    results = []

    used = set()

    for score, chunk in scored:

        chunk_key = chunk.strip()

        if chunk_key in used:

            continue

        used.add(
            chunk_key
        )

        results.append(
            chunk
        )

        if len(results) >= MAX_RESULTS:

            break

    return "\n\n".join(
        results
    )[
        :MAX_RESULT_LENGTH
    ]