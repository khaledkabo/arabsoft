@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r arabsoft_service_system\requirements.txt
python launcher.py
