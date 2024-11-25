import re
import json
from enum import Enum
import filetype
from typing import Dict, List

import boto3

from doc_parser.settings import logger


class InputFormat(str, Enum):
    DOCX = "docx"
    PPTX = "pptx"
    HTML = "html"
    IMAGE = "image"
    PDF = "pdf"
    ASCIIDOC = "asciidoc"
    MD = "md"


class OutputFormat(str, Enum):
    MARKDOWN = "md"
    JSON = "json"
    TEXT = "text"
    DOCTAGS = "doctags"


FormatToExtensions: Dict[InputFormat, List[str]] = {
    InputFormat.DOCX: ["docx", "dotx", "docm", "dotm"],
    InputFormat.PPTX: ["pptx", "potx", "ppsx", "pptm", "potm", "ppsm"],
    InputFormat.PDF: ["pdf"],
    InputFormat.MD: ["md"],
    InputFormat.HTML: ["html", "htm", "xhtml"],
    InputFormat.IMAGE: ["jpg", "jpeg", "png", "tif", "tiff", "bmp"],
    InputFormat.ASCIIDOC: ["adoc", "asciidoc", "asc"],
}

FormatToMimeType: Dict[InputFormat, List[str]] = {
    InputFormat.DOCX: [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    ],
    InputFormat.PPTX: [
        "application/vnd.openxmlformats-officedocument.presentationml.template",
        "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ],
    InputFormat.HTML: ["text/html", "application/xhtml+xml"],
    InputFormat.IMAGE: [
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/gif",
        "image/bmp",
    ],
    InputFormat.PDF: ["application/pdf"],
    InputFormat.ASCIIDOC: ["text/asciidoc"],
    InputFormat.MD: ["text/markdown", "text/x-markdown"],
}
MimeTypeToFormat = {mime: fmt for fmt, mimes in FormatToMimeType.items() for mime in mimes}


def detect_html_xhtml(content):
    content_str = content.decode("ascii", errors="ignore").lower()
    # Remove XML comments
    content_str = re.sub(r"<!--(.*?)-->", "", content_str, flags=re.DOTALL)
    content_str = content_str.lstrip()

    if re.match(r"<\?xml", content_str):
        if "xhtml" in content_str[:1000]:
            return "application/xhtml+xml"

    if re.match(r"<!doctype\s+html|<html|<head|<body", content_str):
        return "text/html"

    return None


def guess_format(obj: bytes, filename: str = None):
    content = b""  # empty binary blob
    mime = None

    if isinstance(obj, bytes):
        content = obj
        mime = filetype.guess_mime(content)
        if mime is None:
            ext = filename.rsplit(".", 1)[-1] if ("." in filename and not filename.startswith(".")) else ""
            mime = mime_from_extension(ext)

    mime = mime or detect_html_xhtml(content)
    mime = mime or "text/plain"
    return MimeTypeToFormat.get(mime)


def mime_from_extension(ext):
    mime = None
    if ext in FormatToExtensions[InputFormat.ASCIIDOC]:
        mime = FormatToMimeType[InputFormat.ASCIIDOC][0]
    elif ext in FormatToExtensions[InputFormat.HTML]:
        mime = FormatToMimeType[InputFormat.HTML][0]
    elif ext in FormatToExtensions[InputFormat.MD]:
        mime = FormatToMimeType[InputFormat.MD][0]

    return mime


def is_file_format_supported(file_bytes: bytes, filename: str) -> bool:
    return guess_format(file_bytes, filename) in FormatToExtensions.keys()


def image_to_text(
    base64_image: str,
    region_name="us-east-1",
    max_tokens=256,
    temperature=0.3,
    top_p=0.95,
) -> str:
    inference_profile_id = "us.meta.llama3-2-11b-instruct-v1:0"

    # Initialize the Bedrock client
    client = boto3.client("bedrock-runtime", region_name=region_name)  # Adjust region as necessary

    # Prepare the messages for the model invocation
    prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>You are a helpful AI extraction for extracting text from images. No add any additional text.<|eot_id|><|start_header_id|>user<|end_header_id|>Extract all text in the given image in markdown.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""  # noqa: E501

    # Call the model with cross-region inference
    try:
        body = json.dumps(
            {
                "temperature": temperature,
                "top_p": top_p,
                "max_gen_len": max_tokens,
                "prompt": prompt,
                "images": [base64_image],
            },
        )

        response = client.invoke_model(
            modelId=inference_profile_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response.get("body").read())

        # text
        result = response_body.get("generation").strip()

        logger.info(f"Successful for calling {inference_profile_id}.")

        return result

    except Exception as e:
        logger.exception(f"An error occurred while invoking the model: {e}.")
        return ""
