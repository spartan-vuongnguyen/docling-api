from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from doc_parser.route import router as doc_parser_router

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


app.include_router(doc_parser_router, prefix="", tags=["doc-parser"])
