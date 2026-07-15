from config.gemini_config import client
from pdf.pdf_utils import extract_pdf_text
import re

def summarize_pdf(pdf_file):

    pdf_content = extract_pdf_text(pdf_file)

    if not pdf_content:
        return "Please upload a PDF first."

    prompt = f"""
    You are a PDF Summarization Assistant.

    Rules:
    1. Summarize ONLY the uploaded PDF.
    2. Do NOT use outside knowledge.
    3. Use clear bullet points.
    4. Include:
    - Main topics
    - Important definitions
    - Key concepts
    - Tools/Technologies (if any)
    - Important conclusions
    5. Do not skip major sections.
    6. Keep the summary concise and well organized.

    PDF Content:
    {pdf_content[:50000]}
    """

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        print("Summary Error:", e)

        lines = [
            para.strip()
            for para in re.split(r'\n\s*\n', pdf_content)
            if para.strip()
        ]

        summary = "\n".join(
            [f"• {line[:250]}" for line in lines[:15]]
        )

        return summary
    