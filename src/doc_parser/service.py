import re

from io import BytesIO
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Any

from fastapi import HTTPException

from docling.datamodel.base_models import InputFormat, DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from docling_core.types.doc.document import (
    DoclingDocument as DLDocument,
    ListItem,
    TextItem,
    TableItem,
    PictureItem,
    DocItem,
    SectionHeaderItem,
    LevelNumber,
)
from docling_core.types.doc.labels import DocItemLabel
from docling_core.transforms.chunker.hierarchical_chunker import (
    HierarchicalChunker,
    BaseChunk,
    DocChunk,
    DocMeta,
)


from doc_parser.schema import ConversionResult, ParserChunk

from doc_parser.utils import image_to_text
from doc_parser.settings import (
    IMAGE_RESOLUTION_SCALE, 
    MAX_TOKENS,
    TEMPERATURE, 
    TOP_P, 
    logger
)


class DocumentConversionBase(ABC):
    @abstractmethod
    def convert(self, document: Tuple[str, BytesIO], **kwargs) -> ConversionResult:
        pass

    @abstractmethod
    def convert_batch(self, documents: List[Tuple[str, BytesIO]], **kwargs) -> List[ConversionResult]:
        pass


class DoclingDocumentConversion(DocumentConversionBase):
    def _setup_pipeline_options(
        self, 
        extract_tables: bool = False,
        generate_page_images: bool = False,
        generate_picture_images: bool = True,
        orc_langs: Optional[List[str]] = ["fr", "de", "es", "en"],
        image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
    ) -> PdfPipelineOptions:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.images_scale = image_resolution_scale
        pipeline_options.generate_page_images = generate_page_images
        pipeline_options.generate_table_images = extract_tables
        pipeline_options.generate_picture_images = generate_picture_images
        pipeline_options.ocr_options = EasyOcrOptions(lang=orc_langs)

        return pipeline_options

    @staticmethod
    def _process_document_image(dl_doc: DLDocument, item: PictureItem, max_tokens: int = MAX_TOKENS, temperature: float = TEMPERATURE, top_p: float = TOP_P) -> Optional[str]:
        text = None
        if not item.image:
            raise ValueError("AWS Credentials are missed. Please check the infrastructure.")
        
        # use VLM for converting
        base64_image = str(item.image.uri).replace("data:image/png;base64,", "").strip()

        image_text = image_to_text(
            base64_image,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        # remove useless text
        image_text = image_text.replace(
            "Extract all text in the given image in markdown.",
            "",
        ).strip()

        # just add when there is text
        if (
            image_text
            and "no text" not in image_text.lower()
            and "not contain any" not in image_text.lower()
        ):
            text = item.caption_text(dl_doc) + f"```{image_text}```"

        return text

    def convert(
        self,
        document: Tuple[str, BytesIO],
        extract_tables: bool = False, 
        generate_page_images: bool = False,
        generate_picture_images: bool = True,
        orc_langs: Optional[List[str]] = ["fr", "de", "es", "en"],
        image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
        top_p: float = TOP_P,
    ) -> ConversionResult:
        filename, file = document
        pipeline_options = self._setup_pipeline_options(extract_tables, generate_page_images, generate_picture_images, orc_langs, image_resolution_scale)
        doc_converter = DocumentConverter(
            # whitelist formats, non-matching files are ignored.
            # csv/xlsx is converted into list-of-tables html
            # ppt/pptx is converted into pdf
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.MD,
                InputFormat.ASCIIDOC,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=DoclingParseV2DocumentBackend,
                    pipeline_options=pipeline_options,
                ),
            },
        )

        conv_res = doc_converter.convert(DocumentStream(name=filename, stream=file), raises_on_error=False)

        if conv_res.errors:
            logger.error(f"Failed to convert {filename}: {conv_res.errors[0].error_message}")
            return ConversionResult(filename=filename, error=conv_res.errors[0].error_message)

        chunker = DoclingChunker()
        chunks = chunker.hierarchical_chunk(conv_res.document, indent=4, max_tokens=max_tokens, temperature=temperature, top_p=top_p)

        chunk_dicts = self.post_process_chunks(chunker.chunker, chunks, indent=4)
        
        return ConversionResult(filename=filename, chunk_dicts=chunk_dicts)

    def convert_batch(
        self,
        documents: List[Tuple[str, BytesIO]],
        extract_tables: bool = False, 
        generate_page_images: bool = False,
        generate_picture_images: bool = True,
        orc_langs: Optional[List[str]] = ["fr", "de", "es", "en"],
        image_resolution_scale: int = IMAGE_RESOLUTION_SCALE,
        max_tokens: int = MAX_TOKENS,
        temperature: float = TEMPERATURE,
        top_p: float = TOP_P,
    ) -> List[ConversionResult]:
        pipeline_options = self._setup_pipeline_options(extract_tables, generate_page_images, generate_picture_images, orc_langs, image_resolution_scale)
        doc_converter = DocumentConverter(
            # whitelist formats, non-matching files are ignored.
            # csv/xlsx is converted into list-of-tables html
            # ppt/pptx is converted into pdf
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.MD,
                InputFormat.ASCIIDOC,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=DoclingParseV2DocumentBackend,
                    pipeline_options=pipeline_options,
                ),
            },
        )

        conv_results = doc_converter.convert_all(
            [DocumentStream(name=filename, stream=file) for filename, file in documents],
            raises_on_error=False,
        )

        results = []
        for conv_res in conv_results:
            if conv_res.errors:
                logger.error(f"Failed to convert {conv_res.input.name}: {conv_res.errors[0].error_message}")
                results.append(ConversionResult(filename=conv_res.input.name, error=conv_res.errors[0].error_message))
                continue

            chunker = DoclingChunker()
            chunks = chunker.hierarchical_chunk(conv_res.document, indent=4, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
            
            chunk_dicts = self.post_process_chunks(chunker.chunker, chunks, indent=4)

            results.append(ConversionResult(filename=conv_res.input.name, chunk_dicts=chunk_dicts))

        return results
    
    def post_process_chunks(self, chunker: HierarchicalChunker, chunks: List[DocChunk], indent: int = 4, min_length: int = 32) -> List[ParserChunk]:
        chunks_dicts: list[dict] = []
        current_item = {}
        for chunk in chunks:
            if not current_item:
                heading_text = (
                    chunker.delim.join(chunk.meta.headings)
                    if chunk.meta.headings and re.sub(r"^#+ ", "", chunk.meta.headings[0]) not in chunk.text
                    else ""
                )
                current_item = {
                    "text": f"{heading_text}\n\n{chunk.text}".strip(),
                    "metadata": {
                        "page_number": chunk.meta.doc_items[0].prov[0].page_no
                        if chunk.meta.doc_items[0].prov
                        else 1,
                        "chunk_type": chunk.meta.doc_items[0].label.value,
                        "bbox": None,  # current we don't consider bbox
                        "file_type": chunk.meta.origin.mimetype,
                        "filename": chunk.meta.origin.filename,
                        "headings": chunk.meta.headings,
                    },
                }
                continue

            if (
                (  # add footnote to table
                    current_item["metadata"]["chunk_type"] == "table"
                    and chunk.meta.doc_items[0].label.value == "footnote"
                )
                or (  # add notes (list item) with higher level to table
                    current_item["metadata"]["chunk_type"] == "table"
                    and chunk.meta.doc_items[0].label.value == "list_item"
                    and chunk.text.startswith(" " * indent)
                )
                or (  # add caption to table
                    current_item["metadata"]["chunk_type"] == "caption"
                    and chunk.meta.doc_items[0].label.value == "table"
                )
                or (  # add text with same heading and page_number with current text length < INPUT_LEN_LIMIT // 4
                    current_item["metadata"]["chunk_type"] != "table"
                    and chunk.meta.doc_items[0].label.value not in ["caption", "table"]
                    and chunk.meta.headings
                    and current_item["metadata"]["headings"]
                    and chunk.meta.headings[0] == current_item["metadata"]["headings"][0]
                    and len(current_item["text"].split(" ")) < MAX_TOKENS
                    and chunk.meta.doc_items[0].prov
                    and current_item["metadata"]["page_number"] == chunk.meta.doc_items[0].prov[0].page_no
                )
            ):
                if (  # change chunk_type if caption is above table chunk
                    current_item["metadata"]["chunk_type"] == "caption"
                    and chunk.meta.doc_items[0].label.value == "table"
                ):
                    current_item["metadata"]["chunk_type"] = "table"
                current_item["text"] = f"{current_item['text']}\n{chunk.text}"
                continue

            # just add chunks with length > min_length
            if len(current_item["text"]) > min_length:
                current_item["text"] = (
                    f"{current_item['text'].strip()}\n\nPage Number: {current_item['metadata']['page_number']}"
                )
                chunks_dicts.append(current_item)

            current_item = {
                "text": f"{chunker.delim.join(chunk.meta.headings) if chunk.meta.headings and re.sub(r'^#+ ','',chunk.meta.headings[0]) not in chunk.text else ''}\n\n{chunk.text}",  # noqa: E501
                "metadata": {
                    "page_number": chunk.meta.doc_items[0].prov[0].page_no if chunk.meta.doc_items[0].prov else 1,
                    "chunk_type": chunk.meta.doc_items[0].label.value,
                    "bbox": None,
                    "file_type": chunk.meta.origin.mimetype,
                    "filename": chunk.meta.origin.filename,
                    "headings": chunk.meta.headings,
                },
            }

        if len(current_item["text"]) > min_length:
            current_item["text"] = (
                f"{current_item['text'].strip()}\n\nPage Number: {current_item['metadata']['page_number']}"
            )
            chunks_dicts.append(current_item)
        return [ParserChunk(**chunk) for chunk in chunks_dicts]


class DocumentConverterService:
    def __init__(self, doc_parser: DocumentConversionBase):
        self.doc_parser = doc_parser

    def convert_document(self, document: Tuple[str, BytesIO], **kwargs) -> ConversionResult:
        result = self.doc_parser.convert(document, **kwargs)
        if result.error:
            logger.error(f"Failed to convert {document[0]}: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        return result

    def convert_documents(self, documents: List[Tuple[str, BytesIO]], **kwargs) -> List[ConversionResult]:
        return self.doc_parser.convert_batch(documents, **kwargs)


class DoclingChunker:
    version = "2.0.0"

    def __init__(self, excluded_embed: List[str] = [], excluded_llm: List[str] = []):
        self.chunker = HierarchicalChunker(version="2.0.0", excluded_embed=excluded_embed, excluded_llm=excluded_llm)
    
    def hierarchical_chunk(
        self,
        dl_doc: DLDocument,
        indent=4,  # for display of heading level
        **kwargs: Any,
    ) -> List[BaseChunk]:
        r"""Chunk the provided document.
        Args:
            dl_doc (DLDocument): document to chunk
        Returns:
            List[DocChunk]: iterator over extracted chunks
        """
        results: list[DocChunk] = []
        heading_by_level: dict[LevelNumber, str] = {}
        list_items: list[TextItem] = []

        for item, level in dl_doc.iterate_items():
            captions = None
            chunk_indent = " " * indent * (level - 1) if level > 1 else ""

            if isinstance(item, DocItem):
                # first handle any merging needed
                if self.chunker.merge_list_items:
                    if isinstance(item, ListItem) or (  # TODO remove when all captured as ListItem:
                        isinstance(item, TextItem) and item.label == DocItemLabel.LIST_ITEM
                    ):
                        item.text = f"{chunk_indent}{item.text}"
                        list_items.append(item)
                        continue
                    elif list_items:  # need to yield
                        # not add chunk if level higher than current
                        if item.label == DocItemLabel.FOOTNOTE or (
                            results and heading_by_level and level > max(heading_by_level)
                        ):
                            results[
                                -1
                            ].text = f"{results[-1].text}\n{self.chunker.delim.join([i.text for i in list_items])}"
                        else:
                            results.append(
                                DocChunk(
                                    text=self.chunker.delim.join([i.text for i in list_items]),
                                    meta=DocMeta(
                                        doc_items=list_items,
                                        headings=[heading_by_level[k] for k in sorted(heading_by_level)] or None,
                                        origin=dl_doc.origin,
                                    ),
                                ),
                            )
                        list_items = []  # reset

                if isinstance(item, SectionHeaderItem) or (
                    isinstance(item, TextItem) and item.label in [DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE]
                ):
                    level = (
                        item.level
                        if isinstance(item, SectionHeaderItem)
                        else (0 if item.label == DocItemLabel.TITLE else 1)
                    )
                    # check header hierarchy due to docling detection (6->6.1->heading text)
                    # if match, increase the level to maximum
                    if re.match(r"\d+\.\d+ ", item.text):
                        level = 2
                    elif (
                        heading_by_level
                        and re.sub(r"#+ ", "", heading_by_level[min(heading_by_level)])[0].isdigit()
                        and not re.match(r"\d+\.? ", item.text)
                    ):
                        level = min(max(heading_by_level) + 1, 3)
                    marker = "#" * level if level > 1 else "#"
                    heading_by_level[level] = f"{marker} {item.text}"

                    # remove headings of higher level as they just went out of scope
                    keys_to_del = [k for k in heading_by_level if k > level]
                    for k in keys_to_del:
                        heading_by_level.pop(k, None)
                    continue

                # skip page number text
                if isinstance(item, TextItem) and item.prov and item.text == str(item.prov[0].page_no):
                    continue

                if isinstance(item, TextItem) or ((not self.chunker.merge_list_items) and isinstance(item, ListItem)):
                    text = item.text
                elif isinstance(item, TableItem):
                    md_table = item.export_to_markdown()
                    text = item.caption_text(dl_doc) + "\n" + md_table + "\n"
                    captions = [c.text for c in [r.resolve(dl_doc) for r in item.captions]] or None
                elif isinstance(item, PictureItem):
                    text = DoclingDocumentConversion._process_document_image(
                        dl_doc,
                        item,
                        **kwargs
                    )
                    if not text:
                        continue
                else:
                    text = item.text

                c = DocChunk(
                    text=f"{chunk_indent}{text}".strip(),
                    meta=DocMeta(
                        doc_items=[item],
                        headings=[heading_by_level[k] for k in sorted(heading_by_level)] or None,
                        captions=captions,
                        origin=dl_doc.origin,
                    ),
                )
                results.append(c)

        if self.chunker.merge_list_items and list_items:  # need to yield
            results.append(
                DocChunk(
                    text=self.chunker.delim.join([i.text for i in list_items]).strip(),
                    meta=DocMeta(
                        doc_items=list_items,
                        headings=[heading_by_level[k] for k in sorted(heading_by_level)] or None,
                        origin=dl_doc.origin,
                    ),
                ),
            )

        return results
