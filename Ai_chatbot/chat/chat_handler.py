from chat.chatbot import chatbot
from features.chat_statistics import (
    update_stats,
    get_statistics
)
import features.chat_statistics

print(features.chat_statistics.__file__)

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

    # Update statistics
    update_stats(answer)
    
    print("="*60)
    print(answer)
    print("="*60)

    return (
        history,
        "",
        get_statistics()
    )