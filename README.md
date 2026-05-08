# OOP Final Project

This repository contains a session-based counseling chat system built with object-oriented design.

## Quick Start (For Grading)

1) Create and activate a virtual environment.

- Windows (PowerShell):
  - `python -m venv .venv`
  - `.venv\Scripts\Activate.ps1`

2) Install dependencies.

- `pip install -r chatagent/requirements.txt`

3) (Optional) Set API environment variables for real LLM responses.

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (default in code: `https://api.deepseek.com/v1`)
- `OPENAI_MODEL` (default in code: `deepseek-chat`)

4) Run the HTTP app.

- `python chatagent/api_server.py`
- Open: `http://127.0.0.1:8000`

5) Run tests.

- `python -m pytest chatagent/tests -q`

## Project Layout

- `chatagent/`: main application code
  - `application/`: application services (auth/chat/session/monitor)
  - `domain/`: core domain models
  - `infrastructure/`: runtime and repository implementations
  - `interfaces/http/`: FastAPI routes, schemas, and app wiring
  - `tests/`: unit tests and HTTP smoke tests
  - `chatbox.html`: active web UI entry file
- `data/`: local runtime data (ignored for submission)
- `logs/`: runtime logs (ignored for submission)

## Run

- Web mode: `python chatagent/api_server.py`
- Terminal mode: `python chatagent/main.py`

## Test

- `python -m pytest chatagent/tests -q`

## Cleanup Notes

- Removed legacy front-end file: `chatagent/index.html`
- Removed local runtime artifacts from `data/` and `logs/`
- Runtime artifacts are now ignored through `.gitignore`
