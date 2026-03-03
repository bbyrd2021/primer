# main.py
import asyncio
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.embeddings import index_chunks
from core.extract import extract_paper_card, get_session_cards
from core.ingest import chunk_pages, estimate_text_density, extract_text
from core.synthesize import chat, generate_brief, stream_brief, stream_chat
from models.message import ChatRequest, ChatResponse
from models.paper import PaperCard, UploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Primer", version="0.1.0")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Low text density threshold — below this, warn the user about scan quality
LOW_DENSITY_THRESHOLD = 100  # chars per page


def _validate_llm_key(x_llm_key: str) -> None:
    """Raise 400 if the provided key is not a recognized provider key."""
    if not x_llm_key or not (
        x_llm_key.startswith("sk-ant-") or x_llm_key.startswith("sk-")
    ):
        raise HTTPException(
            status_code=400,
            detail="A valid Anthropic or OpenAI API key is required to use Primer.",
        )


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return (Path("static") / "index.html").read_text()


@app.post("/api/upload", response_model=UploadResponse)
async def upload_papers(
    files: list[UploadFile] = File(...),
    research_question: str = Form(...),
    session_id: str | None = Form(None),
    x_llm_key: str = Header(default=""),
) -> UploadResponse:
    """Upload and process PDFs. Runs card extraction and chunk indexing per file."""
    _validate_llm_key(x_llm_key)

    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)

    tasks = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            continue
        tasks.append(
            _process_single_file(file, research_question, session_id, session_dir, x_llm_key)
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    cards = []
    total_chunks = 0
    for result in results:
        if isinstance(result, Exception):
            logger.error("File processing failed: %s", result)
            continue
        card, n_chunks = result
        cards.append(card)
        total_chunks += n_chunks

    return UploadResponse(
        session_id=session_id,
        papers=cards,
        total_papers=len(cards),
        total_chunks=total_chunks,
    )


async def _process_single_file(
    file: UploadFile,
    research_question: str,
    session_id: str,
    session_dir: Path,
    api_key: str = "",
) -> tuple[PaperCard, int]:
    """Save, extract, and index a single PDF. Returns (card, chunk_count)."""
    # Save file to disk
    file_path = session_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract text (used by both pipelines)
    full_text, pages = extract_text(str(file_path))

    # Warn if likely scanned
    density = estimate_text_density(full_text, len(pages))
    if density < LOW_DENSITY_THRESHOLD:
        logger.warning(
            "%s appears scanned (%.0f chars/page). Extraction quality may be low.",
            file.filename,
            density,
        )

    # Run both pipelines concurrently — card extraction and chunk indexing
    loop = asyncio.get_event_loop()

    card_task = loop.run_in_executor(
        None,
        extract_paper_card,
        full_text,
        file.filename,
        research_question,
        session_id,
        api_key,
    )
    index_task = loop.run_in_executor(
        None, lambda: index_chunks(chunk_pages(pages), session_id)
    )

    card, n_chunks = await asyncio.gather(card_task, index_task)
    return card, n_chunks


@app.get("/api/cards/{session_id}", response_model=list[PaperCard])
async def get_cards(session_id: str) -> list[PaperCard]:
    """Return all extracted paper cards for a session, sorted by relevance."""
    return get_session_cards(session_id)


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    x_llm_key: str = Header(default=""),
) -> ChatResponse:
    """Generate a grounded chat response or full research brief."""
    _validate_llm_key(x_llm_key)

    if request.generate_brief:
        return generate_brief(
            research_question=request.research_question,
            session_id=request.session_id,
            api_key=x_llm_key,
        )

    return chat(
        message=request.message,
        session_id=request.session_id,
        research_question=request.research_question,
        paper_count=request.paper_count,
        history=request.history,
        api_key=x_llm_key,
    )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    x_llm_key: str = Header(default=""),
) -> StreamingResponse:
    """Stream a chat response or research brief as server-sent events."""
    _validate_llm_key(x_llm_key)

    if request.generate_brief:
        generator = stream_brief(
            research_question=request.research_question,
            session_id=request.session_id,
            api_key=x_llm_key,
        )
    else:
        generator = stream_chat(
            message=request.message,
            session_id=request.session_id,
            research_question=request.research_question,
            paper_count=request.paper_count,
            history=request.history,
            api_key=x_llm_key,
        )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
