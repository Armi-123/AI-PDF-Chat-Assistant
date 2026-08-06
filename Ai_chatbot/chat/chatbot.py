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
    get_pdf_title,
    clean_pdf_text,
    get_linkedin_url,
    get_github_url,
)
from utils.semantic_search import (
    semantic_search,
    build_index
)
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
# DIRECT PDF FACT SEARCH
# =====================================================

def find_direct_pdf_answer(
    question,
    pdf_content,
    pdf_files=None
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
    # PHONE NUMBER
    # =================================================

    phone_queries = [
        "phone number",
        "mobile number",
        "contact number",
        "candidate phone",
        "candidate mobile",
        "candidate contact",
        "person phone",
        "person mobile",
        "resume phone",
        "resume contact",
        "contact details",
        "candidate phone number",
        "candidate mobile number"
    ]

    if any(query in question_lower for query in phone_queries):

        phone_matches = re.findall(
            r"(?:\+91|\(\+91\))?[\s\-]*([6-9]\d{4}[\s\-]?\d{5}|[6-9]\d{9})",
            pdf_content
        )

        formatted_numbers = []
        seen = set()

        for phone in phone_matches:

            phone = re.sub(r"[\s\-]", "", phone)

            if len(phone) != 10:
                continue

            if phone in seen:
                continue

            seen.add(phone)

            formatted_numbers.append(
                f"(+91) {phone[:5]} {phone[5:]}"
            )

        if formatted_numbers:
            return "\n".join(formatted_numbers)
        
    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in question_lower:

        if pdf_files:

            linkedin = get_linkedin_url(pdf_files[0])

            if linkedin:
                return linkedin

        if "linkedin" in pdf_content.lower():
            return "LinkedIn profile is mentioned in the uploaded PDF."

    # =================================================
    # GITHUB
    # =================================================

    if "github" in question_lower:

        if pdf_files:

            github = get_github_url(pdf_files[0])

            if github:
                return github

        if "github" in pdf_content.lower():
            return "GitHub profile is mentioned in the uploaded PDF."

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

def find_section_content(question, pdf_content):
    """
    Extract an entire resume section from the PDF.
    """

    if not question or not pdf_content:
        return ""

    question = question.lower()

    section_map = {
        "skills": [
            "skill",
            "skills",
            "technical",
            "technology",
            "technologies",
            "programming",
            "programming language",
            "programming languages",
            "language",
            "languages",
            "python",
            "sql",
            "java",
            "c++",
            "javascript"
        ],
        "education": [
            "education",
            "degree",
            "qualification",
            "academic",
            "university",
            "college",
            "institute",
            "school",
            "studied",
            "study",
            "graduation",
            "b.tech",
            "m.tech"
        ],
        "experience": [
            "experience", "internship", "intern",
            "employment", "worked", "job"
        ],
        "projects": [
            "project", "projects"
        ],
        "certifications": [
            "certification", "certificate"
        ]
    }

    target_section = None

    for section, keywords in section_map.items():
        if any(word in question for word in keywords):
            target_section = section
            break

    if target_section is None:
        return ""

    lines = [
        line.strip()
        for line in pdf_content.splitlines()
        if line.strip()
    ]

    headings = [
        "summary",
        "education",
        "skills",
        "experience",
        "projects",
        "certifications",
        "achievements",
        "contact"
    ]

    start = None

    for i, line in enumerate(lines):
        if line.lower() == target_section:
            start = i
            break

    if start is None:
        return ""

    result = []

    for i in range(start + 1, len(lines)):

        current = lines[i].strip()

        if (
            current.lower() in headings
            and current.lower() != target_section
        ):
            break

        result.append(current)

    return "\n".join(result).strip()

def format_pdf_section_answer(question, section_text):
    """
    Format section content extracted directly
    from the uploaded PDF.
    """

    if not section_text:
        return ""

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
# CHECK WHETHER QUESTION IS RELATED TO PDF 
# =====================================================

def is_relevant_to_pdf(
    question,
    semantic_index,
    semantic_chunks,
    min_score=SEMANTIC_MIN_SCORE
):
    """
    Decide whether the user's question should be answered
    from the uploaded PDF.
    """

    if not question:
        return False

    question_lower = question.lower()

    pdf_keywords = [
        "candidate",
        "resume",
        "cv",
        "profile",
        "education",
        "degree",
        "qualification",
        "experience",
        "internship",
        "internships",
        "projects",
        "project",
        "skills",
        "skill",
        "certification",
        "certificate",
        "phone",
        "email",
        "contact",
        "linkedin",
        "github",
        "summary"
    ]

    # Immediate PDF detection
    if any(keyword in question_lower for keyword in pdf_keywords):

        if DEBUG:
            print("PDF Related: True (Keyword Match)")

        return True

    if semantic_index is None or not semantic_chunks:
        return False

    try:

        relevant_text = semantic_search(
            index=semantic_index,
            chunks=semantic_chunks,
            query=question,
            top_k=1,
            min_score=min_score
        )

        if not relevant_text:

            if DEBUG:
                print("PDF Related: False")

            return False

        query_words = {

            word

            for word in re.findall(r"\w+", question_lower)

            if len(word) > 2

        }

        context_words = set(
            re.findall(r"\w+", relevant_text.lower())
        )

        overlap = len(query_words & context_words)

        score = overlap / max(len(query_words), 1)

        if DEBUG:
            print(f"Semantic Overlap: {score:.2f}")

        if score >= 0.25:

            if DEBUG:
                print("PDF Related: True")

            return True

        if DEBUG:
            print("PDF Related: False")

        return False

    except Exception as e:

        if DEBUG:
            print("PDF relevance check failed:", e)

        return False
    
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
    # RESUME REVIEW DETECTION
    # =====================================================

    question_lower = message.lower()

    resume_keywords = [
        "resume",
        "cv",
        "profile",
        "candidate",
        "applicant"
    ]

    review_keywords = [
        "resume",
        "cv",
        "ats",

        "review my resume",
        "analyze my resume",
        "analyse my resume",

        "resume review",
        "resume feedback",

        "resume score",
        "ats score",

        "improve my resume",
        "improve resume",

        "strengths",
        "weaknesses",

        "missing skills",
        "missing keywords",

        "interview ready",

        "job roles",
        "salary",
        "companies",
        "recruiter",
        "resume summary",
        "resume suggestions",
        "compare my resume"
    ]

    if (
        any(word in question_lower for word in resume_keywords)
        and
        any(word in question_lower for word in review_keywords)
    ):

        answer = review_resume(pdf_files)

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
    # 4. NO PDF MODE
    # =====================================================

    if not pdf_files:

        result = ask_gemini(
            message=message,
            pdf_context="",
            conversation="",
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
    # 5. EXTRACT ALL PDF TEXT
    # =====================================================

    pdf_content = extract_all_pdf_text(pdf_files)

    if not pdf_content:
        return "⚠ Unable to read the uploaded PDF."

    cache_key = (tuple(pdf_files))

    if cache_key not in semantic_cache:
        semantic_cache[cache_key] = build_index(pdf_content)

    semantic_index, semantic_chunks = semantic_cache[cache_key]
    
    if DEBUG:
        print(f"📄 PDF Ready | Chunks: {len(semantic_chunks)}")
        
    # =====================================================
    # 6. PDF SUMMARY QUERY
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
            "summarize pdf",
            "summarize this resume",
            "brief summary",
            "give me an overview",
            "overview of the pdf"
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
    # 7. PDF METADATA QUERY
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
    # 8. DIRECT PDF FACT SEARCH
    # =====================================================

    direct_answer = find_direct_pdf_answer(
        question=message,
        pdf_content=pdf_content,
        pdf_files=pdf_files
    )


    if direct_answer:

        answer = (
            "📄 Source: Uploaded PDF\n\n"
            + direct_answer
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

    # ------------------------------------------------
    # 9. DYNAMIC PDF DETECTION
    # ------------------------------------------------

    pdf_related = is_relevant_to_pdf(
        question=message,
        semantic_index=semantic_index,
        semantic_chunks=semantic_chunks,
        min_score=SEMANTIC_MIN_SCORE
    )

    if DEBUG:
        print(f"PDF Related: {pdf_related}")
    
    # =====================================================
    # 10. PDF-RELATED QUESTION SEARCH
    # =====================================================

    if pdf_related:

        relevant_text = ""

        # -------------------------------------------------
        # STEP 1 : SECTION SEARCH
        # -------------------------------------------------

        section_text = find_section_content(
            question=message,
            pdf_content=pdf_content
        )

        if section_text:
            
            if DEBUG:
                print("PDF SECTION MATCH FOUND")

            pdf_section_answer = format_pdf_section_answer(
                question=message,
                section_text=section_text
            )

            if pdf_section_answer:

                answer = (
                    "📄 Source: Uploaded PDF\n\n"
                    + pdf_section_answer
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

            # Use section as Gemini context
            relevant_text = section_text


        # -------------------------------------------------
        # STEP 2 : SEMANTIC SEARCH
        # -------------------------------------------------

        if not relevant_text:

            try:

                relevant_text = semantic_search(
                    query=message,
                    index=semantic_index,
                    chunks=semantic_chunks,
                    top_k=SEMANTIC_TOP_K,
                    min_score=SEMANTIC_MIN_SCORE
                )

            except Exception as e:

                if DEBUG:
                    print("Semantic Search Error:", e)

                relevant_text = ""


        # -------------------------------------------------
        # STEP 3 : VALIDATE SEMANTIC RESULT
        # -------------------------------------------------

        if relevant_text:

            question_words = set(re.findall(r"\w+", message.lower()))
            context_words = set(re.findall(r"\w+", relevant_text.lower()))

            overlap = len(question_words & context_words)

            ratio = overlap / max(len(question_words), 1)

            if DEBUG:
                print(f"Overlap : {ratio:.2f}")

            if ratio < 0.30:
                relevant_text = ""


        # -------------------------------------------------
        # STEP 4 : ASK GEMINI USING PDF CONTEXT
        # -------------------------------------------------

        if relevant_text:

            result = ask_gemini(
                message=message,
                pdf_context=relevant_text[:MAX_PDF_CONTEXT],
                conversation=conversation,
                pdf_fallback=False
            )

            # ---------------------------------------------
            # GEMINI SUCCESS
            # ---------------------------------------------

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

            # ---------------------------------------------
            # GEMINI FAILED
            # ---------------------------------------------

            answer = (
                "📄 Source: Uploaded PDF\n\n"
                + pdf_context_fallback(
                    relevant_text[:MAX_PDF_CONTEXT]
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

        # -------------------------------------------------
        # STEP 5 : NO RELEVANT PDF CONTENT
        # -------------------------------------------------

        pass
        
    # =====================================================
    # 11. GENERAL GEMINI QUESTION
    # =====================================================
    
    result = ask_gemini(
        message=message,
        pdf_context="",
        conversation=conversation,
        pdf_fallback=False
    )


    # =====================================================
    # 12. GEMINI SUCCESS
    # =====================================================

    if result["success"]:

        answer = f"🤖 Source: Gemini AI\n\n{result['answer']}"

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
    # 13. GEMINI QUOTA ERROR
    # =====================================================

    if result["error_type"] == "quota":

        return (
            "⚠ Gemini API quota exceeded.\n\n"
            "Please wait and try again later "
            "or use another Gemini API key."
        )


    # =====================================================
    # 14. GEMINI BUSY ERROR
    # =====================================================

    if result["error_type"] == "busy":

        return (
            "⚠ Gemini server is currently busy.\n\n"
            "Please try again after a few seconds."
        )


    # =====================================================
    # 15. GEMINI OTHER ERROR
    # =====================================================

    return (
        "⚠ I couldn't generate a response at the moment. "
        "Please try again in a few seconds."
    )