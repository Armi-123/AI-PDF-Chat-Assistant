from config.gemini_config import client
from pdf.pdf_utils import extract_pdf_text
import os
import re

MODEL_NAME = "gemini-2.5-flash"


def summarize_pdf(pdf_files):

    if not pdf_files:
        return "Please upload one or more PDFs first."

    pdf_content = ""

    for pdf in pdf_files:

        pdf_content += (
            f"\n\n========== {os.path.basename(pdf)} ==========\n\n"
        )

        pdf_content += extract_pdf_text(pdf)

    prompt = f"""
You are an expert PDF Summarization Assistant.

Rules:

1. Summarize ONLY the uploaded PDF(s).
2. Never use outside knowledge.
3. If multiple PDFs are uploaded, summarize EACH PDF separately.
4. Use this format:

# PDF Name

## Main Topics
• ...

## Key Concepts
• ...

## Important Definitions
• ...

## Tools / Technologies
• ...

## Important Conclusions
• ...

5. Keep each PDF summary within 250–300 words.
6. Do NOT copy large paragraphs.
7. Use concise bullet points.
8. Skip repeated information.

PDF Content:

{pdf_content[:45000]}
"""

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        return response.text

    except Exception as e:

        print("Summary Error:", e)

        paragraphs = [
            p.strip()
            for p in re.split(r"\n\s*\n", pdf_content)
            if p.strip()
        ]

        summary = "\n".join(
            f"• {p[:250]}"
            for p in paragraphs[:20]
        )

        return (
            "⚠ Gemini summary unavailable.\n\n"
            "Quick Summary:\n\n"
            + summary
        )