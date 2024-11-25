from io import BytesIO
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, Query

from doc_parser.schema import ConversionResult
from doc_parser.service import DocumentConverterService, DoclingDocumentConversion
from doc_parser.utils import is_file_format_supported

router = APIRouter()

# Could be docling or another converter as long as it implements DocumentConversionBase
converter = DoclingDocumentConversion()
doc_parser_service = DocumentConverterService(doc_parser=converter)


# Document direct conversion endpoints
@router.post(
    '/documents/convert',
    response_model=ConversionResult,
    response_model_exclude_unset=True,
    description="Convert a single document synchronously",
)
async def convert_single_document(
    document: UploadFile = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(1, ge=1, le=4),
    max_tokens: int = Query(256, ge=1, le=8196),
    temperature: float = Query(1, ge=0, le=1),
    top_p: float = Query(0.95, ge=0.5, le=1),
):
    file_bytes = await document.read()
    if not is_file_format_supported(file_bytes, document.filename):
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")

    return doc_parser_service.convert_document(
        (document.filename, BytesIO(file_bytes)),
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )


@router.post(
    '/documents/batch-convert',
    response_model=List[ConversionResult],
    response_model_exclude_unset=True,
    description="Convert multiple documents synchronously",
)
async def convert_multiple_documents(
    documents: List[UploadFile] = File(...),
    extract_tables_as_images: bool = False,
    image_resolution_scale: int = Query(1, ge=1, le=4),
    max_tokens: int = Query(256, ge=1, le=8196),
    temperature: float = Query(1.0, ge=0, le=1),
    top_p: float = Query(0.95, ge=0.5, le=1),
):
    doc_streams = []
    for document in documents:
        file_bytes = await document.read()
        if not is_file_format_supported(file_bytes, document.filename):
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {document.filename}")
        doc_streams.append((document.filename, BytesIO(file_bytes)))

    return doc_parser_service.convert_documents(
        doc_streams,
        extract_tables=extract_tables_as_images,
        image_resolution_scale=image_resolution_scale,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
