# tests/test_extract.py
import json
from unittest.mock import patch

from core.extract import (
    BACK_CHARS,
    FRONT_CHARS,
    MAX_PAPER_TEXT_CHARS,
    _truncate_paper_text,
    extract_paper_card,
    get_session_cards,
)
from models.paper import PaperCard

# ---------------------------------------------------------------------------
# _truncate_paper_text
# ---------------------------------------------------------------------------


def test_truncate_paper_text_short_text_unchanged():
    text = "a" * (MAX_PAPER_TEXT_CHARS - 1)
    assert _truncate_paper_text(text) == text


def test_truncate_paper_text_exact_limit_unchanged():
    text = "a" * MAX_PAPER_TEXT_CHARS
    assert _truncate_paper_text(text) == text


def test_truncate_paper_text_long_text_uses_front_and_back():
    front = "F" * FRONT_CHARS
    middle = "M" * 10_000
    back = "B" * BACK_CHARS
    text = front + middle + back

    result = _truncate_paper_text(text)

    assert result.startswith("F" * FRONT_CHARS)
    assert result.endswith("B" * BACK_CHARS)
    assert "M" not in result
    assert "[...middle truncated...]" in result


# ---------------------------------------------------------------------------
# extract_paper_card — mocked complete() responses
# ---------------------------------------------------------------------------

VALID_CARD_JSON = {
    "title": "YOLOPX: Anchor-free multi-task learning",
    "authors": ["Author A", "Author B"],
    "venue": "Pattern Recognition",
    "year": 2024,
    "task": "Panoptic driving perception",
    "modality": "Camera",
    "methodology": "Anchor-free detection with shared backbone.",
    "results": "71.6 mAP on BDD100K",
    "datasets": ["BDD100K"],
    "pretraining": "ImageNet",
    "code_available": True,
    "code_url": "https://github.com/example/yolopx",
    "key_limitations": "Limited to monocular camera input.",
    "synthesis_note": "Directly relevant to multi-task perception.",
    "relevance_score": 5,
    "tier": 1,
}


def test_extract_paper_card_returns_valid_card(tmp_path):
    with (
        patch("core.extract.complete", return_value=json.dumps(VALID_CARD_JSON)),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            paper_text="Some paper text",
            filename="yolopx.pdf",
            research_question="What are multi-task driving perception approaches?",
            session_id="test-session",
            api_key="sk-ant-test",
        )

    assert isinstance(card, PaperCard)
    assert card.filename == "yolopx.pdf"
    assert card.session_id == "test-session"
    assert card.title == VALID_CARD_JSON["title"]
    assert card.venue == "Pattern Recognition"
    assert card.year == 2024
    assert card.relevance_score == 5
    assert card.tier == 1
    assert card.error is False


def test_extract_paper_card_strips_markdown_fences(tmp_path):
    fenced = f"```json\n{json.dumps(VALID_CARD_JSON)}\n```"
    with (
        patch("core.extract.complete", return_value=fenced),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            "text", "paper.pdf", "question", "session", api_key="sk-ant-test"
        )

    assert card.error is False
    assert card.title == VALID_CARD_JSON["title"]


def test_extract_paper_card_falls_back_on_invalid_json(tmp_path):
    with (
        patch("core.extract.complete", return_value="this is not json {"),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            "text", "broken.pdf", "question", "session", api_key="sk-ant-test"
        )

    assert card.error is True
    assert card.filename == "broken.pdf"
    assert card.session_id == "session"
    # title falls back to filename
    assert card.title == "broken.pdf"


def test_extract_paper_card_falls_back_on_empty_response(tmp_path):
    with (
        patch("core.extract.complete", return_value=""),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            "text", "empty.pdf", "question", "session", api_key="sk-ant-test"
        )

    assert card.error is True


def test_extract_paper_card_persists_json_to_disk(tmp_path):
    with (
        patch("core.extract.complete", return_value=json.dumps(VALID_CARD_JSON)),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        extract_paper_card(
            "text", "yolopx.pdf", "question", "test-session", api_key="sk-ant-test"
        )

    card_path = tmp_path / "test-session" / "yolopx.pdf.json"
    assert card_path.exists()
    saved = PaperCard.model_validate_json(card_path.read_text())
    assert saved.title == VALID_CARD_JSON["title"]


# ---------------------------------------------------------------------------
# extract_paper_card — API exception handling
# ---------------------------------------------------------------------------


def test_extract_paper_card_catches_api_exception(tmp_path):
    with (
        patch("core.extract.complete", side_effect=Exception("API call failed")),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            "text", "paper.pdf", "question", "session", api_key="sk-ant-test"
        )

    assert card.error is True
    assert card.filename == "paper.pdf"


def test_extract_paper_card_api_exception_persists_error_card(tmp_path):
    with (
        patch("core.extract.complete", side_effect=Exception("API call failed")),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        extract_paper_card(
            "text", "paper.pdf", "question", "session", api_key="sk-ant-test"
        )

    card_path = tmp_path / "session" / "paper.pdf.json"
    assert card_path.exists()


def test_extract_paper_card_api_error_message_context_window(tmp_path):
    with (
        patch(
            "core.extract.complete",
            side_effect=Exception("prompt is too long, exceeds context window"),
        ),
        patch("core.extract.CARDS_DIR", tmp_path),
    ):
        card = extract_paper_card(
            "text", "paper.pdf", "question", "session", api_key="sk-ant-test"
        )

    assert card.error is True
    assert "context window" in card.methodology or "too large" in card.methodology


# ---------------------------------------------------------------------------
# get_session_cards
# ---------------------------------------------------------------------------


def test_get_session_cards_returns_empty_for_unknown_session(tmp_path):
    with patch("core.extract.CARDS_DIR", tmp_path):
        cards = get_session_cards("nonexistent-session")
    assert cards == []


def test_get_session_cards_sorts_by_relevance_descending(tmp_path):
    session_dir = tmp_path / "sorted-session"
    session_dir.mkdir()

    for score, name in [(2, "low.pdf"), (5, "high.pdf"), (3, "mid.pdf")]:
        card = PaperCard(
            filename=name, session_id="sorted-session", relevance_score=score
        )
        (session_dir / f"{name}.json").write_text(card.model_dump_json())

    with patch("core.extract.CARDS_DIR", tmp_path):
        cards = get_session_cards("sorted-session")

    assert [c.relevance_score for c in cards] == [5, 3, 2]


def test_get_session_cards_skips_corrupt_files(tmp_path):
    session_dir = tmp_path / "corrupt-session"
    session_dir.mkdir()

    # One valid card
    good = PaperCard(
        filename="good.pdf", session_id="corrupt-session", relevance_score=4
    )
    (session_dir / "good.pdf.json").write_text(good.model_dump_json())

    # One corrupt file
    (session_dir / "bad.pdf.json").write_text("{ not valid json }")

    with patch("core.extract.CARDS_DIR", tmp_path):
        cards = get_session_cards("corrupt-session")

    assert len(cards) == 1
    assert cards[0].filename == "good.pdf"
