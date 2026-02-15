# Instagram Downloader (MVP)

PRD-aligned MVP web app for validating and resolving public Instagram links into downloadable media items.

## Features
- URL normalization and validation for `/p/`, `/reel/`, `/tv/`
- Resolve endpoint with structured error taxonomy
- Preview + per-item download actions
- Responsive mobile-first UI
- In-memory IP rate limiting
- Responsible-use legal/privacy messaging

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000.

## Tests
```bash
pytest
```
