@echo off
title Gonder Gebeya Bot
cd /d "%~dp0"
echo Starting Gonder Gebeya Bot...
call venv\Scripts\activate
python -u run.py
pause
