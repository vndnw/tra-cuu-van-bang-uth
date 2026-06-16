@echo off
title Bot Tra Cuu Van Bang UTH - VPS
color 0A
echo =============================================================
echo   KHOI CHAY BOT TRA CUU VAN BANG UTH TREN WINDOWS SERVER VPS
echo =============================================================
echo.

:: Kiem tra va cai dat pip dependencies
echo [1/2] Dang kiem tra va cai dat cac thu vien Python...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [LOI] Khong the cai dat cac thu vien. Vui long kiem tra Python da duoc add vao PATH.
    pause
    exit /b
)
echo OK! Cac thu vien da san sang.
echo.

:: Khoi chay Bot
echo [2/2] Dang khoi dong Bot...
echo.
python app.py
pause
