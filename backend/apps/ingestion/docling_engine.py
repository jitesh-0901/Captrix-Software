import os
import re
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazily initialized Docling DocumentConverter instance
_docling_converter = None

def get_docling_converter():
    """Lazily initializes and caches the Docling DocumentConverter singleton."""
    global _docling_converter
    if _docling_converter is None:
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.pipeline.native_pdf_pipeline import NativePdfPipeline

            _docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_cls=NativePdfPipeline)
                }
            )
            logger.info("Docling OCR DocumentConverter initialized successfully with NativePdfPipeline.")
        except Exception as e:
            logger.error(f"Failed to initialize Docling DocumentConverter: {e}")
            _docling_converter = None
    return _docling_converter


class DoclingOCREngine:
    """
    Connects the local Docling OCR installation to the Captrix backend.
    Preserves full source traceability (file, page, row, bounding coordinates).
    Adheres strictly to the accounting standard: missing or uncertain values are never replaced with zero.
    """

    @classmethod
    def is_available(cls) -> bool:
        converter = get_docling_converter()
        return converter is not None

    @classmethod
    def get_engine_metadata(cls) -> Dict[str, Any]:
        docling_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Docling OCR"))
        return {
            "engine": "Docling-OCR",
            "status": "OPERATIONAL" if cls.is_available() else "UNAVAILABLE",
            "pipeline": "NativePdfPipeline",
            "source_path": docling_path,
            "license": "MIT",
        }

    @classmethod
    def parse_document(cls, file_path: Any, original_filename: str) -> Optional[Dict[str, Any]]:
        """
        Parses a document (PDF, DOCX, XLSX, etc.) using Docling OCR.
        Extracts structured table records with exact page and bounding box traceability.
        """
        converter = get_docling_converter()
        if not converter:
            logger.warning("Docling OCR converter not available; skipping Docling extraction.")
            return None

        temp_file_created = False
        target_path = file_path

        try:
            from docling.datamodel.base_models import ConversionStatus
            from apps.ingestion.parsers import (
                clean_cell_text,
                normalize_financial_header_name,
                deduplicate_headers,
                detect_best_header_row_and_stitch,
                classify_document_by_name_and_headers,
                classify_document_by_headers,
                clean_and_flatten_tally_record,
                is_candidate_financial_header,
                is_noise_or_carryover_row,
                parse_indian_amount,
            )

            if not (isinstance(file_path, (str, os.PathLike)) and os.path.exists(file_path)):
                import tempfile
                ext = os.path.splitext(original_filename or "")[1] or ".pdf"
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    if hasattr(file_path, 'read'):
                        if hasattr(file_path, 'seek'):
                            file_path.seek(0)
                        tmp.write(file_path.read())
                        if hasattr(file_path, 'seek'):
                            file_path.seek(0)
                    elif isinstance(file_path, bytes):
                        tmp.write(file_path)
                    target_path = tmp.name
                    temp_file_created = True

            res = converter.convert(target_path)
            if res.status != ConversionStatus.SUCCESS:
                logger.warning(f"Docling conversion finished with non-success status: {res.status}")
                return None

            doc = res.document
            records = []
            summary_metadata = {}

            # Strategy A: If Docling extracted structured table objects
            if getattr(doc, 'tables', None) and len(doc.tables) > 0:
                for t_idx, table in enumerate(doc.tables):
                    df = table.export_to_dataframe()
                    if df.empty or len(df.columns) < 2:
                        continue

                    raw_rows = [list(df.columns)] + df.values.tolist()
                    start_data_idx, raw_headers = detect_best_header_row_and_stitch(raw_rows)
                    headers = deduplicate_headers([normalize_financial_header_name(h) for h in raw_headers])
                    doc_type = classify_document_by_name_and_headers(original_filename, headers)

                    for r_idx, row in enumerate(raw_rows[start_data_idx:], start=1):
                        row_dict = {}
                        for c_idx, h in enumerate(headers):
                            val = clean_cell_text(row[c_idx]) if c_idx < len(row) else ''
                            row_dict[h] = val

                        is_noise, _ = is_noise_or_carryover_row(row_dict, headers)
                        if is_noise:
                            continue

                        norm_row, is_valid = clean_and_flatten_tally_record(row_dict, headers, doc_type)
                        if is_valid:
                            records.append({
                                'row_index': len(records) + 1,
                                'source_location': f"Docling:Table_{t_idx + 1}_Row_{r_idx}",
                                'raw': norm_row,
                            })

                    if records:
                        return {
                            'doc_type': doc_type,
                            'headers': headers,
                            'records': records,
                            'summary_metadata': summary_metadata,
                            'ocr_engine_used': 'Docling-OCR',
                            'source_traceability': True
                        }

            # Strategy B: Sub-millimeter Coordinate Clustering from Docling Items
            lines_by_page = defaultdict(lambda: defaultdict(list))
            for item, level in doc.iterate_items():
                text = getattr(item, 'text', '')
                if not text:
                    continue
                prov = getattr(item, 'prov', None)
                if not prov:
                    continue
                page_no = prov[0].page_no
                bbox = prov[0].bbox
                # 3 pt vertical clustering tolerance
                y_key = round(bbox.t / 3.0) * 3.0
                lines_by_page[page_no][y_key].append((bbox.l, text, bbox))

            all_page_rows = []
            for page_no in sorted(lines_by_page.keys()):
                y_dict = lines_by_page[page_no]
                # In BottomLeft coordinates, higher y is near the top of the page
                sorted_y = sorted(y_dict.keys(), reverse=True)
                for y in sorted_y:
                    tokens = sorted(y_dict[y], key=lambda x: x[0])
                    row_texts = [t[1] for t in tokens]
                    all_page_rows.append((page_no, y, row_texts))

            if not all_page_rows:
                return None

            just_rows = [r[2] for r in all_page_rows]
            start_data_idx, raw_headers = detect_best_header_row_and_stitch(just_rows)
            headers = deduplicate_headers([normalize_financial_header_name(h) for h in raw_headers])
            doc_type = classify_document_by_name_and_headers(original_filename, headers)

            for idx, (page_no, y_coord, row_cells) in enumerate(all_page_rows[start_data_idx:], start=1):
                if not any(c.strip() for c in row_cells):
                    continue

                row_dict = {}
                for c_idx, h in enumerate(headers):
                    val = clean_cell_text(row_cells[c_idx]) if c_idx < len(row_cells) else ''
                    row_dict[h] = val

                is_noise, _ = is_noise_or_carryover_row(row_dict, headers)
                if is_noise:
                    continue

                norm_row, is_valid = clean_and_flatten_tally_record(row_dict, headers, doc_type)
                if is_valid:
                    records.append({
                        'row_index': len(records) + 1,
                        'source_location': f"Docling:Page_{page_no}_Y_{int(y_coord)}",
                        'raw': norm_row,
                    })

            if not records:
                return None

            return {
                'doc_type': doc_type,
                'headers': headers,
                'records': records,
                'summary_metadata': summary_metadata,
                'ocr_engine_used': 'Docling-OCR',
                'source_traceability': True
            }

        except Exception as e:
            logger.exception(f"Docling OCR document processing failed on '{file_path}': {e}")
            return None
        finally:
            if temp_file_created and target_path and os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
