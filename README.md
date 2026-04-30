# OOP Final Project

This repository contains a session-based counseling chat system built with object-oriented design.

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
