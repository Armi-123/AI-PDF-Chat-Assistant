import os
import gradio as gr
from google import genai
from dotenv import load_dotenv
from pypdf import PdfReader
import re
import time
from features.smart_suggestions import generate_suggestions
from features.chat_statistics import (
    update_stats,
    get_statistics
)
from pdf.pdf_search import find_relevant_text
from pdf.pdf_utils import get_pdf_title,extract_pdf_text
from pdf.pdf_summary import summarize_pdf
from chat.chatbot import chatbot
from chat.chat_export import save_chat

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

    return history, "", get_statistics()

def load_suggestions(pdf_file):

    if pdf_file is None:
        return ""

    pdf_text = extract_pdf_text(pdf_file)

    return generate_suggestions(pdf_text)

with gr.Blocks(title="AI PDF Chat Assistant") as demo:

    gr.Markdown("# 🤖 AI PDF Chat Assistant")

    # -----------------------------
    # Upload PDF
    # -----------------------------
    pdf_file = gr.File(
        label="📄 Upload PDF",
        type="filepath"
    )

    # -----------------------------
    # PDF Summary
    # -----------------------------
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
    
    # -----------------------------
    # SMART SUGGESTIONS
    # -----------------------------
      
    suggestions_output = gr.Textbox(
        label="💡 Smart Suggestions",
        lines=8,
        interactive=False
    )

    pdf_file.change(
        fn=load_suggestions,
        inputs=pdf_file,
        outputs=suggestions_output
    )
    
    statistics_output = gr.Markdown(
        value=get_statistics(),
        label="📊 Chat Statistics"
    )
    
    # -----------------------------
    # Chatbot
    # -----------------------------
    chatbot_ui = gr.Chatbot(
        label="💬 PDF Chat",
        height=550,
        type="messages",
        show_copy_button=True
    )

    msg = gr.Textbox(
        label="Ask Question",
        placeholder="Ask anything about the uploaded PDF..."
    )

    with gr.Row():

        send_btn = gr.Button(
            "📨 Send",
            variant="primary"
        )

        clear_btn = gr.Button(
            "🗑️ Clear Chat"
        )

        export_btn = gr.Button(
            "💾 Export Chat"
        )

    export_output = gr.Textbox(
        label="Export Status"
    )

    # -----------------------------
    # Send
    # -----------------------------
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

    # -----------------------------
    # Clear Chat
    # -----------------------------
    clear_btn.click(
        lambda: ([], ""),
        outputs=[chatbot_ui, msg]
    )

    # -----------------------------
    # Export
    # -----------------------------
    export_btn.click(
        fn=save_chat,
        outputs=export_output
    )

demo.launch(
    share=False,
    debug=True
)