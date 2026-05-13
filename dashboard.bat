@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
python -m pip install -r requirements.txt
python -m streamlit run coach_miranda_miner/dashboard.py --server.address 127.0.0.1 --server.port 8502
