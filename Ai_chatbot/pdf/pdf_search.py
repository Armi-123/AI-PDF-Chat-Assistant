import re
from difflib import SequenceMatcher
from pdf.pdf_utils import (
    extract_pdf_links,
    get_pdf_title,
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
            "phone number",
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
    question,
    pdf_content,
    pdf_files=None
):
    """
    Find exact answers directly from uploaded PDF content.

    Supports:
    - Email
    - Phone number
    - LinkedIn URL
    - GitHub URL
    - Candidate name
    - Certifications
    - Projects
    - Education
    - Internships
    - Technical skills

    pdf_files is optional and is kept for compatibility
    with the chatbot's existing function calls.
    """

    if not question or not pdf_content:
        return ""

    question_lower = question.lower().strip()

    # =================================================
    # EMAIL
    # =================================================

    if any(keyword in question_lower for keyword in [
        "email",
        "email address",
        "email id",
        "mail id"
    ]):

        emails = re.findall(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            pdf_content
        )

        if emails:
            return "\n".join(
                dict.fromkeys(emails)
            )

    # =================================================
    # PHONE
    # =================================================

    if any(keyword in question_lower for keyword in [
        "phone",
        "mobile",
        "contact number",
        "phone number"
    ]):

        phones = re.findall(
            r"(?:\(\+91\)|\+91)?[\s-]*[6-9]\d{4}[\s-]?\d{5}",
            pdf_content
        )

        if phones:
            return "\n".join(f"(+91) {a} {b}"for a, b in phones)

    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in question_lower:

        linkedin_links = re.findall(
            r"https?://(?:www\.)?linkedin\.com/[^\s\)\]>]+",
            pdf_content,
            re.IGNORECASE
        )

        if linkedin_links:
            return "\n".join(
                dict.fromkeys(
                    link.rstrip(".,;")
                    for link in linkedin_links
                )
            )

        if re.search(
            r"\blinkedin\b",
            pdf_content,
            re.IGNORECASE
        ):
            return (
                "LinkedIn is mentioned in the uploaded PDF, "
                "but the actual LinkedIn profile URL is not provided."
            )

        return ""

    # =================================================
    # GITHUB
    # =================================================

    if "github" in question_lower:

        github_links = re.findall(
            r"https?://(?:www\.)?github\.com/[^\s\)\]>]+",
            pdf_content,
            re.IGNORECASE
        )

        if github_links:
            return "\n".join(
                dict.fromkeys(
                    link.rstrip(".,;")
                    for link in github_links
                )
            )

        if re.search(
            r"\bgithub\b",
            pdf_content,
            re.IGNORECASE
        ):
            return (
                "GitHub is mentioned in the uploaded PDF, "
                "but the actual GitHub profile URL is not provided."
            )

        return ""

    # =================================================
    # CANDIDATE NAME
    # =================================================

    if any(keyword in question_lower for keyword in [
        "candidate name",
        "candidate's name",
        "person name",
        "person's name",
        "who is the candidate",
        "what is the candidate name",
        "what is the candidate's name",
        "what is the name",
        "who is the person"
    ]):

        # Try PDF title first
        try:

            title = get_pdf_title(
                pdf_content
            )

            if (
                title
                and title != "Unknown PDF"
                and not title.lower().endswith(".pdf")
            ):
                return title.strip()

        except Exception:
            pass

        # Try first meaningful line
        lines = [
            line.strip()
            for line in pdf_content.splitlines()
            if line.strip()
        ]

        invalid_names = {
            "resume",
            "curriculum vitae",
            "cv",
            "summary",
            "profile",
            "contact",
            "education",
            "skills",
            "experience",
            "projects"
        }

        for line in lines[:15]:

            if line.lower() in invalid_names:
                continue

            if "@" in line:
                continue

            if "linkedin" in line.lower():
                continue

            if "github" in line.lower():
                continue

            if re.search(
                r"https?://",
                line,
                re.IGNORECASE
            ):
                continue

            if re.fullmatch(
                r"[\d\s\+\-\(\)]+",
                line
            ):
                continue

            # Name should contain 2–5 words
            # and only alphabetic characters
            if re.fullmatch(
                r"[A-Za-z]+(?:[\s]+[A-Za-z]+){1,4}",
                line
            ):

                return line

    # =================================================
    # PROJECTS
    # =================================================

    if (
        "project" in question_lower
        or "projects" in question_lower
    ):

        project_section = re.search(
            r"Projects\s*(.*?)(?=\n(?:Education|Experience|Skills|Certifications|Certifications & Awards|$))",
            pdf_content,
            re.IGNORECASE | re.DOTALL
        )

        if project_section:
            return project_section.group(1).strip()

    # =================================================
    # EDUCATION
    # =================================================

    if (
        "education" in question_lower
        or "educational background" in question_lower
        or "degree" in question_lower
    ):

        education_section = re.search(
            r"Education\s*(.*?)(?=\n(?:Skills|Experience|Projects|Certifications|Summary|Contact|$))",
            pdf_content,
            re.I | re.S,
        )

        if education_section:
            return education_section.group(1).strip()

    # =================================================
    # INTERNSHIPS / EXPERIENCE
    # =================================================

    if (
        "internship" in question_lower
        or "internships" in question_lower
        or "experience" in question_lower
        or "work experience" in question_lower
    ):

        experience_section = re.search(
            r"Experience\s*(.*?)(?=\n(?:Projects|Education|Skills|Certifications|$))",
            pdf_content,
            re.IGNORECASE | re.DOTALL
        )

        if experience_section:
            return experience_section.group(1).strip()

    # =================================================
    # CERTIFICATIONS
    # =================================================

    if (
        "certification" in question_lower
        or "certifications" in question_lower
        or "certificate" in question_lower
        or "certificates" in question_lower
    ):

        certification_section = re.search(
            r"Certifications?(?:\s*&\s*Awards)?\s*(.*?)(?=\n(?:Projects|Education|Skills|Experience|$))",
            pdf_content,
            re.IGNORECASE | re.DOTALL
        )

        if certification_section:

            result = certification_section.group(1).strip()

            if result:
                return result

        return "No certifications are mentioned in the uploaded PDF."

    # =================================================
    # TECHNICAL SKILLS
    # =================================================

    if any(
        keyword in question_lower
        for keyword in (
            "technical skills",
            "skills",
            "technologies",
            "technology",
            "tools",
        )
    ):

        skills_section = re.search(
            r"Skills(?:\s*/\s*Technologies)?\s*(.*?)(?=\n(?:Experience|Projects|Education|Certifications|Summary|Contact|$))",
            pdf_content,
            re.IGNORECASE | re.DOTALL,
        )

        if skills_section:

            skills = skills_section.group(1).strip()

            # Format bullet points
            skills = re.sub(
                r"\s*•\s*",
                "\n• ",
                skills,
            )

            # Put category values on next line
            skills = re.sub(
                r"([A-Za-z/& ]+):",
                r"\1:\n",
                skills,
            )

            # Remove extra blank lines
            skills = re.sub(
                r"\n{3,}",
                "\n\n",
                skills,
            )

            return skills.strip()
    
    # =================================================
    # NO DIRECT ANSWER
    # =================================================

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
    
