# core/sessions.py
import logging
import shutil
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
    user_id: str | None = None,
) -> SessionMeta:
    """Write or overwrite meta.json. Pass created_at to preserve it on update."""
    now = datetime.now(timezone.utc)
    meta = SessionMeta(
        session_id=session_id,
        research_question=research_question,
        paper_count=paper_count,
        created_at=created_at or now,
        updated_at=updated_at,
        user_id=user_id,
    )
    session_dir = CARDS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
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


def list_sessions(user_id: str | None = None) -> list[SessionMeta]:
    """Return sessions with meta.json, sorted by created_at descending.

    When user_id is provided, returns only sessions owned by that user.
    Sessions with no user_id (legacy) are excluded from filtered results.
    """
    results = []
    for meta_path in CARDS_DIR.glob("*/meta.json"):
        meta = load_meta(meta_path.parent.name)
        if meta:
            if user_id is not None:
                if meta.user_id == user_id:
                    results.append(meta)
            else:
                results.append(meta)
    return sorted(results, key=lambda m: m.created_at, reverse=True)


def delete_session(session_id: str) -> None:
    """Delete all data for a session (cards, uploads, ChromaDB)."""
    shutil.rmtree(CARDS_DIR / session_id, ignore_errors=True)
    shutil.rmtree(Path("uploads") / session_id, ignore_errors=True)
    shutil.rmtree(Path("chroma_db") / session_id, ignore_errors=True)
