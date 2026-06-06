#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo ""
echo "============================================================"
echo " THEATER Frontend starting on http://localhost:3000"
echo "============================================================"
echo ""

npm run dev
