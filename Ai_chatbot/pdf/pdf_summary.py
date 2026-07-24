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

# Maximum characters sent to Gemini per PDF
MAX_PDF_CHARS = 30000

# Maximum fallback text length per PDF
MAX_FALLBACK_CHARS = 6000


# =====================================================
# CLEAN TEXT
# =====================================================

def clean_summary_text(text):
    """
    Clean extracted PDF text before summarization.
    Preserves useful line structure.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\t", " ")

    # Remove excessive spaces
    text = re.sub(
        r"[ ]{2,}",
        " ",
        text
    )

    # Remove excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# =====================================================
# GET PDF FILE NAME
# =====================================================

def get_pdf_filename(pdf_file):
    """
    Safely get the original PDF filename.
    """

    pdf_path = get_pdf_path(pdf_file)

    if pdf_path:

        return os.path.basename(
            pdf_path
        )

    return "Uploaded PDF"


# =====================================================
# BUILD LOCAL FALLBACK SUMMARY
# =====================================================

def build_fallback_summary(
    pdf_name,
    pdf_text
):
    """
    Create a useful local summary when Gemini
    is unavailable or quota is exceeded.

    This is NOT an AI-generated summary.
    It extracts important sections and content
    directly from the uploaded PDF.
    """

    if not pdf_text:

        return (
            f"# {pdf_name}\n\n"
            "⚠ No readable text was found in this PDF."
        )


    text = clean_summary_text(
        pdf_text
    )


    # -------------------------------------------------
    # IMPORTANT SECTIONS
    # -------------------------------------------------

    section_names = [
        "summary",
        "profile",
        "objective",
        "education",
        "skills",
        "technical skills",
        "experience",
        "work experience",
        "projects",
        "certifications",
        "certificates",
        "achievements",
    ]


    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


    sections = {}

    current_section = None


    # -------------------------------------------------
    # FIND SECTIONS
    # -------------------------------------------------

    for line in lines:

        normalized = re.sub(
            r"[^a-zA-Z ]",
            "",
            line
        ).strip().lower()


        matched_section = None


        for section in section_names:

            if normalized == section:

                matched_section = section

                break


        if matched_section:

            current_section = matched_section

            if current_section not in sections:

                sections[
                    current_section
                ] = []

            continue


        if current_section:

            # Stop if another obvious heading appears
            if (
                len(line) < 50
                and normalized in section_names
            ):

                current_section = normalized

                if current_section not in sections:

                    sections[
                        current_section
                    ] = []

                continue


            sections[
                current_section
            ].append(line)


    # -------------------------------------------------
    # SECTION DISPLAY
    # -------------------------------------------------

    output = []

    output.append(
        f"# {pdf_name}"
    )

    output.append("")

    output.append(
        "⚠ Gemini summary unavailable. "
        "Showing an extracted PDF content summary instead."
    )

    output.append("")


    # -------------------------------------------------
    # SUMMARY / PROFILE
    # -------------------------------------------------

    summary_content = (
        sections.get("summary", [])
        or sections.get("profile", [])
        or sections.get("objective", [])
    )


    if summary_content:

        output.append(
            "## Main Topics"
        )

        for item in summary_content[:8]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # EDUCATION
    # -------------------------------------------------

    education = sections.get(
        "education",
        []
    )


    if education:

        output.append(
            "## Education"
        )

        for item in education[:10]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # SKILLS
    # -------------------------------------------------

    skills = (
        sections.get("skills", [])
        or sections.get("technical skills", [])
    )


    if skills:

        output.append(
            "## Skills / Technologies"
        )

        for item in skills[:15]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # EXPERIENCE
    # -------------------------------------------------

    experience = (
        sections.get("experience", [])
        or sections.get("work experience", [])
    )


    if experience:

        output.append(
            "## Experience"
        )

        for item in experience[:15]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # PROJECTS
    # -------------------------------------------------

    projects = sections.get(
        "projects",
        []
    )


    if projects:

        output.append(
            "## Projects"
        )

        for item in projects[:15]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # CERTIFICATIONS
    # -------------------------------------------------

    certifications = (
        sections.get("certifications", [])
        or sections.get("certificates", [])
    )


    if certifications:

        output.append(
            "## Certifications"
        )

        for item in certifications[:10]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # ACHIEVEMENTS
    # -------------------------------------------------

    achievements = sections.get(
        "achievements",
        []
    )


    if achievements:

        output.append(
            "## Achievements"
        )

        for item in achievements[:10]:

            output.append(
                f"• {item}"
            )

        output.append("")


    # -------------------------------------------------
    # IF NO SECTIONS FOUND
    # -------------------------------------------------

    if len(output) <= 4:

        output.append(
            "## Extracted PDF Content"
        )

        output.append("")


        # Use meaningful lines instead of
        # blindly taking only first lines

        for line in lines:

            if len(
                "\n".join(output)
            ) >= MAX_FALLBACK_CHARS:

                break


            if len(line) > 2:

                output.append(
                    f"• {line}"
                )


    return "\n".join(
        output
    ).strip()


# =====================================================
# GEMINI SUMMARY
# =====================================================

def generate_gemini_summary(
    pdf_name,
    pdf_text
):
    """
    Generate an AI summary for one PDF.
    """

    if not pdf_text:

        return ""


    pdf_text = clean_summary_text(
        pdf_text
    )


    # Limit content sent to Gemini
    pdf_text = pdf_text[
        :MAX_PDF_CHARS
    ]


    prompt = f"""
