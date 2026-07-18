import re
from PyPDF2 import PdfReader
from pdf.pdf_ocr import extract_text_ocr

# PDF Cache
pdf_cache = {}


def get_pdf_title(pdf_text):

    lines = pdf_text.split("\n")

    for line in lines:

        line = line.strip()

        if len(line) < 5:
            continue

        if line.isdigit():
            continue

        return line

    return "Unknown PDF"


def extract_pdf_text(pdf_file):

    if pdf_file is None:
        return ""

    if pdf_file in pdf_cache:
        return pdf_cache[pdf_file]

    text = ""

    try:

        reader = PdfReader(pdf_file)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        # Clean text
        text = re.sub(r"\n+", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()

        # ---------------------------------------
        # OCR Fallback
        # ---------------------------------------
        if len(text) < 100:
            print("Using OCR for scanned PDF...")
            text = extract_text_ocr(pdf_file)

        pdf_cache[pdf_file] = text

    except Exception as e:

        print("PDF Error:", e)

        # OCR if normal extraction fails
        try:
            text = extract_text_ocr(pdf_file)
            pdf_cache[pdf_file] = text
        except Exception as ocr_error:
            print("OCR Error:", ocr_error)

    return text