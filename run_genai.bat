@echo off
setlocal
REM 优先用项目内 .venv（需先: python -m venv .venv 然后 .venv\Scripts\pip install -r requirements.txt）
REM 否则回退系统 python（需已 pip install playwright）
set PW=%~dp0.venv\Scripts\python.exe
if not exist "%PW%" set "PW=python"
"%PW%" "%~dp0scrape_genai.py" %*
endlocal