You are an expert PDF Summarization Assistant.

Your task is to summarize ONLY the uploaded PDF content.

PDF FILE NAME:
{pdf_name}

STRICT RULES:

1. Use ONLY the information provided in the PDF.
2. Do NOT use outside knowledge.
3. Do NOT invent missing information.
4. Do NOT guess.
5. Do NOT copy large paragraphs.
6. Use concise bullet points.
7. Keep the summary clear and professional.
8. If a section is not present, do not invent it.
9. If there are multiple projects, list them separately.
10. If there are multiple internships or jobs, list them separately.
11. Preserve important names, dates, technologies, numbers, and organizations.

Use this structure when the information exists:

# PDF Name

## Main Topics
• ...

## Education
• ...

## Skills / Technologies
• ...

## Experience
• ...

## Projects
• ...

## Certifications
• ...

## Important Conclusions
• ...

PDF CONTENT:

{pdf_text}

Now generate a concise summary.
"""


    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )


        if (
            response
            and response.text
        ):

            return response.text.strip()


        print(
            "Gemini Summary Error: Empty response."
        )

        return ""


    except Exception as e:

        print(
            "=" * 60
        )

        print(
            "GEMINI PDF SUMMARY ERROR"
        )

        print(
            "PDF:",
            pdf_name
        )

        print(
            "Error:",
            e
        )

        print(
            "=" * 60
        )

        return ""


# =====================================================
# MAIN PDF SUMMARY FUNCTION
# =====================================================

def summarize_pdf(
    pdf_files
):
    """
    Summarize one or more uploaded PDFs.

    Flow:

    1. Validate uploaded PDFs.
    2. Extract text.
    3. Try Gemini AI summary.
    4. If Gemini fails, use local PDF extraction fallback.
    5. Summarize each PDF separately.
    """

    if not pdf_files:

        return (
            "Please upload one or more PDFs first."
        )


    # -------------------------------------------------
    # Normalize single PDF input
    # -------------------------------------------------

    if not isinstance(
        pdf_files,
        (list, tuple)
    ):

        pdf_files = [
            pdf_files
        ]


    summaries = []


    # -------------------------------------------------
    # PROCESS EACH PDF
    # -------------------------------------------------

    for pdf in pdf_files:

        try:

            pdf_path = get_pdf_path(
                pdf
            )


            if not pdf_path:

                print(
                    "PDF Summary Error: "
                    "Invalid PDF path."
                )

                continue


            pdf_name = os.path.basename(
                pdf_path
            )


            print(
                "=" * 60
            )

            print(
                "PDF SUMMARY STARTED"
            )

            print(
                "PDF:",
                pdf_name
            )

            print(
                "=" * 60
            )


            # -----------------------------------------
            # EXTRACT TEXT
            # -----------------------------------------

            pdf_text = extract_pdf_text(
                pdf
            )


            pdf_text = clean_summary_text(
                pdf_text
            )


            if not pdf_text:

                summaries.append(
                    f"# {pdf_name}\n\n"
                    "⚠ Unable to extract readable text "
                    "from this PDF."
                )

                continue


            print(
                "PDF TEXT LENGTH:",
                len(pdf_text)
            )


            # -----------------------------------------
            # TRY GEMINI
            # -----------------------------------------

            ai_summary = generate_gemini_summary(
                pdf_name,
                pdf_text
            )


            if ai_summary:

                summaries.append(
                    ai_summary
                )

                print(
                    "Gemini PDF summary generated successfully."
                )


            # -----------------------------------------
            # GEMINI FALLBACK
            # -----------------------------------------

            else:

                fallback = build_fallback_summary(
                    pdf_name,
                    pdf_text
                )


                summaries.append(
                    fallback
                )


                print(
                    "Using local PDF summary fallback."
                )


        except Exception as e:

            print(
                "=" * 60
            )

            print(
                "PDF SUMMARY PROCESSING ERROR"
            )

            print(
                "Error:",
                e
            )

            print(
                "=" * 60
            )


            try:

                pdf_name = get_pdf_filename(
                    pdf
                )


                summaries.append(
                    f"# {pdf_name}\n\n"
                    "⚠ Unable to generate a summary "
                    "for this PDF."
                )


            except Exception:

                summaries.append(
                    "⚠ Unable to generate a summary "
                    "for this PDF."
                )


    # -------------------------------------------------
    # NO RESULTS
    # -------------------------------------------------

    if not summaries:

        return (
            "⚠ Unable to summarize the uploaded PDF(s)."
        )


    # -------------------------------------------------
    # FINAL RESULT
    # -------------------------------------------------

    return "\n\n---\n\n".join(
        summaries
    )