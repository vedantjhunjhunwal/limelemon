@echo off
REM One-step launcher (Windows). Set ANTHROPIC_API_KEY first for AI mode:  set ANTHROPIC_API_KEY=sk-ant-...
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
python app.py
