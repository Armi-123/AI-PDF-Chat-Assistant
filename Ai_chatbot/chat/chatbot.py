import os
import re
import time
import gradio as gr

from pypdf import PdfReader

from config.gemini_config import client

from pdf.pdf_utils import (
    extract_pdf_text,
    get_pdf_title
)

from pdf.pdf_summary import summarize_pdf
from pdf.pdf_search import find_relevant_text

from features.chat_statistics import update_stats

from utils.chat_memory import (
    chat_history,
    SESSION_FILE
)

def chatbot(message, history, pdf_file, progress=gr.Progress()):

    # ---------------------------------------
    # INITIALIZATION
    # ---------------------------------------
    time.sleep(0.1)
    progress(0.05, desc="🚀 Starting AI Assistant...")

    message = message.strip()

    if not message:
        return "Please enter a question."

    # ---------------------------------------
    # NORMAL GEMINI CHAT
    # ---------------------------------------
    if pdf_file is None:

        try:

            progress(0.35, desc="🧠 Understanding your question...")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message
            )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )
            
            update_stats(answer, "gemini")

            chat_history.append(
                f"User: {message}\nAI: {answer}\n\n"
            )

            with open(
                SESSION_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                file.write(f"User: {message}\n")
                file.write(f"AI: {answer}\n")
                file.write("-" * 50 + "\n")

            progress(1.0, desc="🎉 Response ready!")

            return answer

        except Exception as e:

            print("Gemini Error:", e)

            return (
                "Gemini is temporarily unavailable.\n"
                "Please try again later."
            )
    # ---------------------------------------
    # PDF MODE
    # ---------------------------------------
    progress(0.20, desc="📖 Reading uploaded PDF...")
    
    pdf_content = extract_pdf_text(pdf_file)

    question = message.lower()
    
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
        return summarize_pdf(pdf_file)
    
    
    # ---------------------------------------
    # PDF SIZE
    # ---------------------------------------
    if "pdf size" in question:

        progress(1.0, desc="🎉 Response ready!")

        return (
            f"{round(os.path.getsize(pdf_file)/1024,2)} KB"
        )

    # ---------------------------------------
    # WORD COUNT
    # ---------------------------------------
    if "word count" in question:

        progress(1.0, desc="🎉 Response ready!")

        return (
            f"Total Words: {len(pdf_content.split())}"
        )

    # ---------------------------------------
    # CHARACTER COUNT
    # ---------------------------------------
    if "character count" in question:

        progress(1.0, desc="🎉 Response ready!")

        return (
            f"Total Characters: {len(pdf_content)}"
        )
        
    # ---------------------------------------
    # PDF STATS
    # ---------------------------------------
    if "pdf stats" in question:

        reader = PdfReader(pdf_file)

        progress(1.0, desc="🎉 Response ready!")

        return (
            f"Title: {get_pdf_title(pdf_content)}\n"
            f"Pages: {len(reader.pages)}\n"
            f"Words: {len(pdf_content.split())}\n"
            f"Characters: {len(pdf_content)}\n"
            f"Size: {round(os.path.getsize(pdf_file)/1024,2)} KB"
        )

    # -----------------------------
    # TOTAL QUESTIONS
    # -----------------------------
    if (
        "how many question" in question
        or "how many questions" in question
        or "total question" in question
    ):

        match = re.search(
            r'1\s*[–-]\s*(\d+)',
            pdf_content
        )

        if match:
            progress(1.0, desc="🎉 Response ready!")
            return f"There are {match.group(1)} questions."

        questions = re.findall(
            r'^\d+\.',
            pdf_content,
            re.MULTILINE
        )

        if questions:
            progress(1.0, desc="🎉 Response ready!")
            return f"There are {len(questions)} questions."

        progress(1.0, desc="🎉 Response ready!")
        return "Question count not found."


    # -----------------------------
    # PDF TITLE
    # -----------------------------
    if (
        "pdf title" in question
        or "pdf name" in question
    ):
        progress(1.0, desc="🎉 Response ready!")
        return f"PDF Title: {get_pdf_title(pdf_content)}"


    # -----------------------------
    # PAGE COUNT
    # -----------------------------
    if "how many pages" in question:

        reader = PdfReader(pdf_file)

        progress(1.0, desc="🎉 Response ready!")
        return f"Total Pages: {len(reader.pages)}"


    # -----------------------------
    # CONTACT INFO
    # -----------------------------
    if (
        "contact" in question
        or "email" in question
        or "phone" in question
    ):

        emails = re.findall(
            r'[\w\.-]+@[\w\.-]+\.\w+',
            pdf_content
        )

        phones = re.findall(
            r'(?:\+91[- ]?)?[6-9]\d{9}',
            pdf_content
        )

        result = []

        result.extend(emails)
        result.extend(phones)

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

        try:

            progress(0.75, desc="🤖 Consulting Gemini AI...")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"""
The uploaded PDF does not contain the answer.

Answer the following question using your own knowledge.

Question:
{message}
"""
            )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )
            update_stats(answer, "gemini")
            progress(1.0, desc="🎉 Response ready!")

            chat_history.append(
                f"User: {message}\nAI: {answer}\n\n"
            )

            with open(
                SESSION_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                file.write(f"User: {message}\n")
                file.write(f"AI: {answer}\n")
                file.write("-" * 50 + "\n")

            return answer

        except Exception as e:

            print("Gemini Error:", e)

            return (
                "Gemini is temporarily unavailable.\n"
                "Please try again later."
            )

    # -----------------------------
    # PDF QA PROMPT
    # -----------------------------
    progress(0.80, desc="✍️ Preparing response...")

    prompt = f"""
You are a PDF Question Answering Assistant.

STRICT RULES:

1. Answer ONLY using the PDF content.
2. Never use your own knowledge.
3. Never guess.
4. Never explain beyond the PDF.
5. If the answer is not clearly present, reply EXACTLY:

Information not found in uploaded PDF.

6. Keep the answer within 3-5 lines.

PDF Content:
{relevant_text}

Question:
{message}

Answer:
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        answer = response.text.strip()
        
        # ---------------------------------------
        # Fallback if PDF answer is too weak
        # ---------------------------------------
        if (
            not relevant_text.strip()
            or (
                len(relevant_text.strip()) < 80
                and "information not found" in answer.lower()
            )
        ):

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message
            )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )

            update_stats(answer, "gemini")
            
        else:

            answer = (
                "📄 Source: Uploaded PDF\n\n"
                + answer
            )
            
            update_stats(answer, "pdf")

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
            "Gemini is temporarily unavailable.\n"
            "Please try again later."
        )

    # -----------------------------
    # SAVE CHAT
    # -----------------------------
    chat_history.append(
        f"User: {message}\nAI: {answer}\n\n"
    )

    with open(
        SESSION_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(f"User: {message}\n")
        file.write(f"AI: {answer}\n")
        file.write("-" * 50 + "\n")

    return answer

