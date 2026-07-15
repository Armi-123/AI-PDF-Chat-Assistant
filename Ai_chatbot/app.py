import gradio as gr

from chat.chat_handler import chat
from chat.chat_export import save_chat

from pdf.pdf_summary import summarize_pdf

from features.smart_suggestions import load_suggestions
from features.chat_statistics import get_statistics

with gr.Blocks(
    title="AI PDF Chat Assistant"
) as demo:

    gr.Markdown("# 🤖 AI PDF Chat Assistant")

    # =====================================================
    # PDF UPLOAD
    # =====================================================
    pdf_file = gr.File(
        label="📄 Upload PDF",
        type="filepath"
    )

    # =====================================================
    # PDF ANALYSIS
    # =====================================================
    gr.Markdown("## 📄 PDF Analysis")

    summary_output = gr.Textbox(
        label="📋 PDF Summary",
        lines=15,
        interactive=False
    )

    summarize_btn = gr.Button(
        "📋 Summarize PDF"
    )

    summarize_btn.click(
        fn=summarize_pdf,
        inputs=pdf_file,
        outputs=summary_output
    )

    # =====================================================
    # SMART SUGGESTIONS
    # =====================================================
    suggestions_output = gr.Textbox(
        label="💡 Smart Suggestions",
        lines=6,
        interactive=False
    )

    pdf_file.change(
        fn=load_suggestions,
        inputs=pdf_file,
        outputs=suggestions_output
    )

    # =====================================================
    # CHAT STATISTICS
    # =====================================================
    statistics_output = gr.Markdown(
        value=get_statistics()
    )

    # =====================================================
    # CHAT SECTION
    # =====================================================
    gr.Markdown("## 💬 Chat with PDF")

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

    # =====================================================
    # BUTTONS
    # =====================================================
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

    export_output = gr.Markdown(
        label="Export Status"
    )

    # =====================================================
    # SEND MESSAGE
    # =====================================================
    msg.submit(
        fn=chat,
        inputs=[
            msg,
            chatbot_ui,
            pdf_file
        ],
        outputs=[
            chatbot_ui,
            msg,
            statistics_output
        ]
    )

    send_btn.click(
        fn=chat,
        inputs=[
            msg,
            chatbot_ui,
            pdf_file
        ],
        outputs=[
            chatbot_ui,
            msg,
            statistics_output
        ]
    )

    # =====================================================
    # CLEAR CHAT
    # =====================================================
    clear_btn.click(
        fn=lambda: (
            [],
            "",
            get_statistics()
        ),
        outputs=[
            chatbot_ui,
            msg,
            statistics_output
        ]
    )

    # =====================================================
    # EXPORT CHAT
    # =====================================================
    export_btn.click(
        fn=save_chat,
        outputs=export_output
    )

demo.launch(
    share=False,
    debug=True
)