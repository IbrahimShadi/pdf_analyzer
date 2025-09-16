
from typing import Optional, Tuple
import os
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError

def load_pdf_text(path: str, ocr: bool = False, lang: str = "eng") -> Tuple[str, Optional[str]]:
    """
    Return (text, error). If text is empty and ocr=True, try OCR.
    """
    err = None
    text = ""
    try:
        text = extract_text(path) or ""
    except PDFSyntaxError as e:
        err = f"PDFSyntaxError: {e}"
    except Exception as e:
        err = f"pdfminer_error: {e}"

    if (not text.strip()) and ocr:
        try:
            # OCR path: render with pdf2image and pass to pytesseract
            from pdf2image import convert_from_path
            import pytesseract
            pages = convert_from_path(path)
            ocr_text_parts = []
            for img in pages:
                ocr_text_parts.append(pytesseract.image_to_string(img, lang=lang))
            text = "\n".join(ocr_text_parts)
        except Exception as e:
            if err:
                err = err + f" | ocr_error: {e}"
            else:
                err = f"ocr_error: {e}"
    return text, err
