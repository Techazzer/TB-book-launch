#!/bin/bash
echo "========================================================="
echo " Starting TEST Environment"
echo " Database: data/dashboard_test.db"
echo " Port: 8000 (with hot-reload enabled)"
echo "========================================================="

export DB_PATH="data/dashboard_test.db"
export ENV="test"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Initialize DB
python -c "from database import init_db; init_db()"

# Start FastAPI server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
