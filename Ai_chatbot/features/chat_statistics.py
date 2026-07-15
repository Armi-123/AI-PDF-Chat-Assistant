import time

# -----------------------------
# Global Statistics
# -----------------------------

start_time = time.time()

total_questions = 0
pdf_answers = 0
gemini_answers = 0
total_words = 0


# -----------------------------
# Update Statistics
# -----------------------------
def update_stats(answer):

    global total_questions
    global pdf_answers
    global gemini_answers
    global total_words

    print("Before:", total_questions)

    total_questions += 1

    if "📄 Source: Uploaded PDF" in answer:
        pdf_answers += 1
    elif "🤖 Source: Gemini AI" in answer:
        gemini_answers += 1

    total_words += len(answer.split())

    print("After:", total_questions)


# -----------------------------
# Get Statistics
# -----------------------------
def get_statistics():

    duration = int(time.time() - start_time)

    minutes = duration // 60
    seconds = duration % 60

    return f"""
### 📊 Chat Statistics

💬 Questions Asked : **{total_questions}**

📄 PDF Answers : **{pdf_answers}**

🤖 Gemini Answers : **{gemini_answers}**

📝 Words Generated : **{total_words}**

⏱ Chat Duration : **{minutes}m {seconds}s**
"""