import pytesseract
from pdf2image import convert_from_path


def extract_text_ocr(pdf_file):
    """
    Extract text from scanned PDFs using OCR.
    """

    text = ""

    try:

        images = convert_from_path(
            pdf_file,
            dpi=300
        )

        for image in images:

            page_text = pytesseract.image_to_string(image)

            if page_text:
                text += page_text + "\n"

    except Exception as e:

        print("OCR Error:", e)

    return text