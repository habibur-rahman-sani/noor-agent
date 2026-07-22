@echo off
REM Windows — এক কমান্ডে Noor Agent চালু করুন:  start.bat  (ডাবল-ক্লিক করলেও চলবে)
cd /d "%~dp0"
echo Noor Agent build ^& start (first time takes a few minutes)...
docker compose up -d --build
echo.
echo DONE! Open in browser:  http://localhost:8000
echo Username: agno   Password: noor12345
echo Logs:  docker compose logs -f agno
pause
