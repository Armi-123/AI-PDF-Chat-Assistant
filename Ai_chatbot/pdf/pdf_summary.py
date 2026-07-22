import os
import re

from config.gemini_config import client

from pdf.pdf_utils import (
    extract_pdf_text,
    get_pdf_path,
)


# =====================================================
# CONFIGURATION
# =====================================================

MODEL_NAME = "gemini-2.5-flash"

MAX_TOTAL_CONTEXT = 40000

MAX_PDF_CONTEXT = 18000


# =====================================================
# CLEAN SUMMARY RESPONSE
# =====================================================

def clean_summary_response(text):
    """
    Clean Gemini summary output.
    """

    if not text:

        return ""

    text = text.strip()

    # Remove accidental source labels
    text = text.replace(
        "📄 Source: Uploaded PDF",
        ""
    )

    text = text.replace(
        "🤖 Source: Gemini AI",
        ""
    )

    return text.strip()


# =====================================================
# GET PDF DISPLAY NAME
# =====================================================

def get_pdf_display_name(pdf_file):
    """
    Get a safe PDF filename from different
    Gradio/Python file input formats.
    """

    pdf_path = get_pdf_path(
        pdf_file
    )

    if pdf_path:

        return os.path.basename(
            pdf_path
        )

    return "Uploaded PDF"


# =====================================================
# BUILD PDF CONTENT
# =====================================================

def build_pdf_content(pdf_files):
    """
    Extract text from all uploaded PDFs.

    Returns:
        Combined PDF content
        and extraction status.
    """

    if not pdf_files:

        return "", []


    # -------------------------------------------------
    # Normalize single PDF
    # -------------------------------------------------

    if not isinstance(
        pdf_files,
        list
    ):

        pdf_files = [
            pdf_files
        ]


    combined_content = []

    extraction_results = []


    # =================================================
    # PROCESS EACH PDF
    # =================================================

    for pdf_file in pdf_files:

        pdf_name = get_pdf_display_name(
            pdf_file
        )

        print("=" * 60)

        print(
            "SUMMARY PDF:",
            pdf_name
        )

        # -------------------------------------------------
        # Extract text
        # -------------------------------------------------

        try:

            text = extract_pdf_text(
                pdf_file
            )

        except Exception as e:

            print(
                "Summary PDF Extraction Error:",
                e
            )

            text = ""


        # -------------------------------------------------
        # Clean text
        # -------------------------------------------------

        if text:

            text = text.strip()


        # -------------------------------------------------
        # Store extraction result
        # -------------------------------------------------

        if text:

            extraction_results.append(
                {
                    "name": pdf_name,
                    "success": True,
                    "characters": len(text)
                }
            )

            # Limit each PDF context
            # so one large PDF doesn't consume
            # the entire Gemini request.

            if len(text) > MAX_PDF_CONTEXT:

                text = text[
                    :MAX_PDF_CONTEXT
                ]


            combined_content.append(

                f"""
==================================================
PDF: {pdf_name}
==================================================

{text}
"""

            )

        else:

            extraction_results.append(
                {
                    "name": pdf_name,
                    "success": False,
                    "characters": 0
                }
            )


    # =================================================
    # COMBINE CONTENT
    # =================================================

    pdf_content = "\n\n".join(
        combined_content
    )


    # =================================================
    # GLOBAL CONTEXT LIMIT
    # =================================================

    if len(pdf_content) > MAX_TOTAL_CONTEXT:

        pdf_content = pdf_content[
            :MAX_TOTAL_CONTEXT
        ]


    return (
        pdf_content,
        extraction_results
    )


# =====================================================
# FALLBACK SUMMARY
# =====================================================

