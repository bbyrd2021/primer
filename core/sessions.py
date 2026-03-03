# core/sessions.py
import logging
from datetime import datetime, timezone
from pathlib import Path

from models.paper import SessionMeta

logger = logging.getLogger(__name__)
CARDS_DIR = Path("cards_db")


def save_meta(
    session_id: str,
    research_question: str,
    paper_count: int,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SessionMeta:
    """Write or overwrite meta.json. Pass created_at to preserve it on update."""
    now = datetime.now(timezone.utc)
    meta = SessionMeta(
        session_id=session_id,
        research_question=research_question,
        paper_count=paper_count,
        created_at=created_at or now,
        updated_at=updated_at,
    )
    session_dir = CARDS_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    (session_dir / "meta.json").write_text(meta.model_dump_json(indent=2))
    return meta


def load_meta(session_id: str) -> SessionMeta | None:
    """Return SessionMeta or None if missing/corrupt."""
    path = CARDS_DIR / session_id / "meta.json"
    if not path.exists():
        return None
    try:
        return SessionMeta.model_validate_json(path.read_text())
    except Exception as e:
        logger.warning("Failed to load meta for %s: %s", session_id, e)
        return None


def list_sessions() -> list[SessionMeta]:
    """Return all sessions with meta.json, sorted by created_at descending."""
    results = []
    for meta_path in CARDS_DIR.glob("*/meta.json"):
        meta = load_meta(meta_path.parent.name)
        if meta:
            results.append(meta)
    return sorted(results, key=lambda m: m.created_at, reverse=True)
