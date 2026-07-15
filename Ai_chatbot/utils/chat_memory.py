import os
from datetime import datetime

# -----------------------------
# Chat Memory
# -----------------------------

chat_history = []

# -----------------------------
# Export Directory
# -----------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(EXPORT_DIR, exist_ok=True)

# -----------------------------
# Session File
# -----------------------------

SESSION_FILE = os.path.join(
    EXPORT_DIR,
    f"chat_{datetime.now():%Y%m%d_%H%M%S}.txt"
)

# -----------------------------
# Save Chat Session
# -----------------------------

def save_session(user_message, ai_answer):
    """
    Save every chat message into memory
    and write it to the current session file.
    """

    record = (
        f"User: {user_message}\n"
        f"AI: {ai_answer}\n"
        + "-" * 50 + "\n"
    )

    chat_history.append(record)

    with open(
        SESSION_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(record)