#!/usr/bin/env python3
"""
Bhasha Shiksha Setu — entry point.
Run from the project root:   python run.py
"""
import os
import sys

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
