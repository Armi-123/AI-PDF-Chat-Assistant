import os
import re
import time

import gradio as gr
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


# =====================================================
# CLEAN SOURCE LABEL
# =====================================================

def clean_source_labels(answer):
    """
    Remove duplicate source labels returned by Gemini.
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
# DIRECT PDF FACT SEARCH
# =====================================================

def find_direct_pdf_answer(
    question,
    pdf_content
):
    """
    Handle simple factual questions directly
    from extracted PDF text.

    This reduces unnecessary Gemini API calls.
    """

    question = question.lower()

    # =================================================
    # CANDIDATE / PERSON NAME
    # =================================================

    if (
        "candidate name" in question
        or "candidate's name" in question
        or "person name" in question
        or "person's name" in question
        or "what is the name" in question
        or "who is the candidate" in question
        or "who is the person" in question
    ):

        title = get_pdf_title(pdf_content)

        if (
            title
            and title != "Unknown PDF"
        ):

            return title


    # =================================================
    # EMAIL
    # =================================================

    if (
        "email" in question
        or "email address" in question
    ):

        emails = re.findall(
            r'[\w\.-]+@[\w\.-]+\.\w+',
            pdf_content
        )

        if emails:
            return "\n".join(dict.fromkeys(emails))


    # =================================================
    # PHONE NUMBER
    # =================================================

    if (
        "phone" in question
        or "mobile" in question
        or "contact number" in question
        or "phone number" in question
    ):

        phones = re.findall(
            r'(?:\+91[\s-]?)?[6-9]\d{9}',
            pdf_content
        )

        if phones:
            return "\n".join(dict.fromkeys(phones))


    # =================================================
    # LINKEDIN
    # =================================================

    if "linkedin" in question:

        linkedin = re.findall(
            r'https?://(?:www\.)?linkedin\.com/[^\s]+',
            pdf_content,
            re.IGNORECASE
        )

        if linkedin:

            return "\n".join(dict.fromkeys(linkedin))


    # =================================================
    # GITHUB
    # =================================================

    if "github" in question:

        github = re.findall(
            r'https?://(?:www\.)?github\.com/[^\s]+',
            pdf_content,
            re.IGNORECASE
        )

        if github:

            return "\n".join(dict.fromkeys(github))
        
    return ""


# =====================================================
# GEMINI API CALL
# =====================================================

def ask_gemini(
    message,
    conversation="",
    pdf_fallback=False
):
    """
    Send request to Gemini with retry handling.
    """

    if pdf_fallback:

        contents = f"""
Previous Conversation:

{conversation}

The uploaded PDF does not contain reliable information
needed to answer the question.

Answer using your own general knowledge.

Current Question:

{message}

Answer:
"""

    else:

        contents = f"""
Previous Conversation:

{conversation}

Current Question:

{message}

Answer:
"""


    response = None


    # =================================================
    # RETRY FOR GEMINI SERVER BUSY
    # =================================================

    for attempt in range(3):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents
            )

            break

        except Exception as e:

            error = str(e)

            if "503" in error:

                print(
                    f"Gemini Busy... "
                    f"Retry {attempt + 1}/3"
                )

                time.sleep(3)

                continue
            raise

    if response is None:

        return (
            "⚠ Gemini server is currently busy.\n\n"
            "Please try again in a few seconds."
        )

    answer = response.text.strip()
    answer = clean_source_labels(
        answer
    )


    return ("🤖 Source: Gemini AI\n\n"+ answer)


# =====================================================
# CHATBOT
# =====================================================

def chatbot(message,history,pdf_files,
    progress=gr.Progress()
):

    # =================================================
    # INITIALIZATION
    # =================================================

    time.sleep(0.1)

    progress(0.05,desc="🚀 Starting AI Assistant...")

    message = (message or "").strip()

    conversation = build_conversation(history)

    if not message:

        return ("Please enter a question.")


    # =================================================
    # NORMAL GEMINI CHAT
    # =================================================

    if not pdf_files:

        progress(0.35,desc="🧠 Understanding your question...")


        try:
            answer = ask_gemini(
                message,
                conversation,
                pdf_fallback=False
            )

            save_session(message,answer)

            progress(1.0,desc="🎉 Response ready!")

            return answer

        except Exception as e:

            print("Gemini Error:",e)

            error = str(e)

            if "429" in error:

                return (
                    "⚠ Gemini API quota exceeded.\n\n"
                    "Please wait and try again later "
                    "or use another API key."
                )

            if "503" in error:

                return (
                    "⚠ Gemini server is busy.\n\n"
                    "Please try again after a few seconds."
                )

            return (f"Gemini Error:\n{e}")

    # =================================================
    # PDF MODE
    # =================================================

    progress(0.20,desc="📖 Reading uploaded PDFs...")
    question = message.lower()
    pdf_content = ""

    # =================================================
    # EXTRACT ALL PDF TEXT
    # =================================================

    for pdf in pdf_files:

        try:

            text = extract_pdf_text(pdf)

            if text:
                pdf_content += ("\n\n"+ text)

        except Exception as e:

            print(f"PDF Extraction Error ({pdf}):",e)


    if not pdf_content.strip():

        return (
            "⚠ Unable to extract text "
            "from the uploaded PDF."
        )


    # =================================================
    # BUILD SEMANTIC SEARCH INDEX
    # =================================================

    progress(0.30,desc="🧠 Preparing PDF search...")

    index, chunks = build_index(
        pdf_content
    )


    # =================================================
    # SUMMARY
    # =================================================

    if any(
        word in question
        for word in [
            "summary",
            "summarize",
            "summarise",
            "brief",
            "overview",
            "short summary"
        ]
    ):

        progress(0.90,desc="📋 Generating PDF summary...")

        answer = summarize_pdf(pdf_files)
        save_session(message, answer)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # PDF SIZE
    # =================================================

    if (
        "pdf size" in question
        or "file size" in question
    ):

        result = []

        for pdf in pdf_files:

            size = round(
                os.path.getsize(pdf)
                / 1024,
                2
            )


            result.append(
                f"📄 {os.path.basename(pdf)} : "
                f"{size} KB"
            )


        answer = "\n".join(result)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # WORD COUNT
    # =================================================

    if (
        "word count" in question
        or "number of words" in question
        or "how many words" in question
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : "
                f"{len(text.split())} words"
            )


        answer = "\n".join(result)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # CHARACTER COUNT
    # =================================================

    if (
        "character count" in question
        or "number of characters" in question
        or "how many characters" in question
    ):

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : "
                f"{len(text)} characters"
            )


        answer = "\n".join(result)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # PDF STATS
    # =================================================

    if "pdf stats" in question:

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            reader = PdfReader(pdf)

            result.append(f"""📄 {os.path.basename(pdf)}