# =====================================================
# LOCAL PDF ANSWER
# =====================================================

def answer_from_pdf(question, context):

    q = question.lower()

    # =================================================
    # NAME
    # =================================================

    if any(word in q for word in [
        "name",
        "who am i",
        "my name"
    ]):

        match = re.search(
            r"^\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+)",
            context,
            re.MULTILINE
        )

        if match:
            return f"Your name is {match.group(1).strip()}."


    # =================================================
    # EMAIL
    # =================================================

    if any(word in q for word in [
        "email",
        "email address",
        "mail"
    ]):

        match = re.search(
            r"[\w.+-]+@[\w.-]+\.\w+",
            context
        )

        if match:
            return f"Your email is {match.group(0)}."


    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in q:

        match = re.search(
            r"https?://(?:www\.)?linkedin\.com/in/[^\s]+",
            context,
            re.IGNORECASE
        )

        if match:
            return f"Your LinkedIn profile is:\n{match.group(0)}"


    # =================================================
    # GITHUB
    # =================================================

    if "github" in q:

        match = re.search(
            r"https?://(?:www\.)?github\.com/[^\s]+",
            context,
            re.IGNORECASE
        )

        if match:
            return f"Your GitHub profile is:\n{match.group(0)}"


    # =================================================
    # CGPA
    # =================================================

    if "cgpa" in q:

        match = re.search(
            r"CGPA\s*[:|]?\s*([\d.]+)",
            context,
            re.IGNORECASE
        )

        if match:
            return f"Your CGPA is {match.group(1)}."


    # =================================================
    # EDUCATION / DEGREE
    # =================================================

    if any(word in q for word in [
        "education",
        "degree",
        "qualification"
    ]):

        match = re.search(
            r"(B\.Tech in Computer Engineering\s*\|\s*CGPA\s*[:|]?\s*[\d.]+)",
            context,
            re.IGNORECASE
        )

        if match:
            return f"Your education is {match.group(1).strip()}."


    # =================================================
    # SKILLS
    # =================================================

    if any(word in q for word in [
        "skills",
        "technologies",
        "technical skills",
        "tech skills"
    ]):

        # Extract everything from Skills until Experience
        match = re.search(
            r"Skills\s+(.*?)(?=\s+Experience\b)",
            context,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            skills_text = match.group(1).strip()

            # Clean PDF extraction formatting
            skills_text = re.sub(
                r"\s+",
                " ",
                skills_text
            )

            return (
                "Your technical skills include:\n\n"
                + skills_text
            )


    # =================================================
    # EXPERIENCE / WORK
    # =================================================

    if any(word in q for word in [
        "experience",
        "worked",
        "work",
        "internship",
        "internships",
        "companies"
    ]):

        # Extract Experience section
        match = re.search(
            r"Experience\s+(.*?)(?=\s+Projects\b)",
            context,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            experience_text = match.group(1).strip()

            experience_text = re.sub(
                r"\s+",
                " ",
                experience_text
            )

            return (
                "Your experience includes:\n\n"
                + experience_text
            )


    # =================================================
    # PROJECTS
    # =================================================

    if any(word in q for word in [
        "projects",
        "project",
        "built",
        "developed"
    ]):

        # Exact known project names
        project_names = re.findall(
            r"Retail Sales Analytics Dashboard|"
            r"Customer Churn Prediction|"
            r"Customer Sentiment Analysis System",
            context,
            re.IGNORECASE
        )

        if project_names:

            unique_projects = []
            seen = set()

            for project in project_names:

                clean_project = project.strip()

                key = clean_project.lower()

                if key not in seen:

                    seen.add(key)

                    unique_projects.append(
                        clean_project
                    )

            return (
                "Your projects include:\n\n"
                + "\n".join(
                    f"• {project}"
                    for project in unique_projects
                )
            )


    # =================================================
    # NO LOCAL ANSWER
    # =================================================

    return None