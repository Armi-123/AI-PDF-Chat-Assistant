import re


def generate_suggestions(pdf_text):

    """
    Generate smart questions based on PDF content.
    """

    suggestions = []

    text = pdf_text.lower()

    # ----------------------------------------------------
    # Default Suggestions
    # ----------------------------------------------------
    suggestions.extend([
        "📋 Summarize this PDF",
        "📖 What is the main topic?",
        "⭐ List important points"
    ])

    # ----------------------------------------------------
    # Power BI
    # ----------------------------------------------------
    if "power bi" in text:
        suggestions.append("💬 What is Power BI?")

    # ----------------------------------------------------
    # SQL
    # ----------------------------------------------------
    if "sql" in text:
        suggestions.append("💬 Explain SQL.")

    if "join" in text:
        suggestions.append("💬 Explain SQL Join.")

    # ----------------------------------------------------
    # Excel
    # ----------------------------------------------------
    if "excel" in text:
        suggestions.append("💬 Explain Excel.")

    # ----------------------------------------------------
    # Python
    # ----------------------------------------------------
    if "python" in text:
        suggestions.append("💬 Explain Python.")

    # ----------------------------------------------------
    # Machine Learning
    # ----------------------------------------------------
    if "machine learning" in text:
        suggestions.append("💬 What is Machine Learning?")

    # ----------------------------------------------------
    # Data Analytics
    # ----------------------------------------------------
    if "data analytics" in text:
        suggestions.append("💬 What is Data Analytics?")

    if "data analyst" in text:
        suggestions.append("💬 What are Data Analyst skills?")

    # ----------------------------------------------------
    # Interview Questions
    # ----------------------------------------------------
    if "interview" in text:
        suggestions.append("💬 What are important interview questions?")

    # ----------------------------------------------------
    # Remove duplicate suggestions
    # ----------------------------------------------------
    unique = []

    for item in suggestions:

        if item not in unique:
            unique.append(item)

    return "\n".join(unique)