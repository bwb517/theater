#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "IMPORTANT: Edit backend/.env and add your ANTHROPIC_API_KEY before continuing."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt --quiet

if [ ! -f "theater.db" ]; then
    echo "Seeding database..."
    python seed_data.py
fi

echo ""
echo "============================================================"
echo " THEATER Backend starting on http://localhost:8000"
echo " API docs: http://localhost:8000/docs"
echo "============================================================"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
