"""Vercel Python entrypoint - exposes the FastAPI app as a serverless function.

Vercel's @vercel/python runtime serves the module-level ASGI `app`. `vercel.json` rewrites all
paths to this function, so the whole /v1 API is served from one function.
"""
import os
import sys

_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(_here, "..", "apps", "api")))
sys.path.insert(0, os.path.abspath(os.path.join(_here, "..")))

from app.main import app  # noqa: E402  (path set up above)
