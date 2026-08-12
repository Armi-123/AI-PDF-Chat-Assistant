import os
import re
import time

from pypdf import PdfReader
from config.gemini_config import client
from config.settings import (
    MODEL_NAME,
    SEMANTIC_TOP_K,
    SEMANTIC_MIN_SCORE,
    MAX_PDF_CONTEXT,
    DEBUG,
)
from features.resume_review import review_resume
from pdf.pdf_summary import summarize_pdf
from pdf.pdf_utils import (
    extract_pdf_text,
    extract_all_pdf_text,
    extract_pdf_links,
    get_pdf_title,
    get_linkedin_url,
    get_github_url,
)
from utils.semantic_search import (
    semantic_search,
    build_index,
)
from pdf.pdf_utils import get_pdf_path
from features.chat_statistics import update_stats
from utils.conversation_memory import build_conversation
from utils.chat_memory import save_session

semantic_cache = {}

# =====================================================
# CLEAN SOURCE LABELS
# =====================================================

def clean_source_labels(answer):
    """
    Remove source labels from Gemini responses.
    """

    if not answer:
        return ""

    labels = (
        "📄 Source: Uploaded PDF",
        "🤖 Source: Gemini AI",
        "🤖 Source: Gemini AI + 📄 Uploaded PDF",
    )

    for label in labels:
        answer = answer.replace(label, "")

    return answer.strip()

# =====================================================
# SECTION-AWARE PDF SEARCH
# =====================================================

