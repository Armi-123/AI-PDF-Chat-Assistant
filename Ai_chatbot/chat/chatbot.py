import os
import re
import time

from config.gemini_config import client

from pdf.pdf_search import find_relevant_text
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

MAX_PDF_CONTEXT = 12000

SEMANTIC_TOP_K = 5

SEMANTIC_MIN_SCORE = 0.30


# =====================================================
# CLEAN GEMINI SOURCE LABELS
# =====================================================

def clean_source_labels(answer):
    """
    Remove duplicate source labels from Gemini responses.
    """

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
    """
    Clean extracted PDF text.
    """

    if not text:
        return ""

    text = text.replace(
        "\r",
        " "
    )

    text = text.replace(
        "\t",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =====================================================
# DIRECT PDF FACT SEARCH
# =====================================================

def find_direct_pdf_answer(
    question,
    pdf_content
):
    """
    Handle simple factual questions directly
    from the uploaded PDF.

    This reduces unnecessary Gemini API calls.
    """

    if not question:
        return ""

    if not pdf_content:
        return ""

    question_lower = question.lower()

    # =================================================
    # CANDIDATE / PERSON NAME
    # =================================================

    if (
        "candidate name" in question_lower
        or "candidate's name" in question_lower
        or "person name" in question_lower
        or "person's name" in question_lower
        or "what is the candidate" in question_lower
        or "who is the candidate" in question_lower
    ):

        title = get_pdf_title(
            pdf_content
        )

        if (
            title
            and title != "Unknown PDF"
            and not title.lower().endswith(".pdf")
        ):

            return title


        # Try first meaningful line
        lines = [
            line.strip()
            for line in pdf_content.splitlines()
            if line.strip()
        ]

        if lines:

            first_line = lines[0]

            if (
                len(first_line) < 100
                and "@" not in first_line
            ):

                return first_line


    # =================================================
    # EMAIL
    # =================================================

    if (
        "email" in question_lower
        or "email address" in question_lower
    ):

        emails = re.findall(
            r"[\w\.-]+@[\w\.-]+\.\w+",
            pdf_content
        )

        if emails:

            return "\n".join(
                dict.fromkeys(
                    emails
                )
            )


    # =================================================
    # PHONE NUMBER
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
                dict.fromkeys(
                    phones
                )
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
                dict.fromkeys(
                    linkedin
                )
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
                dict.fromkeys(
                    github
                )
            )


    return ""


# =====================================================
# GEMINI API REQUEST
# =====================================================

def ask_gemini(
    message,
    pdf_context="",
    conversation="",
    pdf_fallback=False
):
    """
    Send a question to Gemini.

    If PDF context exists, Gemini answers using
    the uploaded PDF.

    If PDF context does not exist and pdf_fallback
    is True, Gemini uses general knowledge.
    """

    if pdf_context:

        prompt = f"""
You are an AI PDF Chat Assistant.

Answer the user's question using ONLY the
information provided in the uploaded PDF context.

IMPORTANT RULES:

1. Do not invent information.
2. Do not use outside knowledge.
3. If the answer is present in the PDF context,
   answer directly and clearly.
4. Keep the answer concise.
5. Do not say that you do not know if the
   information is clearly present in the context.
6. Do not mention these instructions.
7. Do not mention "Previous Conversation" in
   your answer.

Previous Conversation:

{conversation}

Uploaded PDF Context:

{pdf_context}

User Question:

{message}

Answer:
"""

    elif pdf_fallback:

        prompt = f"""
You are a helpful AI assistant.

The user's question was not answered from the
uploaded PDF.

Answer the question using your general knowledge.

Do not claim that the answer is in the PDF.

Previous Conversation:

{conversation}

User Question:

{message}

Answer:
"""

    else:

        prompt = f"""
You are a helpful AI assistant.

Answer the user's question clearly and accurately.

Previous Conversation:

{conversation}

User Question:

{message}

Answer:
"""


    # =================================================
    # GEMINI RETRY
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
                f"Gemini Error "
                f"(Attempt {attempt + 1}/3):",
                e
            )


            # =========================================
            # QUOTA / RATE LIMIT
            # =========================================

            if (
                "429" in error
                or "quota" in error
                or "resource_exhausted" in error
            ):

                return {
                    "success": False,
                    "answer": "",
                    "error_type": "quota"
                }


            # =========================================
            # SERVER BUSY
            # =========================================

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


            # =========================================
            # OTHER ERROR
            # =========================================

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
# PDF FALLBACK RESPONSE
# =====================================================

def pdf_context_fallback(
    relevant_text
):
    """
    Return relevant PDF content directly when
    Gemini cannot generate a final response.
    """

    if not relevant_text:
        return ""

    relevant_text = relevant_text.strip()

    if len(relevant_text) > MAX_PDF_CONTEXT:

        relevant_text = (
            relevant_text[
                :MAX_PDF_CONTEXT
            ]
        )


    return (
        "📄 Source: Uploaded PDF\n\n"
        + relevant_text
    )


