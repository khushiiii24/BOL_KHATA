#!/usr/bin/env bash
# Mac / Linux version of start.bat
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First-time setup..."
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Open it, paste your Gnani API key after GNANI_API_KEY=, save, then run ./start.sh again."
  exit 0
fi
# close an older Bol Khata that is still running on port 8000 (it would keep serving old code)
if command -v lsof >/dev/null 2>&1; then
  OLD=$(lsof -ti tcp:8000 -sTCP:LISTEN || true)
  [ -n "$OLD" ] && echo "Closing an older Bol Khata that was still running..." && kill $OLD && sleep 1
fi
echo "Bol Khata is running at http://localhost:8000 (Ctrl+C to stop)"
( sleep 3 && (open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null) ) &
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
