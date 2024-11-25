# Documents to Markdown Converter Server

> [!IMPORTANT]
> This backend server is a robust, scalable solution for effortlessly converting a wide range of document formats—including PDF, DOCX, PPTX, HTML, JPG, PNG, TIFF, BMP, AsciiDoc, and Markdown—into Markdown. Powered by [Docling](https://github.com/DS4SD/docling) (IBM's advanced document parser), this service is built with FastAPI, Celery, and Redis, ensuring fast, efficient processing. Optimized for both CPU and GPU modes, with GPU highly recommended for production environments, this solution offers high performance and flexibility, making it ideal for handling complex document processing at scale.

## Features
- **Multiple Format Support**: Converts various document types including:
  - PDF files
  - Microsoft Word documents (DOCX)
  - PowerPoint presentations (PPTX)
  - HTML files
  - Images (JPG, PNG, TIFF, BMP)
  - AsciiDoc files
  - Markdown files

- **Conversion Capabilities**:
  - Text extraction and formatting
  - Table detection, extraction and conversion
  - Image extraction and processing
  - Multi-language OCR support (French, German, Spanish, English, Italian, Portuguese etc)
  - Configurable image resolution scaling

- **API Endpoints**:
  - Synchronous single document conversion
  - Synchronous batch document conversion
  - Asynchronous single document conversion with job tracking
  - Asynchronous batch conversion with job tracking

- **Processing Modes**:
  - CPU-only processing for standard deployments
  - GPU-accelerated processing for improved performance
  - Distributed task processing using Celery
  - Task monitoring through Flower dashboard

## Environment Setup (Running Locally)

### Prerequisites
- Python 3.8 or higher
- Poetry (Python package manager)
- Redis server (for task queue)

### 1. Install Poetry (if not already installed)
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Clone and Setup Project
```bash
git clone https://github.com/drmingler/docling-api.git
cd docling-parser
poetry install
```

### 3. Configure Environment
Create a `.env` file in the project root:
```bash
REDIS_HOST=redis://localhost:6379/0
ENV=development
```

### 4. Start the Application Components

1. Start the FastAPI server:
```bash
poetry run uvicorn main:app --reload --port 9090
```

### 5. Verify Installation

1. Check if the API server is running:
```bash
curl http://localhost:9090/docs
```

### Development Notes

- The API documentation is available at http://localhost:9090/docs

## Environment Setup (Running in Docker)

1. Clone the repository:
```bash
git clone https://github.com/drmingler/docling-api.git
cd doc-parser
```

2. Create a `.env` file:
```bash
ENV=production
```

### CPU Mode
To start the service using CPU-only processing, use the following command.:
```bash
docker-compose -f docker-compose.cpu.yml up --build
```

### GPU Mode (Recommend for production)
For production, it is recommended to enable GPU acceleration, as it significantly improves performance. Use the command below to start the service with GPU support.:
```bash
docker-compose -f docker-compose.gpu.yml up --build
```

## Service Components

The service will start the following components:

- **API Server**: http://localhost:9090

## API Usage

### Synchronous Conversion

Convert a single document immediately:

```bash
curl -X POST "http://localhost:9090/documents/convert" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=@/path/to/document.pdf" \
  -F "extract_tables_as_images=true" \
  -F "image_resolution_scale=1" \
  -F "max_tokens=256" \
  -F "temperature=0.3" \
  -F "top_p=0.95"
```

Convert many documents:

```bash
curl -X POST "http://localhost:9090/documents/batch-convert" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "document=[@/path/to/document.pdf]" \
  -F "extract_tables_as_images=true" \
  -F "image_resolution_scale=1" \
  -F "max_tokens=256" \
  -F "temperature=0.3" \
  -F "top_p=0.95"
```
## Configuration Options

- `image_resolution_scale`: Control the resolution of extracted images (1-4)
- `extract_tables_as_images`: Extract tables as images (true/false)
- `CPU_ONLY`: Build argument to switch between CPU/GPU modes

## Architecture

The service uses a distributed architecture with the following components:

1. FastAPI application serving the REST API
2. Docling for the file conversion

## Performance Considerations

- GPU mode provides significantly faster processing for large documents
- CPU mode is suitable for smaller deployments or when GPU is not available

## License
The codebase is under MIT license. See LICENSE for more information

## Acknowledgements
- [Docling](https://github.com/DS4SD/docling) the state-of-the-art document conversion library by IBM
- [FastAPI](https://fastapi.tiangolo.com/) the web framework
