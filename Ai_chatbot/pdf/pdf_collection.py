from pdf.pdf_utils import extract_pdf_text


def load_pdfs(pdf_files):

    pdf_database = []

    if not pdf_files:
        return pdf_database

    for pdf in pdf_files:

        try:

            text = extract_pdf_text(pdf)

            pdf_database.append(
                {
                    "name": pdf.name.split("/")[-1],
                    "path": pdf,
                    "text": text
                }
            )

        except Exception:

            pass

    return pdf_database