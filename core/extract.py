# core/extract.py
import json
import logging
from pathlib import Path

from core.llm import BRIEF_MAX_TOKENS, complete
from core.prompts import EXTRACTION_PROMPT
from models.paper import PaperCard

logger = logging.getLogger(__name__)

# Constants
CARDS_DIR = Path("cards_db")
CARDS_DIR.mkdir(exist_ok=True)

MAX_PAPER_TEXT_CHARS: int = 60_000
FRONT_CHARS: int = 40_000
BACK_CHARS: int = 20_000


def _truncate_paper_text(text: str) -> str:
    """Truncate long papers to fit context window.

    Uses first 40k + last 20k chars rather than middle truncation.
    Academic papers front-load methodology (abstract, intro, related work)
    and back-load results/conclusions. The middle is implementation details
    that add noise without improving extraction quality.
    """
    if len(text) <= MAX_PAPER_TEXT_CHARS:
        return text
    return text[:FRONT_CHARS] + "\n\n[...middle truncated...]\n\n" + text[-BACK_CHARS:]


def _api_error_message(exc: Exception) -> str:
    """Map an API exception to a human-readable error description."""
    msg = str(exc).lower()
    if any(k in msg for k in ("context", "too long", "token")):
        return "Extraction failed — paper may be too large for the model's context window."
    if any(k in msg for k in ("rate", "429")):
        return "Extraction failed — rate limit reached. Try uploading fewer papers at once."
    if any(k in msg for k in ("auth", "401", "api_key")):
        return "Extraction failed — API key may be invalid."
    return f"Extraction failed — {type(exc).__name__}"


def extract_paper_card(
    paper_text: str,
    filename: str,
    research_question: str,
    session_id: str,
    api_key: str = "",
) -> PaperCard:
    """Extract a structured card from a single paper via Claude API.

    Makes one Claude API call per paper. Returns a PaperCard with all
    fields populated from the PDF text. Falls back to a minimal error
    card if JSON parsing fails — never raises.

    Args:
        paper_text: Full extracted text of the paper.
        filename: Original PDF filename (used as card identity and for persistence).
        research_question: The project research question used to score relevance.
        session_id: The project session ID for scoping the card cache on disk.

    Returns:
        A populated PaperCard. If Claude returns unparseable JSON, returns
        an error card with error=True rather than raising.
    """
    truncated_text = _truncate_paper_text(paper_text)

    prompt = EXTRACTION_PROMPT.format(
        research_question=research_question,
        paper_text=truncated_text,
    )

    try:
        raw = complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are a research paper analysis assistant. Output ONLY valid JSON — no markdown, no preamble, no explanation.",
            api_key=api_key,
            max_tokens=BRIEF_MAX_TOKENS,
        ).strip()
    except Exception as e:
        logger.warning("Card extraction API call failed for %s: %s", filename, e)
        card = PaperCard(
            filename=filename,
            session_id=session_id,
            title=filename,
            methodology=_api_error_message(e),
            error=True,
        )
        session_dir = CARDS_DIR / session_id
        session_dir.mkdir(exist_ok=True)
        card_path = session_dir / f"{filename}.json"
        card_path.write_text(card.model_dump_json(indent=2))
        return card

    # Strip markdown code fences if Claude adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
        card = PaperCard(
            filename=filename,
            session_id=session_id,
            **{k: v for k, v in data.items() if k in PaperCard.model_fields},
        )
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Card extraction parse failed for %s: %s", filename, e)
        card = PaperCard(
            filename=filename,
            session_id=session_id,
            title=filename,
            methodology="Extraction failed — open paper manually.",
            error=True,
        )

    # Persist to disk
    session_dir = CARDS_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    card_path = session_dir / f"{filename}.json"
    card_path.write_text(card.model_dump_json(indent=2))

    return card


def get_session_cards(session_id: str) -> list[PaperCard]:
    """Load all cards for a session, sorted by relevance score descending.

    Args:
        session_id: The project session ID to load cards for.

    Returns:
        List of PaperCard objects sorted by relevance_score descending.
        Cards with no score sort to the bottom. Returns empty list if
        session has no cards.
    """
    session_dir = CARDS_DIR / session_id
    if not session_dir.exists():
        return []

    cards = []
    for card_file in session_dir.glob("*.json"):
        if card_file.name == "meta.json":
            continue
        try:
            card = PaperCard.model_validate_json(card_file.read_text())
            cards.append(card)
        except Exception as e:
            logger.warning("Failed to load card from %s: %s", card_file, e)

    return sorted(cards, key=lambda c: (c.relevance_score or 0), reverse=True)
