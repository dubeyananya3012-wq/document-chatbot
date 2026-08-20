import sys
import os
import traceback

backend_path = r"c:\Users\Administrator\Downloads\document-chatbot\backend"
sys.path.append(backend_path)
os.environ["ENV"] = "development"
os.chdir(backend_path)

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

_pipeline_options = PdfPipelineOptions()
_pipeline_options.do_ocr = False
_pipeline_options.do_table_structure = False

_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options)
    }
)

result = _converter.convert(r"c:\Users\Administrator\Downloads\1.pdf")
doc = result.document

print("Type of doc:", type(doc))
print("Type of doc.pages:", type(doc.pages))
try:
    print("Length of doc.pages:", len(doc.pages))
    first_key = list(doc.pages.keys())[0] if isinstance(doc.pages, dict) else 0
    first_item = doc.pages[first_key]
    print("First page element:", first_item)
    print("Type of first page element:", type(first_item))
    print("Attributes of first page element:", dir(first_item))
except Exception as e:
    traceback.print_exc()
