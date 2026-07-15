import re
from PyPDF2 import PdfReader

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

        for page_number, page in enumerate(reader.pages, start=1):

            page_text = page.extract_text()

            if page_text:

                text += (
                    page_text
                    + "\n"
                )

        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()

        pdf_cache[pdf_file] = text

    except Exception as e:
        print("PDF Error:", e)

    return text
