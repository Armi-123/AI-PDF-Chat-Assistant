import os
import re

from pypdf import PdfReader

from pdf.pdf_ocr import extract_text_ocr


# =====================================================
# PDF TEXT CACHE
# =====================================================

pdf_cache = {}

# Separate cache for hyperlinks
pdf_links_cache = {}


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
    - pathlib.Path
    """

    if pdf_file is None:
        return None

    # -------------------------------------------------
    # String path
    # -------------------------------------------------

    if isinstance(pdf_file, str):
        return pdf_file

    # -------------------------------------------------
    # Path-like object
    # -------------------------------------------------

    if isinstance(pdf_file, os.PathLike):
        return os.fspath(pdf_file)

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

    # Normalize excessive spaces
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
# NORMALIZE URL
# =====================================================

def normalize_url(url):
    """
    Clean and normalize extracted PDF URLs.
    """

    if not url:
        return ""

    url = str(url).strip()

    # Remove surrounding brackets
    url = url.strip(
        " <>[](){}\"'"
    )

    # Remove trailing punctuation
    url = url.rstrip(
        ".,;:!?)]}>"
    )

    return url


# =====================================================
# EXTRACT PDF HYPERLINKS
# =====================================================

def extract_pdf_links(pdf_file):
    """
    Extract hidden hyperlink URLs from PDF annotations.

    This is important for resumes where the visible text
    may only say:

        LinkedIn
        GitHub

    while the actual URL is stored internally in the PDF.

    Returns:

    {
        "linkedin": [...],
        "github": [...],
        "urls": [...]
    }
    """

    pdf_path = get_pdf_path(
        pdf_file
    )

    if not pdf_path:
        return {
            "linkedin": [],
            "github": [],
            "urls": []
        }

    if not os.path.exists(pdf_path):
        return {
            "linkedin": [],
            "github": [],
            "urls": []
        }

    cache_key = _get_cache_key(
        pdf_path
    )

    if cache_key in pdf_links_cache:

        return pdf_links_cache[
            cache_key
        ]

    links = []

    try:

        reader = PdfReader(
            pdf_path
        )

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                annotations = page.get(
                    "/Annots"
                )

                if not annotations:
                    continue

                for annotation_ref in annotations:

                    try:

                        annotation = (
                            annotation_ref.get_object()
                        )

                        subtype = annotation.get(
                            "/Subtype"
                        )

                        if str(subtype) != "/Link":
                            continue

                        action = annotation.get(
                            "/A"
                        )

                        if not action:
                            continue

                        uri = action.get(
                            "/URI"
                        )

                        if not uri:
                            continue

                        url = normalize_url(
                            uri
                        )

                        if not url:
                            continue

                        links.append(
                            {
                                "url": url,
                                "page": page_number
                            }
                        )

                    except Exception as annotation_error:

                        print(
                            "PDF Link Annotation Error:",
                            annotation_error
                        )

            except Exception as page_error:

                print(
                    f"PDF Link Extraction Error "
                    f"Page {page_number}:",
                    page_error
                )

    except Exception as e:

        print(
            "PDF Hyperlink Extraction Error:",
            e
        )

    # -------------------------------------------------
    # Remove duplicate URLs
    # -------------------------------------------------

    unique_urls = []

    seen = set()

    for item in links:

        url = item["url"]

        if url.lower() not in seen:

            seen.add(
                url.lower()
            )

            unique_urls.append(
                item
            )

    # -------------------------------------------------
    # Classify links
    # -------------------------------------------------

    linkedin_links = []

    github_links = []

    for item in unique_urls:

        url = item["url"]

        lower_url = url.lower()

        if "linkedin.com" in lower_url:

            linkedin_links.append(
                url
            )

        elif "github.com" in lower_url:

            github_links.append(
                url
            )

    result = {
        "linkedin": linkedin_links,
        "github": github_links,
        "urls": [
            item["url"]
            for item in unique_urls
        ]
    }

    pdf_links_cache[
        cache_key
    ] = result

    print(
        "PDF HYPERLINKS FOUND:",
        result
    )

    return result


# =====================================================
# GET LINKEDIN URL
# =====================================================

def get_linkedin_url(pdf_file):
    """
    Return the first LinkedIn URL found in PDF.
    """

    links = extract_pdf_links(
        pdf_file
    )

    if links["linkedin"]:

        return links[
            "linkedin"
        ][0]

    return ""


# =====================================================
# GET GITHUB URL
# =====================================================

def get_github_url(pdf_file):
    """
    Return the first GitHub URL found in PDF.
    """

    links = extract_pdf_links(
        pdf_file
    )

    if links["github"]:

        return links[
            "github"
        ][0]

    return ""


# =====================================================
# GET ALL URLS
# =====================================================

def get_pdf_urls(pdf_file):
    """
    Return all URLs found in the PDF.
    """

    links = extract_pdf_links(
        pdf_file
    )

    return links.get(
        "urls",
        []
    )


# =====================================================
# GET PDF TITLE
# =====================================================

def get_pdf_title(pdf_text):
    """
    Extract a meaningful title from PDF text.

    For resumes, attempts to identify the
    candidate's name.
    """

    if not pdf_text:
        return "Unknown PDF"

    pdf_text = clean_pdf_text(
        pdf_text
    )

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

        # Email
        if "@" in line:
            continue

        # URLs
        if re.search(
            r"(linkedin|github|http://|https://)",
            lower_line
        ):
            continue

        # Phone-only
        if re.fullmatch(
            r"[\d\s\+\-\(\)]+",
            line
        ):
            continue

        # Filename
        if lower_line.endswith(".pdf"):
            continue

        name_match = re.fullmatch(
            r"[A-Za-z]+(?:[\s]+[A-Za-z]+){1,4}",
            line
        )

        if name_match:

            words = line.split()

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
    Extract text from PDF.

    Supports:
    - String path
    - Gradio file object
    - Dictionary file object
    - pathlib.Path

    Uses OCR only when normal extraction
    produces little or no useful text.
    """

    pdf_path = get_pdf_path(
        pdf_file
    )

    if not pdf_path:

        print(
            "PDF ERROR: Invalid PDF file input."
        )

        return ""

    if not os.path.exists(
        pdf_path
    ):

        print(
            "PDF ERROR: File does not exist:",
            pdf_path
        )

        return ""

    cache_key = _get_cache_key(
        pdf_path
    )

    # =================================================
    # CACHE
    # =================================================

    if cache_key in pdf_cache:

        cached_text = pdf_cache[
            cache_key
        ]

        print(
            "Using cached PDF text."
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

    try:

        print(
            "FILE SIZE:",
            os.path.getsize(
                pdf_path
            ),
            "bytes"
        )

    except Exception:
        pass

    print("=" * 60)

    # =================================================
    # NORMAL EXTRACTION
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

    extracted_text = "\n\n".join(
        extracted_pages
    )

    extracted_text = clean_pdf_text(
        extracted_text
    )

    # =================================================
    # OCR FALLBACK
    # =================================================

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
    # CACHE
    # =================================================

    pdf_cache[
        cache_key
    ] = extracted_text

    print("=" * 60)

    print(
        "FINAL PDF TEXT LENGTH:",
        len(extracted_text)
    )

    print(
        "PDF TEXT EXTRACTION SUCCESSFUL"
        if extracted_text
        else "PDF TEXT EXTRACTION FAILED"
    )

    print("=" * 60)

    return extracted_text


# =====================================================
# CLEAR PDF CACHE
# =====================================================

def clear_pdf_cache():
    """
    Clear PDF text and hyperlink caches.
    """

    global pdf_cache
    global pdf_links_cache

    pdf_cache.clear()

    pdf_links_cache.clear()

    print(
        "PDF text and hyperlink caches cleared."
    )