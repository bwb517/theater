#!/bin/bash
set -e

echo "=== THEATER Deploy ==="

git pull

docker compose up -d --build

echo ""
echo "=== Done ==="
echo "First deploy? Seed the database:"
echo "  docker compose exec backend python seed_data.py"
