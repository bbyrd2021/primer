# Primer

Primer is a Python project for working with study materials, cards, and supporting app assets.

## Requirements

- Python 3.11+
- `pip`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Project layout

- `main.py`: primary entrypoint
- `core/`: application logic
- `models/`: data models
- `tests/`: test suite
- `static/`: static assets

## Notes

- Local runtime data in `uploads/`, `chroma_db/`, and `cards_db/` is excluded from Git.
- Local secrets in `.env` are excluded from Git.
