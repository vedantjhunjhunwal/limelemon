#!/usr/bin/env bash
# One-step launcher (macOS/Linux). Usage: ./run.sh   (set ANTHROPIC_API_KEY first for AI mode)
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
python app.py
