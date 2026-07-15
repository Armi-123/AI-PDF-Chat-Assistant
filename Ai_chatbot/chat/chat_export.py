import os
from utils.chat_memory import (
    chat_history,
    EXPORT_DIR
)
from datetime import datetime

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