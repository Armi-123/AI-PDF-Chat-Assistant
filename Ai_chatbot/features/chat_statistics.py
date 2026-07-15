import time

# -----------------------------
# CHAT STATS
# -----------------------------

stats = {
    "questions": 0,
    "pdf_answers": 0,
    "gemini_answers": 0,
    "words_generated": 0,
    "start_time": time.time()
}


def update_stats(answer, source):

    stats["questions"] += 1

    if source == "pdf":
        stats["pdf_answers"] += 1

    elif source == "gemini":
        stats["gemini_answers"] += 1

    stats["words_generated"] += len(answer.split())


def get_statistics():

    duration = int(time.time() - stats["start_time"])

    minutes = duration // 60
    seconds = duration % 60

    return f"""
## 📊 Chat Statistics

💬 Questions Asked : **{stats['questions']}**

📄 PDF Answers : **{stats['pdf_answers']}**

🤖 Gemini Answers : **{stats['gemini_answers']}**

📝 Words Generated : **{stats['words_generated']}**

⏱ Chat Duration : **{minutes}m {seconds}s**
"""