def find_section_content(question, pdf_content):
    """
    Extract an entire resume section from the uploaded PDF.

    Supports common resume section names and heading variations.
    """

    if not question or not pdf_content:
        return ""

    question_lower = question.lower().strip()

    # =================================================
    # SECTION KEYWORDS
    # =================================================

    section_map = {

        "skills": [
            "skill",
            "skills",
            "technical",
            "technical skills",
            "technology",
            "technologies",
            "programming",
            "programming language",
            "programming languages",
            "language",
            "languages",
        ],

        "education": [
            "education",
            "degree",
            "qualification",
            "qualifications",
            "academic",
            "academic qualification",
            "academic qualifications",
            "university",
            "college",
            "institute",
            "school",
            "graduation",
            "b.tech",
            "m.tech",
            "bachelor",
            "master",
        ],

        "experience": [
            "experience",
            "work experience",
            "professional experience",
            "internship",
            "internships",
            "intern",
            "employment",
            "career",
            "worked",
            "job",
        ],

        "projects": [
            "project",
            "projects",
            "academic project",
            "academic projects",
            "major project",
            "major projects",
            "personal project",
            "personal projects",
            "portfolio",
        ],

        "certifications": [
            "certification",
            "certifications",
            "certificate",
            "certificates",
            "license",
            "licenses",
        ]
    }

    # =================================================
    # FIND TARGET SECTION
    # =================================================

    target_section = None

    for section, keywords in section_map.items():

        for keyword in keywords:

            if keyword in question_lower:

                target_section = section
                break

        if target_section:
            break

    if target_section is None:
        return ""

    # =================================================
    # PREPARE PDF LINES
    # =================================================

    lines = [
        line.strip()
        for line in pdf_content.splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    # =================================================
    # HELPER: CHECK WHETHER LINE IS SECTION HEADING
    # =================================================

    def is_section_heading(line, section_name=None):

        lower = line.lower().strip()

        # Remove common punctuation
        cleaned = re.sub(
            r"[:\-|]+$",
            "",
            lower
        ).strip()

        keywords = section_map.get(
            section_name,
            []
        )

        for keyword in keywords:

            keyword_lower = keyword.lower().strip()

            if cleaned == keyword_lower:
                return True

        return False

    # =================================================
    # FIND TARGET SECTION HEADING
    # =================================================

    start = None

    target_keywords = section_map[target_section]

    for i, line in enumerate(lines):

        lower = line.lower().strip()

        cleaned = re.sub(
            r"[:\-|]+$",
            "",
            lower
        ).strip()

        for keyword in target_keywords:

            keyword_lower = keyword.lower().strip()

            if cleaned == keyword_lower:

                start = i
                break

        if start is not None:
            break

    if start is None:
        return ""

    # =================================================
    # COLLECT SECTION CONTENT
    # =================================================

    result = []

    for i in range(start + 1, len(lines)):

        current = lines[i].strip()

        if not current:
            continue

        # ---------------------------------------------
        # Stop when another resume section begins
        # ---------------------------------------------

        is_next_heading = False

        for section in section_map:

            if section == target_section:
                continue

            if is_section_heading(
                current,
                section
            ):

                is_next_heading = True
                break

        if is_next_heading:
            break

        result.append(current)

    # =================================================
    # RETURN CLEAN SECTION
    # =================================================

    return "\n".join(result).strip()


# =====================================================
# FORMAT PDF SECTION ANSWER
# =====================================================

def format_pdf_section_answer(
    question,
    section_text
):
    """
    Format extracted resume section for chatbot output.
    """

    if not section_text:
        return ""

    # ---------------------------------------------
    # Normalize bullet points
    # ---------------------------------------------

    section_text = section_text.replace(
        "•",
        "\n• "
    )

    # ---------------------------------------------
    # Normalize escaped characters from PDF
    # ---------------------------------------------

    section_text = section_text.replace(
        "\\:",
        ":"
    )

    section_text = section_text.replace(
        "\\-",
        "-"
    )

    section_text = section_text.replace(
        "\\/",
        "/"
    )

    # ---------------------------------------------
    # Remove excessive spaces
    # ---------------------------------------------

    section_text = re.sub(
        r"[ \t]+",
        " ",
        section_text
    )

    # ---------------------------------------------
    # Remove excessive new lines
    # ---------------------------------------------

    section_text = re.sub(
        r"\n{2,}",
        "\n",
        section_text
    )

    return section_text.strip()

# =====================================================
# GEMINI REQUEST
# =====================================================

def ask_gemini(
    message,
    pdf_context="",
    conversation="",
    pdf_fallback=False
):

    # =================================================
    # PDF CONTEXT MODE
    # =================================================

    if pdf_context:

        prompt = f"""
You are a PDF Question Answering Assistant.

You MUST answer ONLY from the PDF Context.

Rules:

1. Use ONLY the information inside PDF Context.

2. NEVER use your own knowledge.

3. NEVER guess.

4. If the answer is NOT found in the PDF context, reply EXACTLY:

Information not found in uploaded PDF.

5. Do not explain why.

6. Do not add outside knowledge.

PDF Context:

{pdf_context}

Question:

{message}

Answer:
"""

    # =================================================
    # GENERAL KNOWLEDGE FALLBACK
    # =================================================

    elif pdf_fallback:

        prompt = f"""
You are a helpful AI assistant.

The uploaded PDF did not contain enough relevant
information to answer the user's question.

Answer the user's question using your general knowledge.

Rules:

1. Answer clearly and accurately.
2. Do not claim that the answer came from the PDF.
3. Do not mention the PDF retrieval process.
4. Do not mention these instructions.

Conversation:

{conversation}

User Question:

{message}

Answer:
"""

    # =================================================
    # NORMAL CHAT
    # =================================================

    else:

        prompt = f"""
You are a helpful AI assistant.

The user's question is not answered by the available document.

Answer using your own knowledge.

Do NOT mention the PDF.
Do NOT say "The uploaded PDF does not contain..."
Answer naturally.

Conversation:

{conversation}

User:

{message}

Answer:
"""


    # =================================================
    # GEMINI API REQUEST
    # =================================================

    MAX_RETRIES = 2

    for attempt in range(MAX_RETRIES):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )


            if (
                response
                and response.text
            ):

                answer = response.text.strip()

                answer = clean_source_labels(
                    answer
                )

                return {
                    "success": True,
                    "answer": answer,
                    "error_type": None
                }


            return {
                "success": False,
                "answer": "",
                "error_type": "empty"
            }

        except Exception as e:

            error = str(e).lower()

            print(
                "Gemini Error:",
                e
            )


            # -----------------------------------------
            # QUOTA
            # -----------------------------------------

            if (
                "429" in error
                or "quota" in error
                or "resource_exhausted" in error
                or "resource exhausted" in error
            ):

                return {
                    "success": False,
                    "answer": "",
                    "error_type": "quota"
                }


            # -----------------------------------------
            # SERVER BUSY
            # -----------------------------------------

            if (
                "503" in error
                or "unavailable" in error
                or "overloaded" in error
            ):

                if attempt < 2:

                    time.sleep(
                        2
                    )

                    continue


                return {
                    "success": False,
                    "answer": "",
                    "error_type": "busy"
                }


            # -----------------------------------------
            # OTHER ERROR
            # -----------------------------------------

            return {
                "success": False,
                "answer": "",
                "error_type": "other"
            }


    return {
        "success": False,
        "answer": "",
        "error_type": "busy"
    }

