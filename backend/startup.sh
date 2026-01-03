#!/bin/bash
echo "🚀 Installing dependencies..."
pip install -r requirements.txt

echo "🔥 Starting SpiderFlow API..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
