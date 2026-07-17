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
MODEL_NAME = "gemini-2.5-flash"

def chatbot(message, history, pdf_files, progress=gr.Progress()):

    # ---------------------------------------
    # INITIALIZATION
    # ---------------------------------------
    time.sleep(0.1)
    progress(0.05, desc="🚀 Starting AI Assistant...")

    message = message.strip()
    conversation = build_conversation(history)

    if not message:
        return "Please enter a question."

    # ---------------------------------------
    # NORMAL GEMINI CHAT
    # ---------------------------------------
    if not pdf_files:

        progress(0.35, desc="🧠 Understanding your question...")

        try:

            response = None

            # Retry up to 3 times if Gemini server is busy
            for attempt in range(3):

                try:

                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=f"""
                    Previous Conversation:

                    {conversation}

                    Current Question:

                    {message}
                    """
                    )

                    break

                except Exception as e:

                    if "503" in str(e):

                        print(f"Gemini Busy... Retry {attempt+1}/3")

                        time.sleep(3)

                        continue

                    raise

            if response is None:

                return (
                    "🤖 Gemini server is currently busy.\n\n"
                    "Please try again in a few seconds."
                )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )

            save_session(message, answer)

            progress(1.0, desc="🎉 Response ready!")

            return answer

        except Exception as e:

            print("Gemini Error:", e)

            error = str(e)

            if "429" in error:

                return (
                    "⚠ Gemini API quota exceeded.\n"
                    "Please wait a few minutes or use another API key."
                )

            elif "503" in error:

                return (
                    "⚠ Gemini server is busy.\n"
                    "Please try again after a few seconds."
                )

            return (
                f"Gemini Error:\n{e}"
            )
    # ---------------------------------------
    # PDF MODE
    # ---------------------------------------
    progress(0.20, desc="📖 Reading uploaded PDFs...")

    question = message.lower()

    pdf_content = ""

    for pdf in pdf_files:
        pdf_content += "\n\n" + extract_pdf_text(pdf)
    
     # ---------------------------------------
    # SUMMARY
    # ---------------------------------------
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

        progress(1.0, desc="🎉 Response ready!")
        return summarize_pdf(pdf_files)
    
    
    # ---------------------------------------
    # PDF SIZE
    # ---------------------------------------
    if "pdf size" in question:

        progress(1.0, desc="🎉 Response ready!")

        result = []

        for pdf in pdf_files:

            size = round(os.path.getsize(pdf) / 1024, 2)

            result.append(
                f"{os.path.basename(pdf)} : {size} KB"
            )

        return "\n".join(result)

    # ---------------------------------------
    # WORD COUNT
    # ---------------------------------------
    if "word count" in question:

        progress(1.0, desc="🎉 Response ready!")

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"{os.path.basename(pdf)} : {len(text.split())} words"
            )

        return "\n".join(result)


    # ---------------------------------------
    # CHARACTER COUNT
    # ---------------------------------------
    if "character count" in question:

        progress(1.0, desc="🎉 Response ready!")

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"{os.path.basename(pdf)} : {len(text)} characters"
            )

        return "\n".join(result)
        
    # ---------------------------------------
    # PDF STATS
    # ---------------------------------------
    if "pdf stats" in question:

        progress(1.0, desc="🎉 Response ready!")

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            reader = PdfReader(pdf)

            result.append(
                f"""📄 {os.path.basename(pdf)}

    Title : {get_pdf_title(text)}
    Pages : {len(reader.pages)}
    Words : {len(text.split())}
    Characters : {len(text)}
    Size : {round(os.path.getsize(pdf)/1024,2)} KB
    """
            )

        return "\n\n".join(result)

    # -----------------------------
    # TOTAL QUESTIONS
    # -----------------------------
    if (
        "how many question" in question
        or "how many questions" in question
        or "total question" in question
    ):

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            match = re.search(
                r'1\s*[–-]\s*(\d+)',
                text
            )

            if match:

                result.append(
                    f"📄 {os.path.basename(pdf)} : {match.group(1)} questions"
                )

                continue

            questions = re.findall(
                r'^\d+\.',
                text,
                re.MULTILINE
            )

            if questions:

                result.append(
                    f"📄 {os.path.basename(pdf)} : {len(questions)} questions"
                )

        progress(1.0, desc="🎉 Response ready!")

        if result:
            return "\n".join(result)

        return "Question count not found."


    # -----------------------------
    # PDF TITLE
    # -----------------------------
    if (
        "pdf title" in question
        or "pdf name" in question
    ):

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : {get_pdf_title(text)}"
            )

        progress(1.0, desc="🎉 Response ready!")

        return "\n".join(result)


    # -----------------------------
    # PAGE COUNT
    # -----------------------------
    if "how many pages" in question:

        result = []

        for pdf in pdf_files:

            reader = PdfReader(pdf)

            result.append(
                f"📄 {os.path.basename(pdf)} : {len(reader.pages)} pages"
            )

        progress(1.0, desc="🎉 Response ready!")

        return "\n".join(result)


    # -----------------------------
    # CONTACT INFO
    # -----------------------------
    if (
        "contact" in question
        or "email" in question
        or "phone" in question
    ):

        result = []

        for pdf in pdf_files:

            text = extract_pdf_text(pdf)

            emails = re.findall(
                r'[\w\.-]+@[\w\.-]+\.\w+',
                text
            )

            phones = re.findall(
                r'(?:\+91[- ]?)?[6-9]\d{9}',
                text
            )

            if emails or phones:

                result.append(f"📄 {os.path.basename(pdf)}")

                result.extend(emails)
                result.extend(phones)

                result.append("")

        progress(1.0, desc="🎉 Response ready!")

        if result:
            return "\n".join(result)

        return "No contact information found."
        
     # -----------------------------
    # FIND RELEVANT PDF CONTENT
    # -----------------------------
    progress(0.50, desc="🔍 Searching relevant information...")

    relevant_text = find_relevant_text(
        pdf_content,
        message
    )

    print("=" * 60)
    print("QUESTION :", message)
    print("=" * 60)
    print("RELEVANT TEXT:")
    print(relevant_text if relevant_text else "NOT FOUND")
    print("=" * 60)

    # -----------------------------
    # NOT FOUND IN PDF
    # FALLBACK TO GEMINI
    # -----------------------------
    if not relevant_text:

        progress(0.75, desc="🤖 Consulting Gemini AI...")

        try:

            response = None

            # Retry if Gemini server is busy
            for attempt in range(3):

                try:

                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=f"""
Previous Conversation:

{conversation}

The uploaded PDF does not contain the answer.

Answer using your own knowledge.

Current Question:

{message}

    Answer:
    """
                    )

                    break

                except Exception as e:

                    if "503" in str(e):

                        print(f"Gemini Busy... Retry {attempt+1}/3")

                        time.sleep(3)

                        continue

                    raise

            if response is None:

                return (
                    "⚠ Gemini server is currently busy.\n\n"
                    "Please try again after a few seconds."
                )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )

            save_session(message, answer)

            progress(1.0, desc="🎉 Response ready!")

            return answer

        except Exception as e:

            print("Gemini Error:", e)

            error = str(e)

            if "429" in error:

                return (
                    "⚠ Gemini API quota exceeded.\n"
                    "Please wait a few minutes or use another API key."
                )

            elif "503" in error:

                return (
                    "⚠ Gemini server is busy.\n"
                    "Please try again after a few seconds."
                )

            return (
                f"Gemini Error:\n{e}"
            )
            
    # -----------------------------
    # PDF QA PROMPT
    # -----------------------------
    progress(0.80, desc="✍️ Preparing response...")

    prompt = f"""
You are an expert PDF Question Answering Assistant.

Your job is to answer ONLY from the PDF content below.

Rules:

1. Never use outside knowledge.
2. Never guess.
3. Never invent information.
4. If the answer is not present in the PDF, reply ONLY:

Information not found in uploaded PDF.

5. If the PDF contains:

• Definition → return the definition.
• Steps → return numbered steps.
• Bullet points → preserve bullets.
• Table → summarize the table.
• Comparison → use comparison format.

6. Keep answers clear and concise.

7. Do not repeat the question.

PDF Content:
{relevant_text}

Conversation History:

{conversation}

Question:

{message}

Answer:
"""

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        answer = response.text.strip()
        
        # ---------------------------------------
        # Fallback if PDF answer is too weak
        # ---------------------------------------
        pdf_confidence = len(re.findall(r"\w+", relevant_text))

        if (
            pdf_confidence < 20
            or "information not found" in answer.lower()
            or len(answer.strip()) < 30
        ):

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=message
            )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )

            
        else:

            answer = (
                "📄 Source: Uploaded PDF\n\n"
                + answer
            )
            

        progress(1.0, desc="🎉 Response ready!")

    except Exception as e:

        print("Gemini Error:", e)

        error = str(e)

        if "429" in error:
            return (
                "Gemini API quota exceeded.\n"
                "Please wait a few minutes or use another API key."
            )

        if "503" in error:
            return (
                "Gemini server is busy.\n"
                "Please try again after a few seconds."
            )

        return (
            f"Gemini Error:\n{e}"
            "Please try again later."
        )

    # -----------------------------
    # SAVE CHAT
    # -----------------------------
    save_session(message, answer)

    return answer