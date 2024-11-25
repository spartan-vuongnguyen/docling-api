from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


class ParserChunkMetadata(BaseModel):
    page_number: int
    chunk_type: str
    bbox: None
    file_type: str
    filename: str
    headings: Optional[List[str]]


class ParserChunk(BaseModel):
    text: str
    metadata: ParserChunkMetadata


class ImageData(BaseModel):
    type: Optional[Literal["table", "picture"]] = Field(None, description="The type of the image")
    filename: Optional[str] = Field(None, description="The filename of the image")
    image: Optional[str] = Field(None, description="The image data")


class ConversionResult(BaseModel):
    filename: str = Field(None, description="The filename of the document")
    chunk_dicts: List[ParserChunk] = Field(default_factory=ParserChunk, description="The list of chunks in the document")
    error: Optional[str] = Field(None, description="The error that occurred during the conversion")


class BatchConversionResult(BaseModel):
    conversion_results: List[ConversionResult] = Field(
        default_factory=list, description="The results of the conversions"
    )


class ConversationJobResult(BaseModel):
    job_id: Optional[str] = Field(None, description="The id of the conversion job")
    result: Optional[ConversionResult] = Field(None, description="The result of the conversion job")
    error: Optional[str] = Field(None, description="The error that occurred during the conversion job")
    status: Literal["IN_PROGRESS", "SUCCESS", "FAILURE"] = Field(None, description="The status of the conversion job")


class BatchConversionJobResult(BaseModel):
    job_id: str = Field(..., description="The id of the conversion job")
    conversion_results: List[ConversationJobResult] = Field(
        default_factory=list, description="The results of the conversion job"
    )
    status: Literal["IN_PROGRESS", "SUCCESS", "FAILURE"] = Field(
        None, description="The status of the entire conversion jobs in the batch"
    )
    error: Optional[str] = Field(None, description="If the entire batch failed, this will be the error message")
