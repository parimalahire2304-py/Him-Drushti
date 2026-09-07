@echo off
title Him-Drushti — Laptop-2 Onboard DSS Dashboard
color 0B
echo ============================================================
echo   HIM-DRUSHTI  —  LAPTOP-2  ONBOARD / SHIP DASHBOARD
echo ============================================================
echo.

REM -- Resolve project root: the bat lives in scripts/communication/.
REM    dashboard/ lives one level above; if not, assume bat is at root.
REM    %%~fI normalises the ..\ so no relative segments remain in paths. --
set PROJECT_ROOT=%~dp0
if not exist "%PROJECT_ROOT%dashboard\backend.py" for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI\"

REM -- Duplicate-launch guard: if the dashboard is already serving,
REM    do NOT start a second copy. --
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK]  Dashboard already running on port 5000:
    echo         http://localhost:5000
    echo.
    echo   Skipping — no duplicate backend started.
    echo   (Close the existing window, then re-run, to restart it.)
    echo.
    pause
    exit /b 0
)

echo [1/1] Starting onboard dashboard (Flask + MQTT receiver)...
echo       Dashboard:  http://localhost:5000
echo       Ctrl+C to stop.
echo.

REM -- Set PYTHONPATH for Phase 6 imports (transport, schemas, etc.) --
set PYTHONPATH=%PROJECT_ROOT%scripts\communication

REM -- Run the dashboard backend (includes MQTT receiver thread) --
python "%PROJECT_ROOT%dashboard\backend.py" --broker 10.20.231.143 --port 1883 --listen-port 5000

echo.
echo ============================================================
echo   Dashboard exited.
echo ============================================================
pause
