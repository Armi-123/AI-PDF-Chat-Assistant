from dotenv import load_dotenv
from google import genai
import os
from config.settings import MODEL_NAME,DEBUG
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
        return "⚠ Please upload a resume first."

    if isinstance(pdf_files, str):
        pdf_files = [pdf_files]

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
            model=MODEL_NAME,
            contents=prompt
        )

        # ---------------------------------------------
        # Empty response
        # ---------------------------------------------
        if response is None:
            return "⚠ Gemini returned no response."

        # ---------------------------------------------
        # Normal response
        # ---------------------------------------------
        if getattr(response, "text", None):

            return response.text.strip()

        # ---------------------------------------------
        # Fallback (new SDK sometimes stores text differently)
        # ---------------------------------------------
        try:

            if (
                response.candidates
                and response.candidates[0].content.parts
            ):

                text = "".join(
                    part.text
                    for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                )

                if text.strip():
                    return text.strip()

        except Exception:
            pass

        return "⚠ Gemini returned an empty response."

    except Exception as e:

        error = str(e).lower()

        if (
            "429" in error
            or "quota" in error
            or "resource_exhausted" in error
        ):
            return (
                "⚠ Gemini API quota exceeded.\n\n"
                "Please wait and try again later "
                "or use another Gemini API key."
            )

        if (
            "503" in error
            or "unavailable" in error
            or "overloaded" in error
        ):
            return (
                "⚠ Gemini server is currently busy.\n\n"
                "Please try again after a few seconds."
            )

        if DEBUG:
            print("Resume Review Error:", e)

        return (
            "⚠ Unable to review the resume right now.\n\n"
            "Please try again."
        )