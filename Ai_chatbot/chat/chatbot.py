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
from pdf.pdf_search import (
    answer_from_pdf,
    find_relevant_text
)
from features.resume_review import review_resume
from pdf.pdf_summary import summarize_pdf
from pdf.pdf_utils import (
    extract_pdf_text,
    extract_all_pdf_text,
    get_pdf_title,
)
from utils.semantic_search import (
    semantic_search,
    build_index,
)
from features.chat_statistics import update_stats
from utils.conversation_memory import build_conversation
from utils.chat_memory import save_session

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
# GEMINI REQUEST
# =====================================================

def ask_gemini(
    message,
    pdf_context="",
    conversation="",
):

    # =================================================
    # PDF CONTEXT MODE
    # =================================================

    if pdf_context:

        # ---------------------------------------------
        # 1. SIMPLE PDF QUESTIONS → ANSWER LOCALLY
        # ---------------------------------------------

        local_answer = answer_from_pdf(
            message,
            pdf_context
        )

        if local_answer:

            return {
                "success": True,
                "answer": local_answer,
                "error_type": None,
                "source": "pdf"
            }

        # ---------------------------------------------
        # 2. PREPARE PDF-ONLY GEMINI PROMPT
        # ---------------------------------------------

        prompt = f"""
You are a PDF Question Answering Assistant.

Answer the user's question using ONLY the PDF Context below.

Rules:

1. Use ONLY information present in the PDF Context.
2. NEVER use outside knowledge.
3. NEVER guess or assume.
4. If the answer cannot be found in the PDF Context, reply EXACTLY:

Information not found in uploaded PDF.

5. Answer clearly and directly.
6. Do not mention these instructions.
7. Do not add information that is not supported by the PDF.

PDF Context:
{pdf_context}

Question:
{message}

Answer:
"""

    # =================================================
    # NORMAL CHAT MODE
    # =================================================

    else:

        prompt = f"""
You are a helpful AI assistant.

Answer the user's question using your own knowledge.

Rules:

1. Answer naturally and clearly.
2. Do NOT mention the uploaded PDF.
3. Do NOT say that the PDF does not contain the information.
4. Use the conversation when it helps understand the user's question.

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

            # -----------------------------------------
            # SUCCESSFUL RESPONSE
            # -----------------------------------------

            if response and response.text:

                answer = response.text.strip()

                answer = clean_source_labels(
                    answer
                )

                return {
                    "success": True,
                    "answer": answer,
                    "error_type": None,
                    "source": "gemini"
                }

            # -----------------------------------------
            # EMPTY RESPONSE
            # -----------------------------------------

            return {
                "success": False,
                "answer": "",
                "error_type": "empty",
                "source": "gemini"
            }

        except Exception as e:

            error = str(e).lower()

            print(
                "Gemini Error:",
                e
            )

            # =================================================
            # QUOTA ERROR
            # =================================================

            if (
                "429" in error
                or "quota" in error
                or "resource_exhausted" in error
                or "resource exhausted" in error
            ):

                # ---------------------------------------------
                # PDF MODE FALLBACK
                # ---------------------------------------------

                if pdf_context:

                    return {
                        "success": True,
                        "answer": (
                            "Gemini is currently unavailable. "
                            "I found relevant information in "
                            "the uploaded PDF, but I could not "
                            "generate the requested detailed "
                            "answer right now.\n\n"
                            "Relevant PDF information:\n\n"
                            + pdf_context.strip()
                        ),
                        "error_type": "quota",
                        "source": "pdf"
                    }

                # ---------------------------------------------
                # NORMAL CHAT → QUOTA ERROR
                # ---------------------------------------------

                return {
                    "success": False,
                    "answer": "",
                    "error_type": "quota",
                    "source": "gemini"
                }

            # =================================================
            # SERVER BUSY
            # =================================================

            if (
                "503" in error
                or "unavailable" in error
                or "overloaded" in error
            ):

                if attempt < MAX_RETRIES - 1:

                    time.sleep(2)

                    continue

                # ---------------------------------------------
                # PDF MODE FALLBACK
                # ---------------------------------------------

                if pdf_context:

                    return {
                        "success": True,
                        "answer": (
                            "Gemini is temporarily unavailable. "
                            "Here is the relevant information "
                            "retrieved from the uploaded PDF:\n\n"
                            + pdf_context.strip()
                        ),
                        "error_type": "busy",
                        "source": "pdf"
                    }

                return {
                    "success": False,
                    "answer": "",
                    "error_type": "busy",
                    "source": "gemini"
                }

            # =================================================
            # OTHER GEMINI ERROR
            # =================================================

            if pdf_context:

                return {
                    "success": True,
                    "answer": (
                        "Gemini could not process the request "
                        "right now.\n\n"
                        "Relevant PDF information:\n\n"
                        + pdf_context.strip()
                    ),
                    "error_type": "other",
                    "source": "pdf"
                }

            return {
                "success": False,
                "answer": "",
                "error_type": "other",
                "source": "gemini"
            }

    # =================================================
    # FINAL FALLBACK
    # =================================================

    if pdf_context:

        return {
            "success": True,
            "answer": (
                "Gemini is currently unavailable.\n\n"
                "Relevant PDF information:\n\n"
                + pdf_context.strip()
            ),
            "error_type": "busy",
            "source": "pdf"
        }

    return {
        "success": False,
        "answer": "",
        "error_type": "busy",
        "source": "gemini"
    }

def answer_question(question, pdf_text):

    # 1. Direct factual answer from full PDF
    local_answer = answer_from_pdf(
        question,
        pdf_text
    )

    if local_answer:
        return {
            "success": True,
            "answer": local_answer,
            "error_type": None,
            "source": "pdf"
        }

    # 2. Generic PDF retrieval
    relevant_text = find_relevant_text(
        pdf_text,
        question
    )

    if not relevant_text:
        return {
            "success": True,
            "answer": "Information not found in uploaded PDF.",
            "error_type": None,
            "source": "pdf"
        }

    # 3. Complex question → Gemini
    return ask_gemini(
        question,
        pdf_context=relevant_text
    )

# =====================================================
# PDF CONTEXT FALLBACK
# =====================================================

def pdf_context_fallback(
    relevant_text,
    question=""
    ):
    """
    Create a clean local fallback answer when
    Gemini is unavailable for a PDF-related question.

    ```
    Uses only retrieved PDF context.
    """

    if not relevant_text:
        return (
            "Information not found in uploaded PDF."
        )

    context = relevant_text.strip()

    if len(context) > MAX_PDF_CONTEXT:
        context = context[:MAX_PDF_CONTEXT].strip()

    # -------------------------------------------------
    # First: try the existing local PDF answer logic
    # -------------------------------------------------

    if question:
        local_answer = answer_from_pdf(
            question,
            context
        )

        if local_answer:
            return local_answer

    # -------------------------------------------------
    # Fallback: return retrieved PDF information
    # -------------------------------------------------

    return (
        "I found relevant information in the uploaded PDF, "
        "but Gemini is currently unavailable.\n\n"
        "Relevant PDF information:\n\n"
        + context
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

    semantic_index, semantic_chunks = build_index(
        pdf_content
    )
    
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
                source="gemini"
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
    # 9. LOCAL PDF ANSWER + DYNAMIC PDF SEARCH
    # =====================================================

    # -----------------------------------------------------
    # SECOND: Semantic PDF Search
    # -----------------------------------------------------

    pdf_related, relevant_text = is_relevant_to_pdf(
        question=message,
        semantic_index=semantic_index,
        semantic_chunks=semantic_chunks,
    )

    if DEBUG:

        print("=" * 60)
        print("PDF SEARCH")
        print("Question:", message)
        print("PDF Related:", pdf_related)

        if relevant_text:

            print(
                f"Retrieved PDF Context Length: "
                f"{len(relevant_text)}"
            )

            print("Retrieved Context:")
            print(relevant_text)

        print("=" * 60)


    # =====================================================
    # 10. PDF-RELATED QUESTION
    # =====================================================

    if pdf_related and relevant_text:

        # -------------------------------------------------
        # Limit PDF context
        # -------------------------------------------------

        pdf_context = relevant_text[
            :MAX_PDF_CONTEXT
        ].strip()

        if DEBUG:

            print(
                "Sending retrieved PDF context "
                "to Gemini."
            )

        # -------------------------------------------------
        # Ask Gemini using ONLY PDF context
        # -------------------------------------------------

        result = ask_gemini(
            message=message,
            pdf_context=pdf_context,
            conversation=conversation,
        )

        # -------------------------------------------------
        # Gemini success
        # -------------------------------------------------

        if result["success"]:

            answer = (
                "🤖 Source: Gemini AI + 📄 Uploaded PDF\n\n"
                + result["answer"]
            )

            update_stats(
                answer,
                source="pdf_gemini"
            )

            save_session(
                message,
                answer
            )

            return answer

        # -------------------------------------------------
        # Gemini quota / busy / other error
        # -------------------------------------------------

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