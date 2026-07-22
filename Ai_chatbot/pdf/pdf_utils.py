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

    Supported:
    - String path
    - Gradio file object
    - Dictionary file object
    """

    if pdf_file is None:
        return None

    # -------------------------------------------------
    # String path
    # -------------------------------------------------

    if isinstance(pdf_file, str):
        return pdf_file

    # -------------------------------------------------
    # Gradio file object
    # -------------------------------------------------

    if hasattr(pdf_file, "name"):

        try:
            return pdf_file.name

        except Exception:
            pass

    # -------------------------------------------------
    # Dictionary-style file object
    # -------------------------------------------------

    if isinstance(pdf_file, dict):

        if pdf_file.get("path"):
            return pdf_file["path"]

        if pdf_file.get("name"):
            return pdf_file["name"]

    return None


# =====================================================
# CLEAN PDF TEXT
# =====================================================

def clean_pdf_text(text):
    """
    Clean extracted PDF text while preserving
    useful line and paragraph structure.
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Normalize tabs
    text = text.replace("\t", " ")

    # Remove invisible/null characters
    text = text.replace("\x00", "")

    # Normalize spaces inside lines
    text = re.sub(
        r"[ ]{2,}",
        " ",
        text
    )

    # Remove spaces before newlines
    text = re.sub(
        r"[ ]+\n",
        "\n",
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
    Extract a meaningful title from PDF text.

    For resumes, attempts to identify the candidate's
    name from the first meaningful lines.
    """

    if not pdf_text:
        return "Unknown PDF"

    pdf_text = clean_pdf_text(pdf_text)

    if not pdf_text:
        return "Unknown PDF"

    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return "Unknown PDF"

    # =================================================
    # RESUME / CV NAME DETECTION
    # =================================================

    for line in lines[:15]:

        lower_line = line.lower()

        # Skip obvious section headings
        ignored_headings = {
            "resume",
            "cv",
            "curriculum vitae",
            "summary",
            "education",
            "skills",
            "experience",
            "projects",
            "certifications",
            "contact",
        }

        if lower_line in ignored_headings:
            continue

        # Skip lines containing contact information
        if "@" in line:
            continue

        if re.search(
            r"(linkedin|github|http://|https://)",
            lower_line
        ):
            continue

        # Skip phone-only lines
        if re.fullmatch(
            r"[\d\s\+\-\(\)]+",
            line
        ):
            continue

        # Skip PDF filenames
        if lower_line.endswith(".pdf"):
            continue

        # -------------------------------------------------
        # Candidate name pattern
        # -------------------------------------------------

        name_match = re.fullmatch(
            r"[A-Za-z]+(?:[\s]+[A-Za-z]+){1,4}",
            line
        )

        if name_match:

            words = line.split()

            # Avoid treating long sentences as names
            if 2 <= len(words) <= 5:

                return line

    # =================================================
    # FALLBACK
    # =================================================

    for line in lines:

        if len(line) < 3:
            continue

        if line.isdigit():
            continue

        if line.lower().endswith(".pdf"):
            continue

        if "@" in line:
            continue

        return line

    return "Unknown PDF"


# =====================================================
# CREATE CACHE KEY
# =====================================================

def _get_cache_key(pdf_path):

    try:

        file_size = os.path.getsize(
            pdf_path
        )

        modified_time = os.path.getmtime(
            pdf_path
        )

        return (
            pdf_path,
            file_size,
            modified_time
        )

    except Exception:

        return pdf_path


# =====================================================
# EXTRACT TEXT FROM PDF
# =====================================================

def extract_pdf_text(pdf_file):
    """
    Extract text from a PDF.

    Supports:
    - String file path
    - Gradio file object
    - Dictionary file object

    Uses OCR only when normal extraction
    produces little or no useful text.
    """

    # =================================================
    # GET REAL FILE PATH
    # =================================================

    pdf_path = get_pdf_path(
        pdf_file
    )

    if not pdf_path:

        print(
            "PDF ERROR: Invalid PDF file input."
        )

        return ""

    # =================================================
    # CHECK FILE EXISTS
    # =================================================

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

    # =================================================
    # CACHE KEY
    # =================================================

    cache_key = _get_cache_key(
        pdf_path
    )

    # =================================================
    # RETURN CACHE
    # =================================================

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

    # =================================================
    # DEBUG
    # =================================================

    print("=" * 60)

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

    try:

        print(
            "FILE SIZE:",
            os.path.getsize(pdf_path),
            "bytes"
        )

    except Exception:
        pass

    print("=" * 60)

    # =================================================
    # NORMAL PDF EXTRACTION
    # =================================================

    extracted_pages = []

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

                    page_text = clean_pdf_text(
                        page_text
                    )

                    print(
                        f"Page {page_number}: "
                        f"{len(page_text)} characters"
                    )

                    if page_text:

                        extracted_pages.append(
                            page_text
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

    # =================================================
    # COMBINE PAGES
    # =================================================

    extracted_text = "\n\n".join(
        extracted_pages
    )

    extracted_text = clean_pdf_text(
        extracted_text
    )

    # =================================================
    # DEBUG
    # =================================================

    print("=" * 60)

    print(
        "NORMAL PDF EXTRACTION RESULT"
    )

    print(
        "Characters:",
        len(extracted_text)
    )

    print(
        "Preview:"
    )

    print(
        extracted_text[:2000]
    )

    print("=" * 60)

    # =================================================
    # OCR FALLBACK
    # =================================================

    # Only use OCR if extracted text is too short.
    # This avoids unnecessary OCR processing.

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

            print("=" * 60)

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
                ocr_text[:2000]
            )

            print("=" * 60)

            # Use OCR only when it produces
            # more useful content.

            if len(ocr_text) > len(
                extracted_text
            ):

                extracted_text = ocr_text

        except Exception as ocr_error:

            print(
                "OCR EXTRACTION ERROR:",
                ocr_error
            )

    # =================================================
    # FINAL CLEANING
    # =================================================

    extracted_text = clean_pdf_text(
        extracted_text
    )

    # =================================================
    # SAVE CACHE
    # =================================================

    pdf_cache[
        cache_key
    ] = extracted_text

    # =================================================
    # FINAL DEBUG
    # =================================================

    print("=" * 60)

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

    print("=" * 60)

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