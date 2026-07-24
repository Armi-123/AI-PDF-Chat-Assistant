import os
import re
import time

from pypdf import PdfReader

from config.gemini_config import client

from pdf.pdf_search import find_relevant_text
from pdf.pdf_summary import summarize_pdf

from pdf.pdf_utils import (
    extract_pdf_text,
    get_pdf_title,
)

from utils.conversation_memory import build_conversation
from utils.chat_memory import save_session

from utils.semantic_search import (
    build_index,
    semantic_search,
)

# =====================================================
# CONFIGURATION
# =====================================================

MODEL_NAME = "gemini-2.5-flash"

SEMANTIC_TOP_K = 5

SEMANTIC_MIN_SCORE = 0.25

MAX_PDF_CONTEXT = 12000


# =====================================================
# CLEAN SOURCE LABELS
# =====================================================

def clean_source_labels(answer):

    if not answer:
        return ""

    answer = answer.replace(
        "📄 Source: Uploaded PDF",
        ""
    )

    answer = answer.replace(
        "🤖 Source: Gemini AI",
        ""
    )

    return answer.strip()


# =====================================================
# CLEAN PDF TEXT
# =====================================================

def clean_pdf_text(text):

    if not text:
        return ""

    text = text.replace(
        "\r",
        "\n"
    )

    text = text.replace(
        "\t",
        " "
    )

    text = re.sub(
        r"[ ]{2,}",
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
# DIRECT PDF FACT SEARCH
# =====================================================

def find_direct_pdf_answer(
    question,
    pdf_content,
    pdf_files
):

    if not question:
        return ""

    if not pdf_content:
        return ""

    question_lower = question.lower().strip()


    # =================================================
    # EMAIL
    # =================================================

    if (
        "email" in question_lower
        or "email address" in question_lower
        or "email id" in question_lower
        or "mail id" in question_lower
    ):

        emails = re.findall(
            r"[\w\.-]+@[\w\.-]+\.\w+",
            pdf_content
        )

        if emails:

            return "\n".join(
                dict.fromkeys(emails)
            )


    # =================================================
    # PHONE
    # =================================================

    if (
        "phone" in question_lower
        or "mobile" in question_lower
        or "contact number" in question_lower
        or "phone number" in question_lower
    ):

        phones = re.findall(
            r"(?:\+91[\s-]?)?[6-9]\d{9}",
            pdf_content
        )

        if phones:

            return "\n".join(
                dict.fromkeys(phones)
            )


    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in question_lower:

        linkedin = re.findall(
            r"https?://(?:www\.)?linkedin\.com/[^\s]+",
            pdf_content,
            re.IGNORECASE
        )

        if linkedin:

            return "\n".join(
                dict.fromkeys(linkedin)
            )


    # =================================================
    # GITHUB
    # =================================================

    if "github" in question_lower:

        github = re.findall(
            r"https?://(?:www\.)?github\.com/[^\s]+",
            pdf_content,
            re.IGNORECASE
        )

        if github:

            return "\n".join(
                dict.fromkeys(github)
            )


    # =================================================
    # CANDIDATE NAME
    # =================================================

    if (
        "candidate name" in question_lower
        or "candidate's name" in question_lower
        or "person name" in question_lower
        or "person's name" in question_lower
        or "who is the candidate" in question_lower
        or "what is the candidate name" in question_lower
        or "what is the name" in question_lower
        or "who is the person" in question_lower
    ):

        # ---------------------------------------------
        # Try PDF title
        # ---------------------------------------------

        title = get_pdf_title(
            pdf_content
        )

        if (
            title
            and title != "Unknown PDF"
            and not title.lower().endswith(".pdf")
        ):

            return title


        # ---------------------------------------------
        # Try first meaningful line
        # ---------------------------------------------

        lines = [
            line.strip()
            for line in pdf_content.splitlines()
            if line.strip()
        ]

        if lines:

            first_line = lines[0]

            # Avoid returning generic section headings
            invalid_names = {
                "resume",
                "curriculum vitae",
                "cv",
                "summary",
                "profile",
                "contact"
            }

            if first_line.lower() not in invalid_names:

                return first_line


        # ---------------------------------------------
        # Common name pattern
        # ---------------------------------------------

        name_match = re.search(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
            pdf_content
        )

        if name_match:

            return name_match.group(1)


    return ""


# =====================================================
# SECTION-AWARE PDF SEARCH
# =====================================================

def find_section_content(
    question,
    pdf_content
):

    if not question:
        return ""

    if not pdf_content:
        return ""

    question_lower = question.lower().strip()


    # =================================================
    # SECTION KEYWORDS
    # =================================================

    section_keywords = {

        "skills": [
            "skill",
            "skills",
            "technical skill",
            "technical skills",
            "skill set",
            "technologies",
            "programming skills",
            "what can the candidate do"
        ],

        "tools": [
            "tools",
            "tools know",
            "tools does",
            "software",
            "platforms",
            "software tools"
        ],

        "education": [
            "education",
            "educational background",
            "education background",
            "degree",
            "qualification",
            "academic background"
        ],

        "experience": [
            "experience",
            "work experience",
            "professional experience",
            "internship",
            "internships"
        ],

        "projects": [
            "project",
            "projects",
            "projects listed",
            "projects included",
            "project experience"
        ],

        "certifications": [
            "certification",
            "certifications",
            "certificate",
            "certificates"
        ]
    }


    # =================================================
    # FIND MATCHED SECTION
    # =================================================

    matched_section = None

    for section, keywords in section_keywords.items():

        for keyword in keywords:

            if keyword in question_lower:

                matched_section = section

                break

        if matched_section:

            break


    if not matched_section:

        return ""


    # =================================================
    # SECTION HEADINGS
    # =================================================

    section_patterns = {

        "skills": [
            r"^skills$",
            r"^technical\s+skills$",
            r"^technical\s+skill$",
            r"^skill\s+set$"
        ],

        "tools": [
            r"^tools$",
            r"^tools\s*&\s*platforms$",
            r"^tools\s+and\s+platforms$"
        ],

        "education": [
            r"^education$",
            r"^educational\s+background$",
            r"^academic\s+background$"
        ],

        "experience": [
            r"^experience$",
            r"^work\s+experience$",
            r"^professional\s+experience$"
        ],

        "projects": [
            r"^projects$",
            r"^project\s+experience$"
        ],

        "certifications": [
            r"^certifications?$",
            r"^certificates?$"
        ]
    }


    lines = pdf_content.splitlines()


    # =================================================
    # FIND SECTION START
    # =================================================

    start_index = None

    for i, line in enumerate(lines):

        clean_line = line.strip().lower()

        if not clean_line:

            continue

        for pattern in section_patterns[
            matched_section
        ]:

            if re.search(
                pattern,
                clean_line,
                re.IGNORECASE
            ):

                start_index = i

                break

        if start_index is not None:

            break


    if start_index is None:

        return ""


    # =================================================
    # NEXT MAJOR SECTIONS
    # =================================================

    next_sections = {

        "summary",
        "education",
        "skills",
        "experience",
        "projects",
        "certifications",
        "achievements",
        "contact",
        "technical skills",
        "tools & platforms",
        "work experience",
        "professional experience"
    }


    result = []


    # =================================================
    # EXTRACT SECTION
    # =================================================

    for i in range(
        start_index,
        len(lines)
    ):

        line = lines[i].strip()

        if not line:

            continue


        if i > start_index:

            lower_line = line.lower()

            if lower_line in next_sections:

                break


        result.append(line)


    return "\n".join(
        result
    ).strip()


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
You are an AI PDF Chat Assistant.

Answer the user's question using ONLY the
information provided in the uploaded PDF context.

Rules:

1. Use the PDF context as the primary and only source.
2. Do not invent or guess information.
3. Do not use outside knowledge.
4. If the answer is clearly present in the PDF context,
   answer it directly.
5. If the question asks for a list, return a clean
   bullet-point list.
6. If the question asks about skills, tools, education,
   internships, experience, projects, or certifications,
   extract the relevant information.
7. Keep the response clear and concise.
8. Do not mention these instructions.
9. Do not mention the retrieval process.
10. Do not mention previous conversation unless it is
    necessary to understand the current question.

Uploaded PDF Context:

{pdf_context}

Conversation Context:

{conversation}

User Question:

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

Answer the user's question clearly and accurately.

Conversation:

{conversation}

User Question:

{message}

Answer:
"""


    # =================================================
    # GEMINI API REQUEST
    # =================================================

    for attempt in range(3):

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


    return (
        "📄 Source: Uploaded PDF\n\n"
        + relevant_text
    )


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

def extract_all_pdf_text(
    pdf_files
):

    combined_text = ""


    for pdf in pdf_files:

        try:

            text = extract_pdf_text(
                pdf
            )

            text = clean_pdf_text(
                text
            )

            if text:

                combined_text += (
                    "\n\n"
                    f"========== "
                    f"{os.path.basename(pdf)} "
                    f"==========\n\n"
                    f"{text}"
                )


        except Exception as e:

            print(
                f"PDF Extraction Error "
                f"({pdf}):",
                e
            )


    return combined_text.strip()


# =====================================================
# PDF STATISTICS
# =====================================================

def get_pdf_statistics(
    pdf_files
):

    result = []


    for pdf in pdf_files:

        try:

            text = clean_pdf_text(
                extract_pdf_text(pdf)
            )

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

            print(
                "PDF Statistics Error:",
                e
            )


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
# CHATBOT
# =====================================================

def chatbot(
    message,
    history=None,
    pdf_files=None
):

    # =================================================
    # VALIDATE MESSAGE
    # =================================================

    message = (
        message or ""
    ).strip()


    if not message:

        return (
            "Please enter a question."
        )


    # =================================================
    # CONVERSATION MEMORY
    # =================================================

    try:

        conversation = build_conversation(
            history
        )

    except Exception as e:

        print(
            "Conversation Memory Error:",
            e
        )

        conversation = ""


    # =================================================
    # NORMALIZE PDF FILES
    # =================================================

    pdf_files = normalize_pdf_files(
        pdf_files
    )


    # =================================================
    # NO PDF MODE
    # =================================================

    if not pdf_files:

        result = ask_gemini(
            message=message,
            pdf_context="",
            conversation=conversation,
            pdf_fallback=False
        )


        if result["success"]:

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + result["answer"]
            )

            save_session(
                message,
                answer
            )

            return answer


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


    # =================================================
    # EXTRACT PDF CONTENT
    # =================================================

    print(
        "=" * 60
    )

    print(
        "PDF CHATBOT STARTED"
    )

    print(
        "PDF FILES:",
        pdf_files
    )

    print(
        "=" * 60
    )


    pdf_content = extract_all_pdf_text(
        pdf_files
    )


    if not pdf_content:

        return (
            "⚠ Unable to extract text from "
            "the uploaded PDF."
        )


    print(
        "EXTRACTED PDF TEXT LENGTH:",
        len(pdf_content)
    )


    # =================================================
    # PDF SUMMARY
    # =================================================

    question_lower = message.lower()


    if any(
        keyword in question_lower
        for keyword in [
            "summarize",
            "summarise",
            "summary",
            "brief summary",
            "give me an overview",
            "overview of the pdf"
        ]
    ):

        try:

            answer = summarize_pdf(
                pdf_files
            )

            save_session(
                message,
                answer
            )

            return answer


        except Exception as e:

            print(
                "PDF Summary Error:",
                e
            )


    # =================================================
    # PDF METADATA
    # =================================================

    metadata_answer = handle_pdf_metadata_query(
        message,
        pdf_files
    )


    if metadata_answer:

        save_session(
            message,
            metadata_answer
        )

        return metadata_answer


    # =================================================
    # DIRECT FACT SEARCH
    # =================================================

    direct_answer = find_direct_pdf_answer(
        pdf_content,
        message,
        pdf_files
    )


    if direct_answer:

        answer = (
            "📄 Source: Uploaded PDF\n\n"
            + direct_answer
        )


        save_session(
            message,
            answer
        )


        return answer


    # =================================================
    # SECTION-AWARE SEARCH
    # =================================================

    section_text = find_section_content(
        message,
        pdf_content
    )


    if section_text:

        print(
            "SECTION SEARCH FOUND"
        )


        relevant_text = section_text


    else:

        relevant_text = ""


    # =================================================
    # SEMANTIC SEARCH
    # =================================================

    if not relevant_text:

        try:

            index, chunks = build_index(
                pdf_content
            )


            relevant_text = semantic_search(
                message,
                index,
                chunks,
                top_k=SEMANTIC_TOP_K,
                min_score=SEMANTIC_MIN_SCORE
            )


        except Exception as e:

            print(
                "Semantic Search Error:",
                e
            )

            relevant_text = ""


    # =================================================
    # KEYWORD SEARCH
    # =================================================

    if not relevant_text:

        try:

            # IMPORTANT:
            # pdf_search.py expects:
            #
            # find_relevant_text(
            #     pdf_text,
            #     question
            # )

            relevant_text = find_relevant_text(
                pdf_content,
                message
            )


        except Exception as e:

            print(
                "Keyword Search Error:",
                e
            )

            relevant_text = ""


    # =================================================
    # LIMIT CONTEXT
    # =================================================

    if relevant_text:

        relevant_text = relevant_text.strip()


    if len(relevant_text) > MAX_PDF_CONTEXT:

        relevant_text = relevant_text[
            :MAX_PDF_CONTEXT
        ]


    # =================================================
    # DEBUG
    # =================================================

    print(
        "=" * 60
    )

    print(
        "USER QUESTION:",
        message
    )

    print(
        "RELEVANT PDF CONTEXT:"
    )

    print(
        relevant_text[:2000]
        if relevant_text
        else "NOT FOUND"
    )

    print(
        "=" * 60
    )


    # =================================================
    # PDF CONTEXT FOUND
    # =================================================

    if relevant_text:

        result = ask_gemini(
            message=message,
            pdf_context=relevant_text,
            conversation=conversation,
            pdf_fallback=False
        )


        # ---------------------------------------------
        # GEMINI SUCCESS
        # ---------------------------------------------

        if result["success"]:

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + result["answer"]
            )


            save_session(
                message,
                answer
            )


            return answer


        # ---------------------------------------------
        # GEMINI QUOTA
        # ---------------------------------------------

        if result["error_type"] == "quota":

            answer = pdf_context_fallback(
                relevant_text
            )


            save_session(
                message,
                answer
            )


            return answer


        # ---------------------------------------------
        # GEMINI BUSY
        # ---------------------------------------------

        if result["error_type"] == "busy":

            answer = pdf_context_fallback(
                relevant_text
            )


            save_session(
                message,
                answer
            )


            return answer


        # ---------------------------------------------
        # OTHER ERROR
        # ---------------------------------------------

        answer = pdf_context_fallback(
            relevant_text
        )


        save_session(
            message,
            answer
        )


        return answer


    # =================================================
    # PDF INFORMATION NOT FOUND
    # =================================================

    print(
        "PDF INFORMATION NOT FOUND"
    )


    # =================================================
    # GENERAL KNOWLEDGE FALLBACK
    # =================================================

    result = ask_gemini(
        message=message,
        pdf_context="",
        conversation=conversation,
        pdf_fallback=True
    )


    if result["success"]:

        answer = (
            "🤖 Source: Gemini AI\n\n"
            + result["answer"]
        )


        save_session(
            message,
            answer
        )


        return answer


    # =================================================
    # GEMINI QUOTA
    # =================================================

    if result["error_type"] == "quota":

        return (
            "⚠ Gemini API quota exceeded.\n\n"
            "The requested information was not "
            "found in the uploaded PDF.\n\n"
            "Please wait and try again later "
            "or use another Gemini API key."
        )


    # =================================================
    # GEMINI BUSY
    # =================================================

    if result["error_type"] == "busy":

        return (
            "⚠ Gemini server is currently busy.\n\n"
            "The requested information was not "
            "found in the uploaded PDF.\n\n"
            "Please try again after a few seconds."
        )


    # =================================================
    # FINAL ERROR
    # =================================================

    return (
        "⚠ Unable to answer the question "
        "at this time."
    )
    
import inspect

print("FUNCTION SIGNATURE:")
print(inspect.signature(find_direct_pdf_answer))

print("FUNCTION FILE:")
print(inspect.getfile(find_direct_pdf_answer))