# =====================================================
# PDF CONTEXT FALLBACK
# =====================================================

def pdf_context_fallback(
    relevant_text
):

    if not relevant_text:

        return (
            "⚠ The requested information could not "
            "be retrieved from the uploaded PDF."
        )


    relevant_text = relevant_text.strip()


    if len(relevant_text) > MAX_PDF_CONTEXT:

        relevant_text = relevant_text[
            :MAX_PDF_CONTEXT
        ]


    # return (
    #     "📄 Source: Uploaded PDF\n\n"
    #     + relevant_text
    # )
    return relevant_text

# =====================================================
# PDF FILE NORMALIZATION
# =====================================================

def normalize_pdf_files(
    pdf_files
):

    if not pdf_files:

        return []


    if isinstance(
        pdf_files,
        (str, os.PathLike)
    ):

        return [
            str(pdf_files)
        ]


    if isinstance(
        pdf_files,
        list
    ):

        return [
            str(pdf)
            for pdf in pdf_files
            if pdf
        ]


    return [
        str(pdf_files)
    ]

# =====================================================
# EXTRACT ALL PDF TEXT
# =====================================================

def extract_all_pdf_text(pdf_files):
    """
    Extract and clean text from all uploaded PDFs.
    """

    combined_text = []

    for pdf in pdf_files:

        try:
            text = (
                extract_pdf_text(pdf)
            )

            if text:
                combined_text.append(text)

        except Exception as e:

            if DEBUG:
                print(
                    f"⚠ PDF extraction failed: "
                    f"{os.path.basename(pdf)}"
                )
                print(e)

    return "\n\n".join(combined_text).strip()

# =====================================================
# PDF STATISTICS
# =====================================================

def get_pdf_statistics(
    pdf_files
):

    result = []


    for pdf in pdf_files:

        try:

            text = (extract_pdf_text(pdf))

            reader = PdfReader(
                pdf
            )

            size_kb = round(
                os.path.getsize(pdf)
                / 1024,
                2
            )


            result.append(
                f"""📄 {os.path.basename(pdf)}

Title: {get_pdf_title(text)}

Pages: {len(reader.pages)}

Words: {len(text.split())}

Characters: {len(text)}

Size: {size_kb} KB"""
            )

        except Exception as e:
            if DEBUG:
                print("PDF Statistics Error:", e)


    return "\n\n".join(
        result
    )

# =====================================================
# SIMPLE PDF METADATA QUERY
# =====================================================