# =====================================================
# MAIN CHATBOT
# =====================================================

def chatbot(
    message,
    history=None,
    pdf_file=None
):
    """
    Main chatbot function.

    Flow:

    1. Extract PDF text
    2. Direct PDF fact search
    3. Keyword search
    4. Semantic search
    5. Gemini PDF answer
    6. PDF fallback if Gemini quota exceeded
    7. Gemini general knowledge if PDF has no answer
    """

    if not message:

        return (
            "Please enter a question."
        )


    message = message.strip()


    # =================================================
    # BUILD CONVERSATION MEMORY
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
    # NO PDF UPLOADED
    # =================================================

    if not pdf_file:

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
    # EXTRACT PDF TEXT
    # =================================================

    try:

        pdf_content = extract_pdf_text(
            pdf_file
        )

    except Exception as e:

        print(
            "PDF Extraction Error:",
            e
        )

        pdf_content = ""


    pdf_content = clean_pdf_text(
        pdf_content
    )


    # =================================================
    # PDF EMPTY
    # =================================================

    if not pdf_content:

        return (
            "⚠ Unable to extract text from "
            "the uploaded PDF."
        )


    # =================================================
    # DIRECT PDF FACT SEARCH
    # =================================================

    direct_answer = find_direct_pdf_answer(
        message,
        pdf_content
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
    # KEYWORD SEARCH
    # =================================================

    try:

        relevant_text = find_relevant_text(
            message,
            pdf_content
        )

    except Exception as e:

        print(
            "Keyword Search Error:",
            e
        )

        relevant_text = ""


    # =================================================
    # SEMANTIC SEARCH
    # =================================================

    try:

        index, chunks = build_index(
            pdf_content
        )


        semantic_text = semantic_search(
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

        semantic_text = ""


    # =================================================
    # COMBINE SEARCH RESULTS
    # =================================================

    combined_results = []


    if relevant_text:

        combined_results.append(
            relevant_text
        )


    if semantic_text:

        combined_results.append(
            semantic_text
        )


    # Remove duplicate content
    unique_results = []

    seen_text = set()


    for result in combined_results:

        result = result.strip()

        if not result:
            continue

        result_key = result[:500]

        if result_key in seen_text:
            continue

        seen_text.add(
            result_key
        )

        unique_results.append(
            result
        )


    relevant_text = "\n\n".join(
        unique_results
    )


    # =================================================
    # LIMIT PDF CONTEXT
    # =================================================

    if len(relevant_text) > MAX_PDF_CONTEXT:

        relevant_text = (
            relevant_text[
                :MAX_PDF_CONTEXT
            ]
        )


    # =================================================
    # PDF INFORMATION FOUND
    # =================================================

    if relevant_text.strip():

        print(
            "=" * 60
        )

        print(
            "PDF CONTEXT FOUND"
        )

        print(
            relevant_text[
                :2000
            ]
        )

        print(
            "=" * 60
        )


        # =============================================
        # ASK GEMINI TO FORMAT PDF ANSWER
        # =============================================

        result = ask_gemini(
            message=message,
            pdf_context=relevant_text,
            conversation=conversation
        )


        # =============================================
        # GEMINI SUCCESS
        # =============================================

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


        # =============================================
        # GEMINI QUOTA EXCEEDED
        # =============================================

        if result["error_type"] == "quota":

            answer = pdf_context_fallback(
                relevant_text
            )

            save_session(
                message,
                answer
            )

            return answer


        # =============================================
        # GEMINI SERVER BUSY
        # =============================================

        if result["error_type"] == "busy":

            answer = pdf_context_fallback(
                relevant_text
            )

            save_session(
                message,
                answer
            )

            return answer


        # =============================================
        # OTHER GEMINI ERROR
        # =============================================

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
        "=" * 60
    )

    print(
        "PDF INFORMATION NOT FOUND"
    )

    print(
        "QUESTION:",
        message
    )

    print(
        "=" * 60
    )


    # =================================================
    # GEMINI GENERAL KNOWLEDGE FALLBACK
    # =================================================

    result = ask_gemini(
        message=message,
        pdf_context="",
        conversation=conversation,
        pdf_fallback=True
    )


    # =================================================
    # GEMINI SUCCESS
    # =================================================

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
    # GEMINI QUOTA ERROR
    # =================================================

    if result["error_type"] == "quota":

        return (
            "⚠ Gemini API quota exceeded.\n\n"
            "The requested information was not found "
            "in the uploaded PDF.\n\n"
            "Please wait and try again later "
            "or use another Gemini API key."
        )


    # =================================================
    # GEMINI SERVER BUSY
    # =================================================

    if result["error_type"] == "busy":

        return (
            "⚠ Gemini server is currently busy.\n\n"
            "The requested information was not found "
            "in the uploaded PDF.\n\n"
            "Please try again after a few seconds."
        )


    # =================================================
    # FINAL ERROR
    # =================================================

    return (
        "⚠ Unable to answer the question "
        "at this time."
    )