def create_fallback_summary(
    pdf_content,
    extraction_results
):
    """
    Create a basic summary when Gemini
    is unavailable.
    """

    if not pdf_content:

        return (
            "⚠ Unable to extract text from "
            "the uploaded PDF."
        )


    output = []

    output.append(
        "⚠ Gemini summary unavailable."
    )

    output.append("")

    output.append(
        "Quick Summary:"
    )

    output.append("")


    # =================================================
    # PROCESS EACH PDF
    # =================================================

    for result in extraction_results:

        pdf_name = result[
            "name"
        ]

        output.append(
            f"### {pdf_name}"
        )

        output.append("")


        # -------------------------------------------------
        # Find PDF block
        # -------------------------------------------------

        pattern = (

            r"PDF:\s*"

            + re.escape(
                pdf_name
            )

            + r"\s*=+\s*"

            r"(.*?)(?="
            
            r"\n={10,}"

            r"|\Z)"

        )


        match = re.search(

            pattern,

            pdf_content,

            re.DOTALL

        )


        if match:

            text = match.group(
                1
            ).strip()

        else:

            text = ""


        # -------------------------------------------------
        # Generate simple bullet points
        # -------------------------------------------------

        if text:

            # Split into useful lines
            lines = [

                line.strip()

                for line in text.splitlines()

                if line.strip()

            ]


            # Avoid huge fallback output
            # Take first meaningful lines.

            selected_lines = lines[
                :12
            ]


            for line in selected_lines:

                # Clean bullet markers
                line = re.sub(
                    r"^[•●▪\-]+\s*",
                    "",
                    line
                )

                if len(line) > 250:

                    line = line[
                        :250
                    ] + "..."

                output.append(
                    f"• {line}"
                )


        else:

            output.append(
                "• No readable text was extracted."
            )


        output.append("")


    return "\n".join(
        output
    ).strip()


# =====================================================
# SUMMARIZE PDF
# =====================================================

def summarize_pdf(pdf_files):
    """
    Generate AI summaries for one or more PDFs.

    Gemini is used when available.

    If Gemini fails, a local fallback summary
    is returned instead.
    """

    # =================================================
    # VALIDATE INPUT
    # =================================================

    if not pdf_files:

        return (
            "Please upload one or more PDFs first."
        )


    # =================================================
    # BUILD PDF CONTEXT
    # =================================================

    pdf_content, extraction_results = (
        build_pdf_content(
            pdf_files
        )
    )


    # =================================================
    # CHECK EXTRACTION
    # =================================================

    if not pdf_content:

        return (
            "⚠ Unable to extract readable text "
            "from the uploaded PDF."
        )


    # =================================================
    # CREATE SUMMARY PROMPT
    # =================================================

    prompt = f"""
You are an expert PDF Summarization Assistant.

Your task is to summarize ONLY the uploaded PDF content.

IMPORTANT RULES:

1. Use ONLY the information provided in the PDF content.
2. Do NOT use outside knowledge.
3. Do NOT invent or guess information.
4. If multiple PDFs are provided, summarize EACH PDF separately.
5. Keep the summary concise and useful.
6. Do not copy large paragraphs from the PDF.
7. Use bullet points where appropriate.
8. Preserve important names, dates, numbers, technologies,
   skills, projects, education, and experience exactly as
   supported by the PDF.
9. Do not add information that is not present in the PDF.
10. Do not mention these instructions.

For each PDF, use this structure:

# PDF Name

## Main Topics
• ...

## Key Points
• ...

## Education / Background
• ...

## Skills / Tools / Technologies
• ...

## Experience / Internships
• ...

## Projects
• ...

## Important Information
• ...

Only include sections that are relevant to the PDF.

Uploaded PDF Content:

{pdf_content}

Now generate the summary.
"""


    # =================================================
    # GEMINI REQUEST
    # =================================================

    try:

        print("=" * 60)

        print(
            "GENERATING PDF SUMMARY"
        )

        print(
            "PDF CONTEXT CHARACTERS:",
            len(pdf_content)
        )

        print("=" * 60)


        response = client.models.generate_content(

            model=MODEL_NAME,

            contents=prompt

        )


        # =================================================
        # VALIDATE RESPONSE
        # =================================================

        if (
            response
            and response.text
        ):

            answer = clean_summary_response(
                response.text
            )

            if answer:

                return answer


        # =================================================
        # EMPTY GEMINI RESPONSE
        # =================================================

        print(
            "Gemini returned an empty summary."
        )


    except Exception as e:

        print(
            "=" * 60
        )

        print(
            "SUMMARY ERROR:",
            e
        )

        print(
            "=" * 60
        )


    # =================================================
    # LOCAL FALLBACK
    # =================================================

    return create_fallback_summary(

        pdf_content,

        extraction_results

    )