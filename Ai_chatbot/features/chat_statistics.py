import time


# =====================================================
# GLOBAL STATISTICS
# =====================================================

start_time = time.time()

total_questions = 0
pdf_answers = 0
gemini_answers = 0
total_words = 0


# =====================================================
# UPDATE STATISTICS
# =====================================================

def update_stats(
    answer,
    source="unknown"
):

    global total_questions
    global pdf_answers
    global gemini_answers
    global total_words


    # -------------------------------------------------
    # COUNT TOTAL QUESTIONS
    # -------------------------------------------------

    total_questions += 1


    # -------------------------------------------------
    # COUNT ANSWER SOURCE
    # -------------------------------------------------

    if source == "pdf":

        pdf_answers += 1


    elif source == "gemini":

        gemini_answers += 1


    # -------------------------------------------------
    # COUNT GENERATED WORDS
    # -------------------------------------------------

    if answer:

        total_words += len(
            answer.split()
        )


# =====================================================
# GET STATISTICS
# =====================================================

def get_statistics():

    duration = int(
        time.time()
        - start_time
    )


    minutes = duration // 60

    seconds = duration % 60


    # -------------------------------------------------
    # DISPLAY COMPACT STATISTICS
    # -------------------------------------------------

    return f"""
### 📊 Chat Statistics

💬 Questions Asked: **{total_questions}** | 📄 PDF Answers: **{pdf_answers}** | 🤖 Gemini Answers: **{gemini_answers}**
"""