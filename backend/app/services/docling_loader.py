"""
Unified document loader using Docling.

Replaces the earlier two-library split (PyMuPDF for native PDFs,
LlamaParse for scanned ones). Docling auto-detects per page whether OCR
is needed and extracts tables as structured content instead of flattened
text, so a single code path handles native PDFs, scanned PDFs, and
markdown/docx.
"""
from dataclasses import dataclass

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Lightweight pipeline: disable OCR and table-structure models to save
# hundreds of MB of RAM on memory-constrained hosts (Render free tier).
# Turn these back on only if you need scanned-PDF OCR or structured tables.
_pipeline_options = PdfPipelineOptions()
_pipeline_options.do_ocr = False
_pipeline_options.do_table_structure = False

_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options)
    }
)


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    filename: str
    pages: list[ParsedPage]
    full_markdown: str
    used_ocr: bool = False


def parse_document(file_path: str, filename: str) -> ParsedDocument:
    """
    Parses a PDF/DOCX/MD file into per-page text plus a full markdown
    export (markdown preserves table structure, which downstream
    chunking relies on).
    """
    result = _converter.convert(file_path)
    doc = result.document

    pages: list[ParsedPage] = []
    for page in doc.pages:
        page_text = doc.export_to_markdown(page_no=page.page_no)
        pages.append(ParsedPage(page_number=page.page_no, text=page_text))

    full_markdown = doc.export_to_markdown()

    # Best-effort OCR detection: Docling exposes per-page processing info
    # on the conversion result; if that attribute isn't present on this
    # Docling version, default to False rather than guessing.
    used_ocr = bool(getattr(result, "ocr_applied", False))

    return ParsedDocument(
        filename=filename,
        pages=pages if pages else [ParsedPage(page_number=1, text=full_markdown)],
        full_markdown=full_markdown,
        used_ocr=used_ocr,
    )
