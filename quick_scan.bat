@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
python -m pip install -r requirements.txt
python -m coach_miranda_miner scan
pause

