from dotenv import load_dotenv
from google import genai
import os

from pdf.pdf_utils import extract_pdf_text

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# =====================================================
# AI RESUME REVIEW
# =====================================================

def review_resume(pdf_files):
    """
    Review uploaded resume using Gemini AI.

    Returns:
        Markdown formatted ATS review.
    """

    if not pdf_files:

        return (
            "⚠ Please upload a resume first."
        )

    try:

        pdf_text = ""

        for pdf in pdf_files:

            pdf_text += (
                extract_pdf_text(pdf)
                + "\n\n"
            )

        if not pdf_text.strip():

            return (
                "⚠ Unable to extract text from the uploaded resume."
            )

    except Exception as e:

        return (
            f"⚠ Resume extraction failed.\n\n{e}"
        )


    # =====================================================
    # GEMINI PROMPT
    # =====================================================

    prompt = f"""
You are an experienced ATS Resume Reviewer, HR Manager,
Technical Recruiter and Career Coach.

Analyze the following resume.

Resume:

{pdf_text}

Return ONLY markdown.

Use this exact format.

# ⭐ ATS Resume Review

## 🎯 ATS Score
Give score out of 100.

## 👤 Professional Summary
2-3 lines.

## ✅ Strengths
- Bullet points

## ⚠ Weaknesses
- Bullet points

## ❌ Missing Skills
Mention important missing technical skills.

## 💡 Resume Improvement Suggestions
- Bullet points

## 👨‍💼 Recruiter Feedback
Explain whether this candidate is interview ready.

## 🚀 Final Recommendation
Choose one:

⭐ Excellent
⭐⭐ Good
⭐⭐⭐ Average
⭐⭐⭐⭐ Needs Improvement

Do not mention you are an AI.
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text.strip()

    except Exception as e:

        return (
            "⚠ Gemini Resume Review Failed.\n\n"
            f"{e}"
        )