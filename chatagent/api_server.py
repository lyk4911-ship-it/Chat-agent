# api_server.py - Thin entrypoint for the HTTP interface layer
# -*- coding: utf-8 -*-

import os
import sys

import uvicorn

# Keep script-run compatibility: `python chatagent/api_server.py`
CURRENT_DIR = os.path.dirname(__file__)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from interfaces.http.app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)

