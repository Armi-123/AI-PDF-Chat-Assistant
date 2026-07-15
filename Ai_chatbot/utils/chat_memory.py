import os
from datetime import datetime

chat_history = []

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(EXPORT_DIR, exist_ok=True)

SESSION_FILE = os.path.join(
    EXPORT_DIR,
    f"chat_{datetime.now():%Y%m%d_%H%M%S}.txt"
)