Title : {get_pdf_title(text)}
Pages : {len(reader.pages)}
Words : {len(text.split())}
Characters : {len(text)}
Size : {round(os.path.getsize(pdf) / 1024, 2)} KB"""
            )

        answer = "\n\n".join(result)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # TOTAL QUESTIONS
    # =================================================

    if (
        "how many question" in question
        or "how many questions" in question
        or "total question" in question
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            match = re.search(r'1\s*[–-]\s*(\d+)',text)

            if match:

                result.append(
                    f"📄 {os.path.basename(pdf)} : "
                    f"{match.group(1)} questions"
                )

                continue

            questions = re.findall(
                r'^\d+\.',
                text,
                re.MULTILINE
            )

            if questions:

                result.append(
                    f"📄 {os.path.basename(pdf)} : "
                    f"{len(questions)} questions"
                )

        progress(1.0,desc="🎉 Response ready!")

        if result:
            return "\n".join(result)

        return ("Question count not found.")

    # =================================================
    # PDF TITLE
    # =================================================

    if (
        "pdf title" in question
        or "pdf name" in question
    ):

        result = []


        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : "
                f"{get_pdf_title(text)}"
            )

        answer = "\n".join(result)
        
        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # PAGE COUNT
    # =================================================

    if (
        "how many pages" in question
        or "page count" in question
    ):

        result = []

        for pdf in pdf_files:

            reader = PdfReader(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : "
                f"{len(reader.pages)} pages"
            )

        answer = "\n".join(result)

        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # CONTACT INFORMATION
    # =================================================

    if (
        "contact" in question
        or "email" in question
        or "phone" in question
        or "mobile" in question
    ):

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(
                pdf
            )

            emails = re.findall(
                r'[\w\.-]+@[\w\.-]+\.\w+',
                text
            )

            phones = re.findall(
                r'(?:\+91[\s-]?)?[6-9]\d{9}',
                text
            )

            if emails or phones:

                result.append(f"📄 {os.path.basename(pdf)}")

                result.extend(emails)
                result.extend(phones)
                result.append("")

        progress(1.0,desc="🎉 Response ready!")

        if result:

            return "\n".join(result)

        return ("No contact information found.")

    # =================================================
    # DIRECT PDF FACT SEARCH
    # =================================================

    progress(0.40,desc="🔎 Checking direct PDF information...")

    direct_answer = find_direct_pdf_answer(question,pdf_content)

    if direct_answer:

        answer = ("📄 Source: Uploaded PDF\n\n"+ direct_answer)

        save_session(message, answer)
        
        progress(1.0,desc="🎉 Response ready!")

        return answer

    # =================================================
    # SEMANTIC SEARCH
    # =================================================

    progress(0.50,desc="🧠 Searching PDF semantically...")

    relevant_text = semantic_search(
        message,
        index,
        chunks,
        top_k=5,
        min_score=0.30
    )

    # =================================================
    # KEYWORD SEARCH FALLBACK
    # =================================================

    if not relevant_text.strip():

        progress(0.60,desc="🔍 Trying keyword search...")

        relevant_text = find_relevant_text(
            pdf_content,
            message
        )

    # =================================================
    # DEBUG INFORMATION
    # =================================================

    print("=" * 60)
    print("QUESTION:",message)
    print("SEMANTIC / KEYWORD RESULT:")
    print(
        relevant_text
        if relevant_text
        else "NOT FOUND"
    )
    print("=" * 60)


    # =================================================
    # PDF NOT FOUND → GEMINI FALLBACK
    # =================================================

    if not relevant_text.strip():

        progress(0.75,desc="🤖 Information not found in PDF...")

        try:

            answer = ask_gemini(
                message,
                conversation,
                pdf_fallback=True
            )

            save_session(message, answer)
                
            progress(1.0,desc="🎉 Response ready!")

            return answer

        except Exception as e:

            print("Gemini Error:",e)

            error = str(e)

            if "429" in error:

                return (
                    "⚠ Gemini API quota exceeded.\n\n"
                    "Please wait and try again later "
                    "or use another API key."
                )

            if "503" in error:

                return (
                    "⚠ Gemini server is busy.\n\n"
                    "Please try again after a few seconds."
                )

            return (
                f"Gemini Error:\n{e}"
            )

    # =================================================
    # PDF QUESTION ANSWERING
    # =================================================

    progress(0.80,desc="✍️ Preparing PDF answer...")


    prompt = f"""
