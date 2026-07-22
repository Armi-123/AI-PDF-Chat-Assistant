import os
import re

from pypdf import PdfReader

from pdf.pdf_ocr import extract_text_ocr


# =====================================================
# PDF TEXT CACHE
# =====================================================

pdf_cache = {}


# =====================================================
# GET FILE PATH
# =====================================================

def get_pdf_path(pdf_file):
    """
    Convert different Gradio/Python file inputs
    into a usable PDF file path.
    """

    if pdf_file is None:
        return None

    # -------------------------------------------------
    # Normal string path
    # -------------------------------------------------

    if isinstance(pdf_file, str):
        return pdf_file

    # -------------------------------------------------
    # Gradio file object
    # -------------------------------------------------

    if hasattr(pdf_file, "name"):
        return pdf_file.name

    # -------------------------------------------------
    # Dictionary-style file object
    # -------------------------------------------------

    if isinstance(pdf_file, dict):

        if "path" in pdf_file:
            return pdf_file["path"]

        if "name" in pdf_file:
            return pdf_file["name"]

    return None


# =====================================================
# CLEAN PDF TEXT
# =====================================================

def clean_pdf_text(text):
    """
    Clean extracted PDF text while preserving
    useful line structure.
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # Replace tabs
    text = text.replace(
        "\t",
        " "
    )

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
# GET PDF TITLE
# =====================================================

def get_pdf_title(pdf_text):
    """
    Get a meaningful title/name from extracted PDF text.
    """

    if not pdf_text:
        return "Unknown PDF"

    lines = pdf_text.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Ignore very short lines
        if len(line) < 3:
            continue

        # Ignore page numbers
        if line.isdigit():
            continue

        # Ignore email-only lines
        if re.fullmatch(
            r"[\w\.-]+@[\w\.-]+\.\w+",
            line
        ):
            continue

        # Ignore phone-only lines
        if re.fullmatch(
            r"[\d\s\+\-\(\)]+",
            line
        ):
            continue

        # Ignore PDF filename
        if line.lower().endswith(".pdf"):
            continue

        return line

    return "Unknown PDF"


# =====================================================
# EXTRACT TEXT FROM PDF
# =====================================================

def extract_pdf_text(pdf_file):
    """
    Extract text from a PDF file.

    Supports:
    - Gradio file path
    - String file path
    - Gradio file object
    - Dictionary file object

    Uses OCR if normal PDF text extraction fails.
    """

    # -------------------------------------------------
    # GET REAL FILE PATH
    # -------------------------------------------------

    pdf_path = get_pdf_path(
        pdf_file
    )

    if not pdf_path:

        print(
            "PDF ERROR: Invalid PDF file input."
        )

        return ""


    # -------------------------------------------------
    # CHECK FILE EXISTS
    # -------------------------------------------------

    if not os.path.exists(
        pdf_path
    ):

        print(
            "PDF ERROR: File does not exist:"
        )

        print(
            pdf_path
        )

        return ""


    # -------------------------------------------------
    # CREATE CACHE KEY
    # -------------------------------------------------

    try:

        file_size = os.path.getsize(
            pdf_path
        )

        modified_time = os.path.getmtime(
            pdf_path
        )

        cache_key = (
            pdf_path,
            file_size,
            modified_time
        )

    except Exception:

        cache_key = pdf_path


    # -------------------------------------------------
    # RETURN CACHED TEXT
    # -------------------------------------------------

    if cache_key in pdf_cache:

        cached_text = pdf_cache[
            cache_key
        ]

        print(
            "Using cached PDF text."
        )

        print(
            "Cached Characters:",
            len(cached_text)
        )

        return cached_text


    # -------------------------------------------------
    # DEBUG INFORMATION
    # -------------------------------------------------

    print(
        "=" * 60
    )

    print(
        "PDF EXTRACTION STARTED"
    )

    print(
        "PDF PATH:",
        pdf_path
    )

    print(
        "FILE EXISTS:",
        os.path.exists(pdf_path)
    )

    print(
        "FILE SIZE:",
        os.path.getsize(pdf_path),
        "bytes"
    )

    print(
        "=" * 60
    )


    # -------------------------------------------------
    # NORMAL PDF EXTRACTION
    # -------------------------------------------------

    extracted_text = ""

    try:

        reader = PdfReader(
            pdf_path
        )

        print(
            "PDF PAGES:",
            len(reader.pages)
        )


        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                page_text = page.extract_text()

                if page_text:

                    print(
                        f"Page {page_number}: "
                        f"{len(page_text)} characters"
                    )

                    extracted_text += (
                        page_text
                        + "\n"
                    )

                else:

                    print(
                        f"Page {page_number}: "
                        "No text extracted"
                    )

            except Exception as page_error:

                print(
                    f"Page {page_number} "
                    f"Extraction Error:",
                    page_error
                )


    except Exception as e:

        print(
            "NORMAL PDF EXTRACTION ERROR:",
            e
        )


    # -------------------------------------------------
    # CLEAN EXTRACTED TEXT
    # -------------------------------------------------

    extracted_text = clean_pdf_text(
        extracted_text
    )


    # -------------------------------------------------
    # DEBUG EXTRACTION RESULT
    # -------------------------------------------------

    print(
        "=" * 60
    )

    print(
        "PDF EXTRACTION RESULT"
    )

    print(
        "Characters:",
        len(extracted_text)
    )

    print(
        "Preview:"
    )

    print(
        extracted_text[
            :2000
        ]
    )

    print(
        "=" * 60
    )


    # -------------------------------------------------
    # OCR FALLBACK
    # -------------------------------------------------

    if len(extracted_text) < 100:

        print(
            "Normal extraction returned very little text."
        )

        print(
            "Trying OCR fallback..."
        )


        try:

            ocr_text = extract_text_ocr(
                pdf_path
            )


            ocr_text = clean_pdf_text(
                ocr_text
            )


            print(
                "=" * 60
            )

            print(
                "OCR EXTRACTION RESULT"
            )

            print(
                "Characters:",
                len(ocr_text)
            )

            print(
                "Preview:"
            )

            print(
                ocr_text[
                    :2000
                ]
            )

            print(
                "=" * 60
            )


            if len(ocr_text) > len(
                extracted_text
            ):

                extracted_text = ocr_text


        except Exception as ocr_error:

            print(
                "OCR EXTRACTION ERROR:",
                ocr_error
            )


    # -------------------------------------------------
    # FINAL CLEANING
    # -------------------------------------------------

    extracted_text = clean_pdf_text(
        extracted_text
    )


    # -------------------------------------------------
    # SAVE CACHE
    # -------------------------------------------------

    pdf_cache[
        cache_key
    ] = extracted_text


    # -------------------------------------------------
    # FINAL DEBUG
    # -------------------------------------------------

    print(
        "=" * 60
    )

    print(
        "FINAL PDF TEXT LENGTH:",
        len(extracted_text)
    )

    if extracted_text:

        print(
            "PDF TEXT EXTRACTION SUCCESSFUL"
        )

    else:

        print(
            "PDF TEXT EXTRACTION FAILED"
        )

    print(
        "=" * 60
    )


    return extracted_text


# =====================================================
# CLEAR PDF CACHE
# =====================================================

def clear_pdf_cache():
    """
    Clear all cached PDF text.
    """

    global pdf_cache

    pdf_cache.clear()

    print(
        "PDF cache cleared."
    )