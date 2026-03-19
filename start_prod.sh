#!/bin/bash
echo "========================================================="
echo " Starting PRODUCTION Environment"
echo " Database: data/dashboard_prod.db"
echo " Port: 8001 (multi-worker configuration)"
echo "========================================================="

export DB_PATH="data/dashboard_prod.db"
export ENV="prod"

# Initialize DB
python -c "from backend.database import init_db; init_db()"

# Start FastAPI server
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --workers 4
