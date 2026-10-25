import os
import re
import logging
from decimal import Decimal
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

_ocr_instance = None

def get_ocr_engine():
    """Lazily initializes and returns the singleton RapidOCR engine."""
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_instance = RapidOCR()
            logger.info("RapidOCR original offline OCR engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR engine: {e}")
            _ocr_instance = None
    return _ocr_instance


class OriginalOCREngine:
    """
    100% Offline, Deterministic, Original Optical Character Recognition (OCR) Engine.
    Uses RapidOCR (ONNX Runtime + OpenCV) to process:
    1. Scanned audit vouchers, cheques, invoices, and payment receipts (PNG, JPG, TIFF).
    2. Scanned / image-only bank statements and passbook PDFs.
    Zero external cloud AI dependencies. Full client confidentiality.
    """

    @staticmethod
    def process_image(img_input) -> list[dict]:
        """
        Runs OCR on an image file path or PIL Image object.
        Returns a list of detected items: [{'box': [[x1,y1],...], 'text': str, 'confidence': float, 'center_y': float, 'center_x': float}]
        """
        engine = get_ocr_engine()
        if not engine:
            return []

        try:
            if isinstance(img_input, str):
                results, _ = engine(img_input)
            elif isinstance(img_input, Image.Image):
                img_np = np.array(img_input.convert('RGB'))
                results, _ = engine(img_np)
            else:
                results, _ = engine(img_input)

            if not results:
                return []

            parsed_items = []
            for item in results:
                box, text, score = item[0], item[1], float(item[2])
                # Calculate center coordinates for coordinate clustering
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                center_x = sum(xs) / len(xs)
                center_y = sum(ys) / len(ys)
                min_x = min(xs)
                max_x = max(xs)

                parsed_items.append({
                    'box': box,
                    'text': str(text).strip(),
                    'confidence': score,
                    'center_x': center_x,
                    'center_y': center_y,
                    'min_x': min_x,
                    'max_x': max_x,
                })

            return parsed_items
        except Exception as e:
            logger.exception(f"Error during OCR extraction: {e}")
            return []

    @staticmethod
    def structure_ocr_lines(ocr_items: list[dict], y_tolerance: float = 12.0) -> list[dict]:
        """
        Clusters OCR text tokens into horizontal lines based on Y-coordinates,
        then sorts tokens left-to-right within each line.
        """
        if not ocr_items:
            return []

        # Sort all tokens by top-to-bottom Y center
        sorted_by_y = sorted(ocr_items, key=lambda it: it['center_y'])

        lines = []
        curr_line = [sorted_by_y[0]]
        curr_y = sorted_by_y[0]['center_y']

        for it in sorted_by_y[1:]:
            if abs(it['center_y'] - curr_y) <= y_tolerance:
                curr_line.append(it)
                # Update running average Y
                curr_y = sum(x['center_y'] for x in curr_line) / len(curr_line)
            else:
                lines.append(curr_line)
                curr_line = [it]
                curr_y = it['center_y']

        if curr_line:
            lines.append(curr_line)

        # Sort each line left-to-right by min_x
        structured_lines = []
        for line in lines:
            line_sorted = sorted(line, key=lambda it: it['min_x'])
            full_text = " ".join(t['text'] for t in line_sorted)
            structured_lines.append({
                'tokens': line_sorted,
                'text': full_text,
                'avg_y': sum(t['center_y'] for t in line_sorted) / len(line_sorted),
                'min_x': line_sorted[0]['min_x'],
                'max_x': line_sorted[-1]['max_x']
            })

        return structured_lines

    @staticmethod
    def extract_financial_rows_from_lines(structured_lines: list[dict]) -> tuple[list[str], list[dict], str]:
        """Extracts financial tabular rows from structured OCR lines."""
        from .parsers import parse_indian_amount, parse_flexible_date, classify_document_by_headers

        headers = ['Date', 'Particulars', 'Chq/Ref No', 'Debit', 'Credit', 'Balance']
        records = []
        row_counter = 1

        # Look for candidate header row
        header_line_idx = -1
        for idx, line in enumerate(structured_lines[:15]):
            line_text = line['text'].lower()
            if any(k in line_text for k in ['date', 'txn date', 'particulars', 'narration', 'description']) and any(k in line_text for k in ['amount', 'debit', 'credit', 'withdrawal', 'deposit', 'balance', 'dr', 'cr']):
                header_line_idx = idx
                break

        # Process data lines
        data_lines = structured_lines[header_line_idx + 1:] if header_line_idx >= 0 else structured_lines

        DATE_REGEX = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b')
        AMOUNT_REGEX = re.compile(r'₹?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?|\d+\.\d{2})')

        for s_line in data_lines:
            txt = s_line['text'].strip()
            if not txt or len(txt) < 3:
                continue

            tokens = s_line['tokens']
            # Find date token
            date_match = DATE_REGEX.search(txt)
            date_val = date_match.group(0) if date_match else ''

            # Find amount tokens
            found_amounts = []
            for t in tokens:
                amt = parse_indian_amount(t['text'])
                if amt is not None and amt != Decimal('0.00'):
                    found_amounts.append((t, amt))

            if not date_val and not found_amounts:
                # Continuation narration of previous record
                if records and len(txt) > 2:
                    records[-1]['raw']['Particulars'] = f"{records[-1]['raw']['Particulars']} {txt}".strip()
                continue

            # Build record dictionary
            row_dict = {
                'Date': date_val,
                'Particulars': '',
                'Chq/Ref No': '',
                'Debit': '',
                'Credit': '',
                'Balance': ''
            }

            # Partition tokens into text vs amounts
            text_tokens = []
            for t in tokens:
                if date_val and t['text'] in date_val:
                    continue
                amt = parse_indian_amount(t['text'])
                if amt is not None and amt != Decimal('0.00'):
                    continue
                # Check for cheque/ref tokens
                if re.match(r'^(chq|ref|utr|neft|rtgs|imps|vch|pv|rv)[-:]?\s*[a-z0-9]+', t['text'], re.IGNORECASE):
                    row_dict['Chq/Ref No'] = t['text']
                else:
                    text_tokens.append(t['text'])

            row_dict['Particulars'] = " ".join(text_tokens).strip()

            if len(found_amounts) == 1:
                # Single amount: check if line indicates Dr or Cr, or default to Debit
                amt_val = str(found_amounts[0][1])
                if any(cr in txt.lower() for cr in ['deposit', 'cr', 'credit', 'by ']):
                    row_dict['Credit'] = amt_val
                else:
                    row_dict['Debit'] = amt_val
            elif len(found_amounts) == 2:
                row_dict['Debit'] = str(found_amounts[0][1])
                row_dict['Balance'] = str(found_amounts[1][1])
            elif len(found_amounts) >= 3:
                row_dict['Debit'] = str(found_amounts[0][1])
                row_dict['Credit'] = str(found_amounts[1][1])
                row_dict['Balance'] = str(found_amounts[2][1])

            records.append({
                'row_index': row_counter,
                'source_location': f"OCR:Line_{row_counter}",
                'raw': row_dict
            })
            row_counter += 1

        doc_type = 'BANK_STATEMENT'
        return headers, records, doc_type

    @staticmethod
    def parse_scanned_pdf(file_path: str, max_pages: int = 25) -> dict:
        """
        Renders pages of a scanned / image-only PDF into high-res images and executes RapidOCR.
        """
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(file_path)
        total_pages = min(len(pdf), max_pages)

        all_records = []
        final_headers = ['Date', 'Particulars', 'Chq/Ref No', 'Debit', 'Credit', 'Balance']
        doc_type = 'BANK_STATEMENT'

        for p_idx in range(total_pages):
            page = pdf[p_idx]
            # Render page at 200 DPI (scale ~2.77) for high-precision OCR
            pil_image = page.render(scale=2.77).to_pil()
            ocr_items = OriginalOCREngine.process_image(pil_image)
            structured_lines = OriginalOCREngine.structure_ocr_lines(ocr_items)
            headers, records, detected_type = OriginalOCREngine.extract_financial_rows_from_lines(structured_lines)

            if detected_type != 'UNKNOWN':
                doc_type = detected_type

            for r in records:
                r['source_location'] = f"Page_{p_idx + 1}:{r['source_location']}"
                r['row_index'] = len(all_records) + 1
                all_records.append(r)

        return {
            'doc_type': doc_type,
            'headers': final_headers,
            'records': all_records,
            'is_scanned_pdf': True,
            'total_scanned_pages_processed': total_pages,
            'ocr_engine_used': 'RapidOCR-ONNX'
        }