You are an expert PDF Question Answering Assistant.

Your task is to answer the user's question using
ONLY the provided PDF content.

IMPORTANT RULES:

1. Use ONLY the PDF context below.
2. Never use outside knowledge.
3. Never guess.
4. Never invent information.
5. If the answer is not present in the provided context,
   reply exactly:

Information not found in uploaded PDF.

6. Keep the answer clear and concise.
7. Do not repeat the question.
8. If the PDF contains a definition, explain the definition.
9. If the PDF contains steps, use numbered steps.
10. If the PDF contains bullet points, preserve them.
11. If the PDF contains a comparison, use a comparison format.
12. If the answer contains a list, use bullet points.

PDF Context:

{relevant_text}

Conversation History:

{conversation}

User Question:

{message}

Answer:
"""

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        answer = response.text.strip()

        # ---------------------------------------------
        # Remove duplicate source labels
        # ---------------------------------------------

        answer = clean_source_labels(answer)

        # ---------------------------------------------
        # Check if Gemini says answer is not found
        # ---------------------------------------------

        not_found_phrases = [
            "information not found in uploaded pdf",
            "information not found",
            "not present in the pdf",
            "not mentioned in the pdf",
            "not available in the pdf"
        ]

        answer_lower = answer.lower()

        if any(
            phrase in answer_lower
            for phrase in not_found_phrases
        ):

            progress(0.90,desc="🤖 PDF answer unavailable...")

            # -----------------------------------------
            # Try keyword search once more
            # -----------------------------------------

            keyword_text = find_relevant_text(
                pdf_content,
                message
            )

            if (
                keyword_text
                and keyword_text.strip()
                and keyword_text.strip()
                != relevant_text.strip()
            ):

                retry_prompt = f"""
Answer the question using ONLY this PDF content.

PDF Content:

{keyword_text}

Question:

{message}

If the answer is not present, reply exactly:

Information not found in uploaded PDF.
"""

                retry_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=retry_prompt
                )


                retry_answer = (
                    retry_response.text.strip()
                )


                retry_answer = clean_source_labels(
                    retry_answer
                )


                if not any(
                    phrase in retry_answer.lower()
                    for phrase in not_found_phrases
                ):

                    answer = retry_answer

                else:
                    answer = None
                    
            else:
                answer = None


            # -----------------------------------------
            # True Gemini fallback
            # -----------------------------------------

            if not answer:

                answer = ask_gemini(
                    message,
                    conversation,
                    pdf_fallback=True
                )

                save_session(message,answer)

                progress(1.0,desc="🎉 Response ready!")

                return answer


        # =================================================
        # PDF ANSWER
        # =================================================

        answer = (
            "📄 Source: Uploaded PDF\n\n"
            + answer
        )

        progress(1.0,desc="🎉 Response ready!")


    except Exception as e:

        print("Gemini Error:",e)

        error = str(e)

        if "429" in error:

            return (
                "⚠ Gemini API quota exceeded.\n\n"
                "Please wait and try again later "
                "or use another API key."
            )

        if "503" in error:

            return (
                "⚠ Gemini server is busy.\n\n"
                "Please try again after a few seconds."
            )


        return (f"Gemini Error:\n{e}")

    # =================================================
    # SAVE CHAT
    # =================================================

    save_session(message,answer)

    return answer