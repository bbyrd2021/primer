# tests/test_sessions.py
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from models.paper import SessionMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXED_EARLIER = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _import_sessions(tmp_path: Path):
    """Import core.sessions with CARDS_DIR patched to tmp_path."""
    import core.sessions as mod
    mod.CARDS_DIR = tmp_path
    return mod


# ---------------------------------------------------------------------------
# save_meta
# ---------------------------------------------------------------------------


def test_save_meta_creates_meta_json(tmp_path):
    mod = _import_sessions(tmp_path)
    result = mod.save_meta(
        session_id="abc",
        research_question="What is RLHF?",
        paper_count=3,
    )
    meta_path = tmp_path / "abc" / "meta.json"
    assert meta_path.exists()
    assert isinstance(result, SessionMeta)


def test_save_meta_returns_correct_fields(tmp_path):
    mod = _import_sessions(tmp_path)
    result = mod.save_meta(
        session_id="sess-1",
        research_question="Deep learning in medicine",
        paper_count=5,
        created_at=FIXED_NOW,
    )
    assert result.session_id == "sess-1"
    assert result.research_question == "Deep learning in medicine"
    assert result.paper_count == 5
    assert result.created_at == FIXED_NOW
    assert result.updated_at is None


def test_save_meta_preserves_provided_created_at(tmp_path):
    mod = _import_sessions(tmp_path)
    # First save
    mod.save_meta(
        session_id="sess-2",
        research_question="Question v1",
        paper_count=1,
        created_at=FIXED_EARLIER,
    )
    # Update — pass the original created_at
    result = mod.save_meta(
        session_id="sess-2",
        research_question="Question v2",
        paper_count=1,
        created_at=FIXED_EARLIER,
        updated_at=FIXED_NOW,
    )
    assert result.created_at == FIXED_EARLIER
    assert result.updated_at == FIXED_NOW


def test_save_meta_stores_updated_at_when_provided(tmp_path):
    mod = _import_sessions(tmp_path)
    result = mod.save_meta(
        session_id="sess-3",
        research_question="Some question",
        paper_count=2,
        updated_at=FIXED_NOW,
    )
    assert result.updated_at == FIXED_NOW


def test_save_meta_updated_at_is_none_when_omitted(tmp_path):
    mod = _import_sessions(tmp_path)
    result = mod.save_meta(
        session_id="sess-4",
        research_question="Some question",
        paper_count=0,
    )
    assert result.updated_at is None


# ---------------------------------------------------------------------------
# load_meta
# ---------------------------------------------------------------------------


def test_load_meta_returns_none_for_missing_session(tmp_path):
    mod = _import_sessions(tmp_path)
    assert mod.load_meta("nonexistent") is None


def test_load_meta_returns_none_for_corrupt_json(tmp_path):
    mod = _import_sessions(tmp_path)
    session_dir = tmp_path / "bad-sess"
    session_dir.mkdir()
    (session_dir / "meta.json").write_text("{ this is not valid json }")
    result = mod.load_meta("bad-sess")
    assert result is None


def test_load_meta_returns_correct_session_meta(tmp_path):
    mod = _import_sessions(tmp_path)
    saved = mod.save_meta(
        session_id="sess-load",
        research_question="Test question",
        paper_count=7,
        created_at=FIXED_NOW,
    )
    loaded = mod.load_meta("sess-load")
    assert loaded is not None
    assert loaded.session_id == "sess-load"
    assert loaded.research_question == "Test question"
    assert loaded.paper_count == 7
    assert loaded.created_at == FIXED_NOW


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


def test_list_sessions_returns_empty_when_no_sessions(tmp_path):
    mod = _import_sessions(tmp_path)
    assert mod.list_sessions() == []


def test_list_sessions_returns_all_sorted_newest_first(tmp_path):
    mod = _import_sessions(tmp_path)
    mod.save_meta("old-sess", "Old question", 1, created_at=FIXED_EARLIER)
    mod.save_meta("new-sess", "New question", 2, created_at=FIXED_NOW)
    sessions = mod.list_sessions()
    assert len(sessions) == 2
    assert sessions[0].session_id == "new-sess"
    assert sessions[1].session_id == "old-sess"


def test_list_sessions_skips_directories_without_meta_json(tmp_path):
    mod = _import_sessions(tmp_path)
    mod.save_meta("real-sess", "Has meta", 1, created_at=FIXED_NOW)
    # Create a session dir without meta.json
    (tmp_path / "no-meta-sess").mkdir()
    sessions = mod.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "real-sess"


def test_list_sessions_skips_corrupt_meta_json(tmp_path):
    mod = _import_sessions(tmp_path)
    mod.save_meta("good-sess", "Good", 1, created_at=FIXED_NOW)
    corrupt_dir = tmp_path / "corrupt-sess"
    corrupt_dir.mkdir()
    (corrupt_dir / "meta.json").write_text("not json at all")
    sessions = mod.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "good-sess"