def handle_pdf_metadata_query(
    question,
    pdf_files
):

    question_lower = question.lower()


    # =================================================
    # PDF SIZE
    # =================================================

    if (
        "pdf size" in question_lower
        or "file size" in question_lower
    ):

        result = []


        for pdf in pdf_files:

            try:

                size_kb = round(
                    os.path.getsize(pdf)
                    / 1024,
                    2
                )

                result.append(
                    f"📄 {os.path.basename(pdf)}: "
                    f"{size_kb} KB"
                )

            except Exception:

                continue


        if result:

            return "\n".join(
                result
            )


    # =================================================
    # WORD COUNT
    # =================================================

    if (
        "word count" in question_lower
        or "number of words" in question_lower
        or "how many words" in question_lower
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(
                pdf
            )

            result.append(
                f"📄 {os.path.basename(pdf)}: "
                f"{len(text.split())} words"
            )


        return "\n".join(
            result
        )


    # =================================================
    # CHARACTER COUNT
    # =================================================

    if (
        "character count" in question_lower
        or "number of characters" in question_lower
        or "how many characters" in question_lower
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(
                pdf
            )

            result.append(
                f"📄 {os.path.basename(pdf)}: "
                f"{len(text)} characters"
            )


        return "\n".join(
            result
        )


    # =================================================
    # PAGE COUNT
    # =================================================

    if (
        "how many pages" in question_lower
        or "page count" in question_lower
    ):

        result = []


        for pdf in pdf_files:

            reader = PdfReader(
                pdf
            )

            result.append(
                f"📄 {os.path.basename(pdf)}: "
                f"{len(reader.pages)} pages"
            )


        return "\n".join(
            result
        )


    # =================================================
    # PDF TITLE / NAME
    # =================================================

    if (
        "pdf title" in question_lower
        or "pdf name" in question_lower
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(
                pdf
            )

            result.append(
                f"📄 {os.path.basename(pdf)}: "
                f"{get_pdf_title(text)}"
            )


        return "\n".join(
            result
        )


    # =================================================
    # PDF STATS
    # =================================================

    if "pdf stats" in question_lower:

        return get_pdf_statistics(
            pdf_files
        )


    return ""

# =====================================================
# DIRECT PDF FACT SEARCH
# =====================================================

def find_direct_pdf_answer(
    question,
    pdf_content,
    pdf_files=None
):
    """
    Dynamically search for direct facts from the uploaded PDF.

    Returns:
        str: Direct PDF answer if a reliable fact is found.
        "" : If no direct fact is found.
    """

    if not question:
        return ""

    if not pdf_content:
        return ""

    question_lower = question.casefold().strip()

    # =================================================
    # EMAIL
    # =================================================

    if any(
        phrase in question_lower
        for phrase in [
            "email",
            "email address",
            "email id",
            "mail id"
        ]
    ):

        # Try hyperlinks first
        if pdf_files:

            try:

                for pdf_file in pdf_files:

                    links = extract_pdf_links(
                        pdf_file
                    )

                    for url in links.get("urls", []):

                        url = str(url).strip()

                        if url.casefold().startswith(
                            "mailto:"
                        ):

                            email = url[
                                len("mailto:"):
                            ].strip()

                            if email:
                                return email

            except Exception as e:

                if DEBUG:
                    print(
                        "Email hyperlink extraction error:",
                        e
                    )

        # Fallback to PDF text
        emails = re.findall(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            pdf_content,
            re.IGNORECASE
        )

        emails = list(
            dict.fromkeys(emails)
        )

        if emails:
            return "\n".join(emails)

    # =================================================
    # PHONE NUMBER
    # =================================================

    phone_queries = [
        "phone",
        "mobile",
        "contact number",
        "phone number",
        "mobile number",
        "contact details",
        "candidate phone",
        "candidate mobile",
        "candidate contact",
        "resume phone",
        "resume contact"
    ]

    if any(
        phrase in question_lower
        for phrase in phone_queries
    ):

        phone_matches = re.findall(
            r"(?:\+91[\s\-]*)?([6-9]\d{4}[\s\-]?\d{5}|[6-9]\d{9})",
            pdf_content
        )

        formatted_numbers = []
        seen = set()

        for phone in phone_matches:

            phone = re.sub(
                r"[\s\-]",
                "",
                phone
            )

            if len(phone) != 10:
                continue

            if phone in seen:
                continue

            seen.add(phone)

            formatted_numbers.append(
                f"(+91) {phone[:5]} {phone[5:]}"
            )

        if formatted_numbers:
            return "\n".join(
                formatted_numbers
            )

    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in question_lower:

        if pdf_files:

            try:

                for pdf_file in pdf_files:

                    linkedin = get_linkedin_url(
                        pdf_file
                    )

                    if linkedin:
                        return linkedin

            except Exception as e:

                if DEBUG:
                    print(
                        "LinkedIn extraction error:",
                        e
                    )

        linkedin_match = re.search(
            r"https?://(?:www\.)?linkedin\.com/[^\s<>\]]+",
            pdf_content,
            re.IGNORECASE
        )

        if linkedin_match:
            return linkedin_match.group(0)

        if "linkedin" in pdf_content.casefold():
            return (
                "LinkedIn profile is mentioned "
                "in the uploaded PDF."
            )

    # =================================================
    # GITHUB
    # =================================================

    if "github" in question_lower:

        if pdf_files:

            try:

                for pdf_file in pdf_files:

                    github = get_github_url(
                        pdf_file
                    )

                    if github:
                        return github

            except Exception as e:

                if DEBUG:
                    print(
                        "GitHub extraction error:",
                        e
                    )

        github_match = re.search(
            r"https?://(?:www\.)?github\.com/[^\s<>\]]+",
            pdf_content,
            re.IGNORECASE
        )

        if github_match:
            return github_match.group(0)

        if "github" in pdf_content.casefold():
            return (
                "GitHub profile is mentioned "
                "in the uploaded PDF."
            )

    # =================================================
    # CGPA
    # =================================================

    if (
        "cgpa" in question_lower
        or "gpa" in question_lower
        or "grade point" in question_lower
    ):

        cgpa_patterns = [

            r"\bCGPA\s*[:\-]?\s*(\d+(?:\.\d+)?)",

            r"\bGPA\s*[:\-]?\s*(\d+(?:\.\d+)?)",

            r"\b(?:CGPA|GPA)\s+of\s+(\d+(?:\.\d+)?)"

        ]

        for pattern in cgpa_patterns:

            match = re.search(
                pattern,
                pdf_content,
                re.IGNORECASE
            )

            if match:

                return (
                    f"Your CGPA is "
                    f"{match.group(1)}."
                )

    # =================================================
    # EDUCATION / DEGREE
    # =================================================

    education_terms = [
        "education",
        "educational background",
        "degree",
        "qualification",
        "academic background",
        "what did i study",
        "what degree do i have"
    ]

    if any(
        term in question_lower
        for term in education_terms
    ):

        education_section = re.search(
            r"(?:Education|Academic Background)"
            r"(.*?)(?=\n(?:Skills|Experience|Projects|Certifications|Achievements)\b|\Z)",
            pdf_content,
            re.IGNORECASE | re.DOTALL
        )

        if education_section:

            text = education_section.group(1).strip()

            if text:
                return text

        # Fallback around B.Tech
        degree_match = re.search(
            r".{0,150}"
            r"(?:B\.?Tech|Bachelor(?:'s)?\s+of\s+Technology)"
            r".{0,250}",
            pdf_content,
            re.IGNORECASE | re.DOTALL
        )

        if degree_match:
            return degree_match.group(0).strip()

    # =================================================
    # GRADUATION YEAR
    # =================================================

    if any(
        term in question_lower
        for term in [
            "graduation year",
            "graduated",
            "graduation",
            "when did i graduate",
            "when did i complete my degree",
            "passing year"
        ]
    ):

        year_match = re.search(
            r"(?:2021|2022|2023|2024|2025|2026)"
            r"\s*[-–]\s*"
            r"(20\d{2})",
            pdf_content
        )

        if year_match:

            return (
                f"You completed your degree in "
                f"{year_match.group(1)}."
            )

    # =================================================
    # CANDIDATE NAME
    # =================================================

    if any(
        phrase in question_lower
        for phrase in [
            "what is my name"
            "candidate name",
            "candidate's name",
            "person name",
            "person's name",
            "who is the candidate",
            "what is the candidate name",
            "what is the name",
            "who is the person",
            "who is this",
            "whose resume",
            "resume belongs to",
            "applicant name"
        ]
    ):

        title = get_pdf_title(
            pdf_content
        )

        if (
            title
            and title != "Unknown PDF"
            and not title.casefold().endswith(".pdf")
        ):

            return title

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

        for line in lines[:10]:

            if line.casefold() not in invalid_names:

                if len(line.split()) <= 5:

                    return line

    # =================================================
    # NO DIRECT FACT FOUND
    # =================================================

    return ""

# =====================================================
# CHECK WHETHER QUESTION IS RELATED TO PDF
# =====================================================

def is_relevant_to_pdf(
    question,
    semantic_index,
    semantic_chunks,
):
    """
    Dynamically determine whether the user's question
    is related to the uploaded PDF.

    Returns:
        (True, relevant_text)
        (False, "")
    """

    # =================================================
    # 1. VALIDATE QUESTION
    # =================================================

    if not question:
        return False, ""

    question = question.strip()

    if not question:
        return False, ""

    # =================================================
    # 2. VALIDATE SEMANTIC INDEX
    # =================================================

    if (
        semantic_index is None
        or not semantic_chunks
    ):

        if DEBUG:
            print(
                "PDF Related: False "
                "(Semantic Index Unavailable)"
            )

        return False, ""

    # =================================================
    # 3. SEMANTIC SEARCH
    # =================================================

    try:

        relevant_text = semantic_search(
            index=semantic_index,
            chunks=semantic_chunks,
            query=question,
            top_k=SEMANTIC_TOP_K,
            min_score=SEMANTIC_MIN_SCORE
        )

    except Exception as e:

        if DEBUG:
            print(
                "PDF Semantic Search Error:",
                e
            )

        return False, ""

    # =================================================
    # 4. NO RELEVANT CONTEXT
    # =================================================

    if not relevant_text:

        if DEBUG:
            print(
                "PDF Related: False "
                "(No Relevant PDF Context)"
            )

        return False, ""

    # =================================================
    # 5. BASIC CONTEXT VALIDATION
    # =================================================

    cleaned_context = relevant_text.strip()

    if len(cleaned_context) < 50:

        if DEBUG:
            print(
                "PDF Related: False "
                "(PDF Context Too Short)"
            )

        return False, ""

    # =================================================
    # 6. OPTIONAL DEBUG INFORMATION
    # =================================================

    if DEBUG:

        question_words = set(
            re.findall(
                r"\w+",
                question.casefold()
            )
        )

        context_words = set(
            re.findall(
                r"\w+",
                cleaned_context.casefold()
            )
        )

        overlap = len(
            question_words & context_words
        )

        overlap_ratio = (
            overlap /
            max(len(question_words), 1)
        )

        print(
            f"PDF Semantic Overlap: "
            f"{overlap_ratio:.2f}"
        )

        print(
            "PDF Related: True "
            "(Semantic Search Match)"
        )

    # =================================================
    # 7. RETURN PDF CONTEXT
    # =================================================

    return True, cleaned_context

# =====================================================
# CHATBOT
# =====================================================

def chatbot(
    message,
    history=None,
    pdf_files=None
):

    # =====================================================
    # 1. VALIDATE USER MESSAGE
    # =====================================================

    message = (
        message or ""
    ).strip()

    if not message:

        return (
            "Please enter a question."
        )
        
    # =====================================================
    # 2. BUILD CONVERSATION MEMORY
    # =====================================================

    try:

        conversation = build_conversation(
            history or []
        )

    except Exception as e:

        if DEBUG:
            print("Conversation Memory Error:", e)

        conversation = ""


    # =====================================================
    # 3. NORMALIZE PDF FILES
    # =====================================================

    pdf_files = normalize_pdf_files(
        pdf_files
    )

    pdf_content = ""
    relevant_text = ""
    answer = ""

    # =====================================================
    # 4. RESUME REVIEW DETECTION
    # =====================================================

    question_lower = message.casefold().strip()

    resume_review_phrases = [
    "review my resume",
    "review my cv",

    "analyze my resume",
    "analyse my resume",
    "analyze my cv",
    "analyse my cv",

    "resume review",
    "resume feedback",

    "resume score",
    "cv score",
    "ats score",
    "ats review",
    "ats analysis",

    "improve my resume",
    "improve my cv",
    "resume suggestions",
    "resume improvement",

    "resume strengths",
    "resume weaknesses",
    "resume missing skills",
    "resume missing keywords",

    "resume job roles",
    "compare my resume",
    "compare my cv",

    "is my resume interview ready",
    "is my resume ats friendly",

    # Natural variants
    "how good is my resume",
    "how strong is my resume",
    "rate my resume",
    "evaluate my resume",
    "check my resume",
    "check my cv",
]
    is_resume_review_request = any(
        phrase in question_lower
        for phrase in resume_review_phrases
    )

    if is_resume_review_request:

        if not pdf_files:

            return (
                "📄 Please upload your resume PDF first "
                "to use Resume Review."
            )

        try:

            answer = review_resume(
                pdf_files
            )

            update_stats(
                answer,
                source="pdf"
            )

            save_session(
                message,
                answer
            )

            return answer

        except Exception as e:

            if DEBUG:
                print(
                    "Resume Review Error:",
                    e
                )

            return (
                "⚠ Unable to review the resume right now.\n\n"
                "Please try again."
            )
    
    # =====================================================
    # 5. NO PDF MODE
    # =====================================================

    if not pdf_files:

        result = ask_gemini(
            message=message,
            pdf_context="",
            conversation=conversation,
            pdf_fallback=False
        )


        if result["success"]:

            answer = result["answer"]

            update_stats(
                answer,
                source="gemini"
            )

            save_session(
                message,
                answer
            )

            return f"🤖 Source: Gemini AI\n\n{answer}"


        if result["error_type"] == "quota":

            return (
                "⚠ Gemini API quota exceeded.\n\n"
                "Please wait and try again later "
                "or use another Gemini API key."
            )


        if result["error_type"] == "busy":

            return (
                "⚠ Gemini server is currently busy.\n\n"
                "Please try again after a few seconds."
            )


        return (
            "⚠ Unable to generate a response "
            "right now."
        )

    # =====================================================
    # 6. EXTRACT ALL PDF TEXT
    # =====================================================

    pdf_content = extract_all_pdf_text(pdf_files)

    if not pdf_content:
        return "⚠ Unable to read the uploaded PDF."

    cache_key = tuple(
        get_pdf_path(f)
        for f in pdf_files
    )

    if cache_key not in semantic_cache:
        semantic_cache[cache_key] = build_index(pdf_content)

    semantic_index, semantic_chunks = semantic_cache[cache_key]
    
    if DEBUG:
        print(f"📄 PDF Ready | Chunks: {len(semantic_chunks)}")
        
    # =====================================================
    # 7. PDF SUMMARY QUERY
    # =====================================================

    message = re.sub(
        r"\s+",
        " ",
        message
    ).strip()

    question_lower = message.casefold()
    
    # ------------------------------------------------
    # Always initialize
    # ------------------------------------------------

    is_summary_request = any(
        keyword in question_lower
        for keyword in [
            "summarize",
            "summarise",
            "summary",
            "overview",
            "give me an overview",
            "brief summary",
        ]
    )


    if is_summary_request:

        try:

            answer = summarize_pdf(pdf_files)

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + answer
            )
            
            update_stats(
                answer,
                source="pdf"
            )

            save_session(
                message,
                answer
            )


            return answer


        except Exception as e:

            if DEBUG:
                print("PDF Summary Error:", e)


    # =====================================================
    # 8. PDF METADATA QUERY
    # =====================================================

    metadata_answer = handle_pdf_metadata_query(
        message,
        pdf_files
    )


    if metadata_answer:
        
        metadata_answer = (
            "📄 Source: Uploaded PDF\n\n"
            + metadata_answer
        )
                
        update_stats(
            metadata_answer,
            source="pdf"
        )

        save_session(
            message,
            metadata_answer
        )

        return metadata_answer

    # =====================================================
    # 9. DYNAMIC PDF SEARCH
    # =====================================================

    # Semantic search is now the primary PDF retrieval method.
    # Static section/direct searches are not allowed to return
    # an answer before semantic retrieval.

    pdf_related, relevant_text = is_relevant_to_pdf(
        question=message,
        semantic_index=semantic_index,
        semantic_chunks=semantic_chunks,
    )
    
    if DEBUG:
        print("=" * 60)
        print("SEMANTIC SEARCH DEBUG")
        print("Question:", message)
        print("PDF Related:", pdf_related)
        print("Retrieved Context:")
        print(relevant_text)
        print("=" * 60)

    if DEBUG:
        print("=" * 60)
        print("DYNAMIC PDF SEARCH")
        print(f"Question: {message}")
        print(f"PDF Related: {pdf_related}")

        if relevant_text:
            print(
                f"Retrieved PDF Context Length: "
                f"{len(relevant_text)}"
            )

        print("=" * 60)


    # =====================================================
    # 10. PDF-RELATED QUESTION
    # =====================================================

    if pdf_related and relevant_text:

        # -----------------------------------------------
        # Limit context sent to Gemini
        # -----------------------------------------------

        pdf_context = relevant_text[
            :MAX_PDF_CONTEXT
        ].strip()

        if DEBUG:
            print(
                "Sending retrieved PDF context "
                "to Gemini."
            )

        # -----------------------------------------------
        # Ask Gemini using ONLY retrieved PDF context
        # -----------------------------------------------

        result = ask_gemini(
            message=message,
            pdf_context=pdf_context,
            conversation=conversation,
            pdf_fallback=False
        )

        # =================================================
        # GEMINI SUCCESS
        # =================================================

        if result["success"]:

            answer = (
                "🤖 Source: Gemini AI + 📄 Uploaded PDF\n\n"
                + result["answer"]
            )

            update_stats(
                answer,
                source="gemini"
            )

            save_session(
                message,
                answer
            )

            return answer

        # =================================================
        # GEMINI QUOTA ERROR
        # =================================================

        if result["error_type"] == "quota":

            # Do not send the question to unrestricted
            # Gemini because this is a PDF-related query.

            answer = (
                "📄 Source: Uploaded PDF\n\n"
                + pdf_context_fallback(
                    pdf_context
                )
            )

            update_stats(
                answer,
                source="pdf"
            )

            save_session(
                message,
                answer
            )

            return answer

        # =================================================
        # GEMINI SERVER BUSY
        # =================================================

        if result["error_type"] == "busy":

            answer = (
                "📄 Source: Uploaded PDF\n\n"
                + pdf_context_fallback(
                    pdf_context
                )
            )

            update_stats(
                answer,
                source="pdf"
            )

            save_session(
                message,
                answer
            )

            return answer

        # =================================================
        # OTHER GEMINI ERROR
        # =================================================

        answer = (
            "📄 Source: Uploaded PDF\n\n"
            + pdf_context_fallback(
                pdf_context
            )
        )

        update_stats(
            answer,
            source="pdf"
        )

        save_session(
            message,
            answer
        )

        return answer


    # =====================================================
    # 11. PDF NOT RELEVANT
    # =====================================================

    if DEBUG:

        print(
            "No sufficiently relevant PDF "
            "context found."
        )


    # =====================================================
    # 12. GENERAL GEMINI QUESTION
    # =====================================================

    result = ask_gemini(
        message=message,
        pdf_context="",
        conversation=conversation,
        pdf_fallback=False
    )


    # =====================================================
    # 13. GEMINI SUCCESS
    # =====================================================

    if result["success"]:

        answer = (
            "🤖 Source: Gemini AI\n\n"
            + result["answer"]
        )

        update_stats(
            answer,
            source="gemini"
        )

        save_session(
            message,
            answer
        )

        return answer


    # =====================================================
    # 14. GEMINI QUOTA ERROR
    # =====================================================

    if result["error_type"] == "quota":

        return (
            "⚠ Gemini API quota exceeded.\n\n"
            "Please wait and try again later "
            "or use another Gemini API key."
        )


    # =====================================================
    # 15. GEMINI SERVER BUSY
    # =====================================================

    if result["error_type"] == "busy":

        return (
            "⚠ Gemini server is currently busy.\n\n"
            "Please try again after a few seconds."
        )


    # =====================================================
    # 16. OTHER ERROR
    # =====================================================

    return (
        "⚠ Unable to generate a response at the moment.\n\n"
        "Please try again in a few seconds."
    )