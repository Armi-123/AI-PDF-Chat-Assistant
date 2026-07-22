from chat.chatbot import chatbot

from features.chat_statistics import (
    update_stats,
    get_statistics
)

import features.chat_statistics


# =====================================================
# DEBUG: SHOW CHAT STATISTICS FILE LOCATION
# =====================================================

print(
    "Chat Statistics File:",
    features.chat_statistics.__file__
)


# =====================================================
# MAIN CHAT HANDLER
# =====================================================

def chat(message, history, pdf_file):
    """
    Handle chat requests from the Gradio UI.

    Flow:

    Gradio UI
        ↓
    chat_handler.chat()
        ↓
    chatbot()
        ↓
    PDF Search / Semantic Search / Gemini
        ↓
    Return updated chat history + statistics
    """

    # =================================================
    # INITIALIZE HISTORY
    # =================================================

    if history is None:
        history = []

    # =================================================
    # GET CHATBOT ANSWER
    # =================================================

    try:
        answer = chatbot(
            message,
            history,
            pdf_file
        )

    except Exception as e:
        print(
            "Chatbot Error:",
            e
        )

        answer = (
            "⚠ An unexpected error occurred while "
            "processing your question.\n\n"
            f"Error: {e}"
        )

    # =================================================
    # ADD USER MESSAGE
    # =================================================

    history.append(
        {
            "role": "user",
            "content": message
        }
    )

    # =================================================
    # ADD ASSISTANT RESPONSE
    # =================================================

    history.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    # =================================================
    # UPDATE CHAT STATISTICS
    # =================================================

    try:
        update_stats(
            answer
        )

    except Exception as e:
        print(
            "Statistics Error:",
            e
        )

    # =================================================
    # DEBUG OUTPUT
    # =================================================

    print(
        "=" * 60
    )

    print(
        "USER QUESTION:"
    )

    print(
        message
    )

    print(
        "-" * 60
    )

    print(
        "ASSISTANT ANSWER:"
    )

    print(
        answer
    )

    print(
        "=" * 60
    )

    # =================================================
    # GET CURRENT STATISTICS
    # =================================================

    try:
        statistics = get_statistics()

    except Exception as e:
        print(
            "Get Statistics Error:",
            e
        )

        statistics = ""

    # =================================================
    # RETURN TO GRADIO
    # =================================================

    return (
        history,
        "",
        statistics
    )