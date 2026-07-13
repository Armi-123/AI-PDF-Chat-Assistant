import os
import gradio as gr
from google import genai
from dotenv import load_dotenv
from pypdf import PdfReader
import re
import time

# Load API Key
load_dotenv()

if os.getenv("GEMINI_API_KEY"):
    print("Gemini API Loaded Successfully")
else:
    print("Gemini API Key Not Found")

from datetime import datetime

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# Store chat history
chat_history = []

pdf_cache = {}

# Export folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(EXPORT_DIR, exist_ok=True)

CHAT_FILE = os.path.join(EXPORT_DIR, "chat_history.txt")

SESSION_FILE = os.path.join(
    EXPORT_DIR,
    f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
)

def get_pdf_title(pdf_text):

    lines = pdf_text.split("\n")

    for line in lines:
        line = line.strip()

        if len(line) < 5:
            continue

        if line.isdigit():
            continue

        return line

    return "Unknown PDF"

def chatbot(message, history, pdf_file, progress=gr.Progress()):

    # ---------------------------------------
    # INITIALIZATION
    # ---------------------------------------
    time.sleep(0.1)
    progress(0.05, desc="Initializing...")

    message = message.strip()

    if not message:
        return "Please enter a question."

    # ---------------------------------------
    # NORMAL GEMINI CHAT
    # ---------------------------------------
    if pdf_file is None:

        try:

            progress(0.40, desc="Thinking...")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message
            )

            answer = (
                "🤖 Source: Gemini AI\n\n"
                + response.text.strip()
            )

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

            progress(1.0, desc="Completed ✅")

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
    progress(0.20, desc="Reading PDF...")

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

        progress(1.0, desc="Completed ✅")
        return summarize_pdf(pdf_file)
    
    
    # ---------------------------------------
    # PDF SIZE
    # ---------------------------------------
    if "pdf size" in question:

        progress(1.0, desc="Completed ✅")

        return (
            f"{round(os.path.getsize(pdf_file)/1024,2)} KB"
        )

    # ---------------------------------------
    # WORD COUNT
    # ---------------------------------------
    if "word count" in question:

        progress(1.0, desc="Completed ✅")

        return (
            f"Total Words: {len(pdf_content.split())}"
        )

    # ---------------------------------------
    # CHARACTER COUNT
    # ---------------------------------------
    if "character count" in question:

        progress(1.0, desc="Completed ✅")

        return (
            f"Total Characters: {len(pdf_content)}"
        )
        
    # ---------------------------------------
    # PDF STATS
    # ---------------------------------------
    if "pdf stats" in question:

        reader = PdfReader(pdf_file)

        progress(1.0, desc="Completed ✅")

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
            progress(1.0, desc="Completed ✅")
            return f"There are {match.group(1)} questions."

        questions = re.findall(
            r'^\d+\.',
            pdf_content,
            re.MULTILINE
        )

        if questions:
            progress(1.0, desc="Completed ✅")
            return f"There are {len(questions)} questions."

        progress(1.0, desc="Completed ✅")
        return "Question count not found."


    # -----------------------------
    # PDF TITLE
    # -----------------------------
    if (
        "pdf title" in question
        or "pdf name" in question
    ):
        progress(1.0, desc="Completed ✅")
        return f"PDF Title: {get_pdf_title(pdf_content)}"


    # -----------------------------
    # PAGE COUNT
    # -----------------------------
    if "how many pages" in question:

        reader = PdfReader(pdf_file)

        progress(1.0, desc="Completed ✅")
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

        progress(1.0, desc="Completed ✅")

        if result:
            return "\n".join(result)

        return "No contact information found."
    
     # -----------------------------
    # FIND RELEVANT PDF CONTENT
    # -----------------------------
    progress(0.50, desc="Searching PDF...")

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

            progress(0.80, desc="Using Gemini AI...")

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

            progress(1.0, desc="Completed ✅")

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
    progress(0.80, desc="Generating Answer...")

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
            len(relevant_text.strip()) < 80
            and "information not found" in answer.lower()
        ):

            response = client.models.generate_content(
                model="gemini-2.5-flash",
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

        progress(1.0, desc="Completed ✅")

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

def summarize_pdf(pdf_file):

    pdf_content = extract_pdf_text(pdf_file)

    if not pdf_content:
        return "Please upload a PDF first."

    prompt = f"""
    You are a PDF Summarization Assistant.

    Rules:
    1. Summarize ONLY the uploaded PDF.
    2. Do NOT use outside knowledge.
    3. Use clear bullet points.
    4. Include:
    - Main topics
    - Important definitions
    - Key concepts
    - Tools/Technologies (if any)
    - Important conclusions
    5. Do not skip major sections.
    6. Keep the summary concise and well organized.

    PDF Content:
    {pdf_content[:50000]}
    """

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        print("Summary Error:", e)

        lines = [
            para.strip()
            for para in re.split(r'\n\s*\n', pdf_content)
            if para.strip()
        ]

        summary = "\n".join(
            [f"• {line[:250]}" for line in lines[:15]]
        )

        return summary
    
def save_chat():

    if not chat_history:
        return "No chat available to export."

    filename = os.path.join(
        EXPORT_DIR,
        f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    with open(filename, "w", encoding="utf-8") as file:
        file.writelines(chat_history)

    return (
        "✅ Chat exported successfully.\n\n"
        f"Location:\n{filename}"
    )

def extract_pdf_text(pdf_file):

    if pdf_file is None:
        return ""

    if pdf_file in pdf_cache:
        return pdf_cache[pdf_file]

    text = ""

    try:

        reader = PdfReader(pdf_file)

        for page_number, page in enumerate(reader.pages, start=1):

            page_text = page.extract_text()

            if page_text:

                text += (
                    page_text
                    + "\n"
                )

        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()

        pdf_cache[pdf_file] = text

    except Exception as e:
        print("PDF Error:", e)

    return text
  
def find_relevant_text(pdf_text, question):

    # -----------------------------
    # Split PDF into lines
    # -----------------------------
    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    # -----------------------------
    # Create chunks (20 lines each)
    # -----------------------------
    chunk_size = 20

    chunks = []

    for i in range(0, len(lines), chunk_size):

        chunk = "\n".join(
            lines[i:i + chunk_size]
        )

        chunks.append(chunk)

    # -----------------------------
    # Normalize question
    # -----------------------------
    question = question.lower()

    replacements = {
        "ai": "artificial intelligence",
        "ml": "machine learning",
        "db": "database",
        "powerbi": "power bi"
    }

    for old, new in replacements.items():
        question = question.replace(old, new)

    # -----------------------------
    # Stop Words
    # -----------------------------
    stop_words = {
        "what","is","the","a","an","of",
        "how","many","who","where","when",
        "does","do","are","in","on","for",
        "tell","me","pdf","uploaded",
        "please","can","could","would",
        "give","define","describe",
        "about","from","their","there",
        "this","that","explain",
        "difference","between"
    }

    question_words = {
        word
        for word in re.findall(r"\w+", question)
        if word not in stop_words
    }

    # -----------------------------
    # Score each chunk
    # -----------------------------
    scored = []

    for chunk in chunks:

        text = chunk.lower()

        score = 0

        for word in question_words:

            if word in text:
                score += 2

        if question in text:
            score += 10

        if score > 0:
            scored.append((score, chunk))

    # -----------------------------
    # Sort by score
    # -----------------------------
    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # -----------------------------
    # No relevant content
    # -----------------------------
    if not scored:
        return ""

    if scored[0][0] < 6:
        return ""

    # -----------------------------
    # Take Top 3 chunks
    # -----------------------------
    result = []

    seen = set()

    for score, chunk in scored:

        if chunk not in seen:

            seen.add(chunk)

            result.append(chunk)

        if len(result) == 3:
            break

    # -----------------------------
    # Return Relevant Text
    # -----------------------------
    return "\n\n".join(result)[:6000]

def chat(message, history, pdf_file):

    if history is None:
        history = []

    answer = chatbot(
        message,
        history,
        pdf_file
    )

    history.append({
        "role": "user",
        "content": message
    })

    history.append({
        "role": "assistant",
        "content": answer
    })

    return history, ""

with gr.Blocks() as demo:

    gr.Markdown("# 🤖 AI PDF Chat Assistant")

    pdf_file = gr.File(
        label="📄 Upload PDF",
        type="filepath"
    )

    summary_output = gr.Textbox(
        label="📋 PDF Summary",
        lines=10
    )

    summarize_btn = gr.Button("📋 Summarize PDF")

    summarize_btn.click(
        fn=summarize_pdf,
        inputs=pdf_file,
        outputs=summary_output
    )

    chatbot_ui = gr.Chatbot(
        label="💬 PDF Chat",
        height=500,
        type="messages"
    )
    msg = gr.Textbox(
        label="Ask Question",
        placeholder="Ask question from uploaded PDF..."
    )

    send_btn = gr.Button("Send")
    
    msg.submit(
        fn=chat,
        inputs=[msg, chatbot_ui, pdf_file],
        outputs=[chatbot_ui, msg]
    )

    send_btn.click(
        fn=chat,
        inputs=[msg, chatbot_ui, pdf_file],
        outputs=[chatbot_ui, msg]
    )
    
    export_btn = gr.Button("💾 Export Chat")

    export_output = gr.Textbox(
        label="Export Status"
    )

    export_btn.click(
        fn=save_chat,
        outputs=export_output
    )
    
demo.launch(
    share=False,
    debug=True
)