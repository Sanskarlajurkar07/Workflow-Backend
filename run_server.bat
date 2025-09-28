@echo off
cd /d "E:\Workflow Automation p4 - Copy\backend"
call .\venv_minimal\Scripts\activate
echo.
echo Starting Quick Server on port 3001...
echo.
echo If you see "INFO: Uvicorn running on..." message, the server is working!
echo.
echo Test in browser: http://localhost:3001
echo.
python quick_server.py
pause 