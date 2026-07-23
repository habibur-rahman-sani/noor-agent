@echo off
REM Windows — এক কমান্ডে Noor Agent চালু করুন:  start.bat  (ডাবল-ক্লিক করলেও চলবে)
cd /d "%~dp0"
REM .env na thakle (GitHub theke clone korle) example theke banao — na hole docker .env-ke folder baniye felbe
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo New .env created ^(you can set the API key later from the UI gear/settings^).
)
echo Noor Agent build ^& start (first time takes a few minutes)...
docker compose up -d --build
echo.
echo DONE! Open in browser:  http://localhost:8000
echo Username: agno   Password: noor12345
echo Logs:  docker compose logs -f agno
pause
