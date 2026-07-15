from chat.chatbot import chatbot
from features.chat_statistics import get_statistics


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