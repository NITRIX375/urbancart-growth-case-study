"""Vercel entry point: the same dashboard + agent as Part3_Prototype/app.py, as one serverless function.

Vercel's Python runtime looks for a top-level class named `handler` derived from
BaseHTTPRequestHandler. The Engine (DuckDB over data/raw) is built once per warm instance.
Charts are served statically from public/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Part3_Prototype.app import make_handler   # noqa: E402
from Part3_Prototype.engine import Engine      # noqa: E402

_Base = make_handler(Engine())


class handler(_Base):  # noqa: N801  (name required by Vercel)
    pass
