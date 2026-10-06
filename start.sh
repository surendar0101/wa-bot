#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Backend setup
cd "$ROOT/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# Frontend setup
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi

# Start backend in background
cd "$ROOT/backend"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
cd "$ROOT/frontend"
echo ""
echo "============================================"
echo "  MVP Demo starting..."
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo "============================================"
echo ""
npm run dev

kill $BACKEND_PID 2>/dev/null || true
