from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:
    fitz = None


logger = logging.getLogger(__name__)


@dataclass
class PageText:
    page_num: int
    text: str
    bbox: tuple[float, float, float, float]


@dataclass
class ExtractedTable:
    page_num: int
    data: List[List[str]]
    bbox: tuple[float, float, float, float]


@dataclass
class PDFParseResult:
    text_by_page: List[PageText]
    tables: List[ExtractedTable]
    full_text: str
    page_count: int


def parse_pdf(pdf_path: Path) -> PDFParseResult:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    data = pdf_path.read_bytes()
    if not data.startswith(b"%PDF"):
        error_msg = (
            f"File {pdf_path} does not appear to be a valid PDF (missing PDF header). "
            f"It may have been corrupted during ingestion. Please re-ingest the file."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    if fitz is None:
        logger.warning("pymupdf not available, falling back to basic text extraction")
        return _fallback_parse(pdf_path)

    text_by_page: List[PageText] = []
    tables: List[ExtractedTable] = []
    full_text_parts: List[str] = []

    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            page_text = page.get_text()
            page_bbox = page.rect

            text_by_page.append(
                PageText(
                    page_num=page_num + 1,
                    text=page_text,
                    bbox=(page_bbox.x0, page_bbox.y0, page_bbox.x1, page_bbox.y1),
                )
            )
            full_text_parts.append(page_text)

            try:
                page_tables = page.find_tables()
                for table in page_tables:
                    try:
                        table_data = table.extract()
                        if table_data and len(table_data) > 0:
                            tables.append(
                                ExtractedTable(
                                    page_num=page_num + 1,
                                    data=table_data,
                                    bbox=(table.bbox.x0, table.bbox.y0, table.bbox.x1, table.bbox.y1),
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Failed to extract table data on page {page_num + 1}: {e}")
            except Exception as e:
                logger.warning(f"Table extraction failed on page {page_num + 1}: {e}")

        doc.close()
        full_text = "\n\n".join(full_text_parts)

        return PDFParseResult(
            text_by_page=text_by_page,
            tables=tables,
            full_text=full_text,
            page_count=page_count,
        )
    except Exception as e:
        logger.error(f"PDF parsing failed for {pdf_path}: {e}", exc_info=True)
        return _fallback_parse(pdf_path)


def _fallback_parse(pdf_path: Path) -> PDFParseResult:
    try:
        if fitz is not None:
            doc = fitz.open(pdf_path)
            full_text = ""
            text_by_page = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                text_by_page.append(
                    PageText(
                        page_num=page_num + 1,
                        text=page_text,
                        bbox=(0, 0, 0, 0),
                    )
                )
                full_text += page_text + "\n\n"
            doc.close()
            return PDFParseResult(
                text_by_page=text_by_page,
                tables=[],
                full_text=full_text.strip(),
                page_count=len(text_by_page),
            )
    except Exception:
        pass

    return PDFParseResult(
        text_by_page=[],
        tables=[],
        full_text="",
        page_count=0,
    )


def save_parsed_data(vendor_dir: Path, pdf_path: Path, result: PDFParseResult) -> Dict[str, str]:
    base_name = pdf_path.stem
    parsed_dir = vendor_dir / "parsed"
    parsed_dir.mkdir(exist_ok=True)

    text_file = parsed_dir / f"{base_name}_text.txt"
    text_file.write_text(result.full_text, encoding="utf-8")

    pages_file = parsed_dir / f"{base_name}_pages.json"
    pages_data = [
        {
            "page_num": p.page_num,
            "text": p.text,
            "bbox": p.bbox,
        }
        for p in result.text_by_page
    ]
    pages_file.write_text(json.dumps(pages_data, indent=2), encoding="utf-8")

    tables_file = parsed_dir / f"{base_name}_tables.json"
    tables_data = [
        {
            "page_num": t.page_num,
            "data": t.data,
            "bbox": t.bbox,
        }
        for t in result.tables
    ]
    tables_file.write_text(json.dumps(tables_data, indent=2), encoding="utf-8")

    return {
        "text": str(text_file),
        "pages": str(pages_file),
        "tables": str(tables_file),
    }


def load_parsed_text(parsed_text_path: Path) -> str:
    if not parsed_text_path.exists():
        return ""
    return parsed_text_path.read_text(encoding="utf-8")


def load_parsed_tables(parsed_tables_path: Path) -> List[ExtractedTable]:
    if not parsed_tables_path.exists():
        return []
    try:
        data = json.loads(parsed_tables_path.read_text(encoding="utf-8"))
        return [
            ExtractedTable(
                page_num=item["page_num"],
                data=item["data"],
                bbox=tuple(item["bbox"]),
            )
            for item in data
        ]
    except Exception as e:
        logger.warning(f"Failed to load parsed tables: {e}")
        return []
