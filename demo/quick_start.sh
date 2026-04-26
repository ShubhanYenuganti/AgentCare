#!/usr/bin/env bash
# Autocare Demo Quick Start
# Seeds the database and starts both servers in the background.
# Usage: bash demo/quick_start.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Checking dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not found"; exit 1; }

echo "==> Seeding database..."
cd "$ROOT"
python3 data/seed.py

echo "==> Starting FastAPI backend (port 8000)..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Starting Vite frontend (port 5173)..."
cd "$ROOT/dashboard"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "---"
echo "Servers running:"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "PIDs: backend=$BACKEND_PID frontend=$FRONTEND_PID"
echo "To stop: kill $BACKEND_PID $FRONTEND_PID"
echo "---"

sleep 3
if command -v open >/dev/null 2>&1; then
  open "http://localhost:5173"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:5173"
fi

wait
